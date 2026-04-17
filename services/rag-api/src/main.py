"""
RAG バックエンドサーバー

FastAPI で検索 API と AI チャット API を提供する。
- /api/search: ハイブリッド検索（同期）
- /api/chat:   LLM 回答をストリーミングで返却（NDJSON）
"""

import asyncio
import json
import logging
import re
import time
import uuid
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_settings import BaseSettings
from starlette.middleware.base import BaseHTTPMiddleware

from rag_core import (
    HybridSearcher,
    LLMService,
    calculate_display_score,
    sanitize_float_values,
    settings as core_settings,
)

from src.api.feedback_store import FeedbackStore, get_default_store
from src.api.models import (
    ChatRequest,
    DocumentDetail,
    FeedbackRequest,
    FeedbackResponse,
    FilterMetadata,
    HierarchyNode,
    SearchRequest,
    SearchResponse,
    SearchResult,
)


# ==================== 設定 ====================

class Settings(BaseSettings):
    """アプリケーション設定"""

    HOST: str = "0.0.0.0"
    PORT: int = 8001

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ]

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


# ==================== ロギング（構造化 JSON） ====================

class JsonLogFormatter(logging.Formatter):
    """
    1 行 1 JSON のシンプルなログフォーマッタ

    Datadog / CloudWatch Logs などの集約基盤で検索しやすい形式。
    追加フィールドは `logger.info("...", extra={"key": "value"})` で渡す。
    """

    # logging.LogRecord が最初から持っている属性（extra でなければ含めない）
    _RESERVED = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message", "module",
        "msecs", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # extra で渡されたキー（request_id 等）を拾う
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    """root logger に JSON フォーマッタを適用（uvicorn 配下のログも拾う）"""
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    # 既存ハンドラを一旦クリアしてから再設定
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)


_configure_logging()
logger = logging.getLogger(__name__)


# ==================== Request ID ミドルウェア ====================

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    入ってきたリクエストに X-Request-ID を付与し、ログに埋め込む

    - ヘッダーに X-Request-ID があればそれを利用、無ければ uuid4
    - 処理時間も一緒にログ出力
    - レスポンスヘッダにも同じ ID を返す（現場からの障害報告に使える）
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


# ==================== Prompt Injection 簡易検知 ====================

# 完全なブロックは目的外。"怪しい入力が来たら気付ける" ための監視用パターン
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above)\s+(instructions?|rules?)", re.I),
    re.compile(r"(これまでの|以前の|今までの)\s*(指示|ルール|命令).*?(無視|忘れて|破棄)", re.I),
    re.compile(r"(あなたは|今から).{0,30}(になって|として振る舞|role\s*play)", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"jailbreak", re.I),
]


def _detect_injection(text: str) -> Optional[str]:
    """疑わしいパターンがあれば最初にマッチしたパターンを返す（無ければ None）"""
    if not text:
        return None
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


# ==================== ヘルパー関数 ====================

def _build_hierarchy(metadata: List[Dict[str, Any]]) -> List[HierarchyNode]:
    """
    メタデータから設備の階層構造（工場 → ライン → 設備1〜3）を構築

    フロントエンドのツリービュー表示で使用する。
    """
    tree: Dict[str, Any] = {}

    for doc in metadata:
        meta = doc.get('metadata', {})
        loc = meta.get('location')
        line = meta.get('line')
        eq1 = meta.get('equipment1')
        eq2 = meta.get('equipment2')
        eq3 = meta.get('equipment3')

        if not all([loc, line]):
            continue

        if loc not in tree:
            tree[loc] = {}
        if line not in tree[loc]:
            tree[loc][line] = {}

        if eq1:
            if eq1 not in tree[loc][line]:
                tree[loc][line][eq1] = {}
            if eq2:
                if eq2 not in tree[loc][line][eq1]:
                    tree[loc][line][eq1][eq2] = {}
                if eq3:
                    tree[loc][line][eq1][eq2][eq3] = True

    result = []
    for loc_name, lines in sorted(tree.items()):
        loc_node = HierarchyNode(id=loc_name, label=loc_name, children=[])
        for line_name, eq1s in sorted(lines.items()):
            line_node = HierarchyNode(id=line_name, label=line_name, children=[])
            for eq1_name, eq2s in sorted(eq1s.items()):
                eq1_node = HierarchyNode(id=eq1_name, label=eq1_name, children=[])
                for eq2_name, eq3s in sorted(eq2s.items()):
                    eq2_node = HierarchyNode(id=eq2_name, label=eq2_name, children=[])
                    for eq3_name in sorted(eq3s.keys()):
                        eq3_node = HierarchyNode(id=eq3_name, label=eq3_name, children=[])
                        eq2_node.children.append(eq3_node)
                    eq1_node.children.append(eq2_node)
                line_node.children.append(eq1_node)
            loc_node.children.append(line_node)
        result.append(loc_node)

    return result


def _get_filter_metadata(metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
    """フィルターパネル用のメタデータ（利用可能値一覧）を生成"""
    if not metadata:
        return {
            'categories': [],
            'productionLines': [],
            'workTypes': [],
            'equipment1s': [],
            'equipment2s': [],
            'equipment3s': [],
            'yearRange': {'startYear': 2020, 'endYear': 2024},
            'totalDocuments': 0,
            'hierarchy': [],
        }

    hierarchy = _build_hierarchy(metadata)

    categories, work_types, lines = set(), set(), set()
    equipment1s, equipment2s, equipment3s = set(), set(), set()
    years: List[int] = []

    for doc in metadata:
        meta = doc.get('metadata', {})
        if c := meta.get('category'):
            categories.add(c)
        if wt := meta.get('work_type'):
            work_types.add(wt)
        if ln := meta.get('line'):
            lines.add(ln)
        if eq1 := meta.get('equipment1'):
            equipment1s.add(eq1)
        if eq2 := meta.get('equipment2'):
            equipment2s.add(eq2)
        if eq3 := meta.get('equipment3'):
            equipment3s.add(eq3)
        date_str = meta.get('date', '')
        if date_str and len(date_str) >= 4:
            try:
                year = int(date_str[:4])
                if 2000 <= year <= 2100:
                    years.append(year)
            except (ValueError, TypeError):
                continue

    return {
        'categories': sorted(categories),
        'productionLines': sorted(lines),
        'workTypes': sorted(work_types),
        'equipment1s': sorted(equipment1s),
        'equipment2s': sorted(equipment2s),
        'equipment3s': sorted(equipment3s),
        'yearRange': {
            'startYear': min(years) if years else 2020,
            'endYear': max(years) if years else 2024,
        },
        'totalDocuments': len(metadata),
        'hierarchy': hierarchy,
    }


async def run_async_search(
    request: Request,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    非同期で検索を実行（CPU バウンド処理を別スレッドに逃がす）

    検索中に他のリクエストがブロックされるのを防ぐため、
    `run_in_executor` で別スレッドに委譲する。
    """
    searcher = getattr(request.app.state, 'searcher', None)
    if searcher is None:
        logger.error("Searcher not initialized")
        return []

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(searcher.search, query=query, filters=filters),
    )


# ==================== アプリケーションライフサイクル ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    起動時・終了時処理

    検索エンジン（PostgreSQL pgvector + BM25）と
    LLM サービス（OpenAI API）を初期化する。
    """
    logger.info("=" * 80)
    logger.info("RAG API サービス起動中...")
    logger.info("=" * 80)

    try:
        logger.info("検索エンジンを初期化中...")
        app.state.searcher = HybridSearcher()
        app.state.metadata = app.state.searcher.dense_searcher.metadata
        logger.info(
            "✅ 検索エンジン準備完了: %d件のドキュメント",
            len(app.state.metadata),
        )

        logger.info("LLMサービスを初期化中...")
        app.state.llm = LLMService()
        if app.state.llm.available:
            logger.info("✅ LLMサービス準備完了（OpenAI API連携）")
        else:
            logger.warning("⚠️ LLMサービス利用不可（OPENAI_API_KEY 未設定）")

        logger.info("=" * 80)
        logger.info("✅ すべてのサービスが正常に起動しました")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("❌ 初期化エラー: %s", e, exc_info=True)
        app.state.searcher = None
        app.state.metadata = []
        app.state.llm = None

    yield

    logger.info("サービスをシャットダウンしています...")


# ==================== FastAPI アプリ ====================

app = FastAPI(
    title="AssistChat RAG Service",
    description="保全記録検索 API - ハイブリッド検索 + LLM 対話機能",
    version="3.0.0",
    lifespan=lifespan,
)

# Request ID を最も外側に置くことで CORS 含む全ての処理をログに載せる
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# ==================== 検索系エンドポイント ====================

@app.get("/health")
async def health_check(request: Request):
    """ヘルスチェック（Docker Compose のヘルスチェックで使用）"""
    searcher = getattr(request.app.state, 'searcher', None)
    llm = getattr(request.app.state, 'llm', None)
    metadata = getattr(request.app.state, 'metadata', [])

    return {
        "status": "healthy" if searcher else "degraded",
        "timestamp": datetime.now().isoformat(),
        "index_loaded": searcher is not None,
        "documents": len(metadata),
        "reranker_ready": (
            searcher.reranker.is_available
            if searcher and searcher.reranker else False
        ),
        "llm_ready": bool(llm and llm.available),
    }


@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(req: SearchRequest, request: Request):
    """メインの検索エンドポイント"""
    start_time = time.time()
    if not getattr(request.app.state, 'searcher', None):
        raise HTTPException(status_code=503, detail="Search service not fully initialized.")

    try:
        filters_dict = req.filters.model_dump(exclude_none=True) if req.filters else None
        if filters_dict:
            logger.info("Applying filters: %s", filters_dict)

        search_results = await run_async_search(request, req.query, filters=filters_dict)

        results = []
        for res in search_results:
            meta = res.get('metadata', res)
            score = calculate_display_score(res)
            text = res.get('text', '')

            results.append(
                SearchResult(
                    doc_id=meta.get('doc_id', ''),
                    title=meta.get('title', '故障対応記録'),
                    summary=text[:150] + '...' if text else '',
                    score=score,
                    confidence=int(score * 100),
                    snippet=text[:200] + '...' if text else '',
                    date=meta.get('date', ''),
                    machine=meta.get('machine'),
                    line=meta.get('line'),
                    category=meta.get('category', 'その他'),
                    match_fields={"text": score},
                    location=meta.get('location'),
                    symptom=meta.get('symptom'),
                    action_taken=meta.get('action_taken'),
                    parts_replaced=meta.get('parts_replaced'),
                    operator=meta.get('operator'),
                )
            )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(
            "Search completed: query='%s...', results=%d, time=%dms",
            req.query[:30], len(results), processing_time,
        )
        return SearchResponse(results=results, total=len(results), processingTime=processing_time)

    except Exception as e:
        logger.error("Search endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/metadata", response_model=FilterMetadata)
async def get_filter_metadata(request: Request):
    """フィルターパネル用のメタデータを返す"""
    metadata = getattr(request.app.state, 'metadata', None)
    if not metadata:
        raise HTTPException(status_code=503, detail="Metadata not loaded")
    try:
        return FilterMetadata(**_get_filter_metadata(metadata))
    except Exception as e:
        logger.error("Failed to get filter metadata: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/docs/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str, request: Request):
    """ドキュメント詳細を返す"""
    metadata = getattr(request.app.state, 'metadata', None)
    if not metadata:
        raise HTTPException(status_code=503, detail="Metadata service not initialized.")

    # 2 万件規模であれば線形探索で十分（インデックス化のコストを回避）
    doc = next(
        (
            m for m in metadata
            if m.get('metadata', {}).get('doc_id') == doc_id or m.get('doc_id') == doc_id
        ),
        None,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    meta = doc.get('metadata', doc)
    text = doc.get('text', '')
    return DocumentDetail(
        doc_id=doc_id,
        title=meta.get('title', 'N/A'),
        content=text,
        metadata=doc,
        full_text=text,
        chunks=[{
            "chunk_id": f"{doc_id}_chunk_0",
            "text": text,
            "chunk_index": 0,
            "source_doc_id": doc_id,
        }],
        attachments=[],
        action_taken=meta.get('action_taken'),
        parts_replaced=meta.get('parts_replaced'),
    )


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    """
    フィードバックを受け付けて JSONL に追記

    蓄積されたデータは `tools/analyze_feedback.py` で集計し、
    低評価ドキュメント分析や Re-ranker ファインチューニング用の
    正解ペア抽出に利用する。
    """
    store: FeedbackStore = get_default_store()
    payload = store.append(feedback.model_dump())
    return FeedbackResponse(
        success=True,
        message="フィードバックを受け付けました。改善に活用させていただきます。",
        saved_at=datetime.fromisoformat(payload["saved_at"].rstrip("Z")),
    )


# ==================== AI チャットエンドポイント ====================

def _ndjson_line(payload: Dict[str, Any]) -> str:
    """NDJSON の 1 行に変換（NaN/Infinity をサニタイズ）"""
    safe = sanitize_float_values(payload)
    return json.dumps(safe, ensure_ascii=False) + "\n"


async def _chat_event_stream(
    request: Request,
    req: ChatRequest,
) -> AsyncIterator[str]:
    """
    /api/chat のストリーミング本体

    NDJSON 形式で以下のイベントを順に送出する:
    - meta:   引用元 / 書き換え後クエリ / 処理ステージ
    - token:  LLM から届いたトークン
    - done:   正常終了（confidence 等の確定情報）
    - error:  エラー発生（クライアントに表示）
    """
    llm: LLMService = request.app.state.llm
    start_time = time.time()
    request_id = getattr(request.state, "request_id", None)

    # 疑わしい入力を監視（ブロックはせずログで気付けるようにする）
    injection_hit = _detect_injection(req.query) or next(
        (_detect_injection(m.content) for m in req.messages if _detect_injection(m.content)),
        None,
    )
    if injection_hit:
        logger.warning(
            "prompt_injection_suspected",
            extra={
                "request_id": request_id,
                "pattern": injection_hit,
                "query_preview": req.query[:80],
            },
        )

    try:
        history = [m.model_dump() for m in req.messages]

        # 1. Query Rewriting（履歴がある場合のみ LLM で独立クエリに書き換え）
        yield _ndjson_line({"type": "stage", "stage": "rewriting"})
        loop = asyncio.get_running_loop()
        rewritten_query = await loop.run_in_executor(
            None,
            partial(llm.rewrite_query, query=req.query, history=history),
        )

        # 2. ハイブリッド検索（書き換え後クエリで検索）
        yield _ndjson_line({"type": "stage", "stage": "searching"})
        filters_dict = req.filters.model_dump(exclude_none=True) if req.filters else None
        search_results = await run_async_search(
            request,
            rewritten_query,
            filters=filters_dict,
        )

        # 3. 引用元・信頼度を即座に送出（回答生成前にユーザーへ表示できる）
        sources = llm.extract_sources(search_results)
        confidence = llm.assess_confidence(search_results)
        yield _ndjson_line({
            "type": "meta",
            "rewritten_query": rewritten_query,
            "original_query": req.query,
            "sources": sources,
            "result_count": len(search_results),
        })

        # 4. LLM ストリーミング生成
        yield _ndjson_line({"type": "stage", "stage": "generating"})
        async for token in llm.stream_answer(
            query=req.query,           # 元の質問を自然な形で LLM に渡す
            search_results=search_results,
            history=history,
        ):
            if token:
                yield _ndjson_line({"type": "token", "content": token})

        # 5. 完了イベント
        processing_time_ms = int((time.time() - start_time) * 1000)
        yield _ndjson_line({
            "type": "done",
            "confidence": confidence,
            "processingTime": processing_time_ms,
        })

    except Exception as e:
        logger.error("チャットストリーミング失敗: %s", e, exc_info=True)
        yield _ndjson_line({
            "type": "error",
            "message": "回答生成中にエラーが発生しました。しばらくしてから再度お試しください。",
            "detail": str(e)[:200],
        })


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    """
    対話式 RAG エンドポイント（ストリーミング / NDJSON）

    応答形式: `application/x-ndjson`
    クライアントは 1 行ごとに JSON をパースして段階的に UI を更新する。
    """
    llm = getattr(request.app.state, 'llm', None)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service not initialized. Please check server logs.",
        )

    return StreamingResponse(
        _chat_event_stream(request, req),
        media_type="application/x-ndjson",
        headers={
            # プロキシがバッファリングしないように明示
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== その他 ====================

@app.get("/api/stats")
async def get_stats(request: Request):
    """統計情報"""
    searcher = getattr(request.app.state, 'searcher', None)
    metadata = getattr(request.app.state, 'metadata', [])
    embedding_config = core_settings.get("embedding", {})

    return {
        "total_documents": len(metadata),
        "model": embedding_config.get("model_name", "unknown"),
        "status": "operational" if searcher else "initializing",
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )
