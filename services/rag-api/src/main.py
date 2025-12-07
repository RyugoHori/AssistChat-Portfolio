'''
RAGバックエンドサーバー

FastAPIで検索APIを提供する。
最初はStreamlitで作ってたけど、複数人で使うならちゃんとしたAPIサーバーが必要だった。
'''

import asyncio
import logging
import math
import time
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

# rag-coreパッケージから共通ロジックをインポート
from rag_core import HybridSearcher, settings as core_settings

from src.api.models import (
    SearchRequest,
    SearchResponse,
    DocumentDetail,
    FilterMetadata,
    SearchResult,
    HierarchyNode,
)

# ==================== 設定 ====================

class Settings(BaseSettings):
    """アプリケーション設定"""
    
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # CORSの許可オリジン
    # 開発時はlocalhost:3000、本番はfrontend:3000
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://frontend:3000",
    ]
    
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# ==================== ヘルパー関数 ====================

def _build_hierarchy(metadata: List[Dict[str, Any]]) -> List[HierarchyNode]:
    """
    メタデータから設備の階層構造を構築
    工場 → ライン → 設備1 → 設備2 → 設備3 の階層
    
    フロントエンドのツリービューで使う
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

    # ツリー構造をHierarchyNodeのリストに変換
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
    """
    フィルター用のメタデータを生成
    フロントエンドのフィルターパネルで使う選択肢のリスト
    """
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
            'hierarchy': []
        }
    
    hierarchy = _build_hierarchy(metadata)
    
    # ユニークな値を集める
    categories = set()
    for doc in metadata:
        meta = doc.get('metadata', {})
        category = meta.get('category')
        if category:
            categories.add(category)
    
    # 故障分類
    work_types = set()
    for doc in metadata:
        meta = doc.get('metadata', {})
        work_type = meta.get('work_type')
        if work_type:
            work_types.add(work_type)
    
    # 生産ライン
    lines = set()
    for doc in metadata:
        meta = doc.get('metadata', {})
        line = meta.get('line')
        if line:
            lines.add(line)
    
    # 設備階層
    equipment1s = set()
    equipment2s = set()
    equipment3s = set()
    for doc in metadata:
        meta = doc.get('metadata', {})
        if meta.get('equipment1'):
            equipment1s.add(meta['equipment1'])
        if meta.get('equipment2'):
            equipment2s.add(meta['equipment2'])
        if meta.get('equipment3'):
            equipment3s.add(meta['equipment3'])
    
    # 年度範囲
    years = []
    for doc in metadata:
        meta = doc.get('metadata', {})
        date_str = meta.get('date', '')
        if date_str and len(date_str) >= 4:
            try:
                year = int(date_str[:4])
                if 2000 <= year <= 2100:
                    years.append(year)
            except (ValueError, TypeError):
                continue
    
    return {
        'categories': sorted(list(categories)),
        'productionLines': sorted(list(lines)),
        'workTypes': sorted(list(work_types)),
        'equipment1s': sorted(list(equipment1s)),
        'equipment2s': sorted(list(equipment2s)),
        'equipment3s': sorted(list(equipment3s)),
        'yearRange': {
            'startYear': min(years) if years else 2020,
            'endYear': max(years) if years else 2024
        },
        'totalDocuments': len(metadata),
        'hierarchy': hierarchy
    }

async def run_async_search(
    request: Request,
    query: str,
    k: int,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    非同期で検索を実行
    
    検索処理はCPUバウンドなので、run_in_executorで別スレッドに逃がす。
    そうしないと検索中に他のリクエストがブロックされる。
    """
    if not hasattr(request.app.state, 'searcher') or not request.app.state.searcher:
        logger.error("Searcher not initialized")
        return []

    loop = asyncio.get_running_loop()
    
    return await loop.run_in_executor(
        None,
        partial(
            request.app.state.searcher.search,
            query=query,
            filters=filters
        )
    )


# ==================== アプリケーションライフサイクル ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時と終了時の処理"""
    logger.info("Starting RAG service...")
    
    try:
        # HybridSearcherの初期化
        # 初回起動時はモデルのダウンロードで時間かかる
        logger.info("Initializing HybridSearcher (this may take a while on first run)...")
        app.state.searcher = HybridSearcher()
        
        # メタデータへのショートカット
        app.state.metadata = app.state.searcher.dense_searcher.metadata
        
        logger.info(f"✅ Search system ready. Docs: {len(app.state.metadata)}")
            
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)
        app.state.searcher = None
        app.state.metadata = []
    
    yield
    
    logger.info("Shutting down...")


# ==================== FastAPIアプリ ====================

app = FastAPI(
    title="AssistChat RAG Service",
    description="保全記録検索API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS設定
# フロントエンドから繋がらなくてハマった　これでOK
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== APIエンドポイント ====================

@app.get("/health")
async def health_check(request: Request):
    """ヘルスチェック。Docker Composeのヘルスチェックで使う"""
    searcher = getattr(request.app.state, 'searcher', None)
    
    return {
        "status": "healthy" if searcher else "degraded",
        "timestamp": datetime.now().isoformat(),
        "index_loaded": searcher is not None,
        "documents": len(request.app.state.metadata) if hasattr(request.app.state, 'metadata') else 0,
        "reranker_ready": searcher.reranker.is_available if searcher and searcher.reranker else False
    }


@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(req: SearchRequest, request: Request):
    """メインの検索エンドポイント"""
    start_time = time.time()
    if not hasattr(request.app.state, 'searcher') or not request.app.state.searcher:
        raise HTTPException(status_code=503, detail="Search service not fully initialized.")

    try:
        filters_dict = req.filters.model_dump(exclude_none=True) if req.filters else None
        if filters_dict:
            logger.info(f"Applying filters: {filters_dict}")
        
        search_results = await run_async_search(request, req.query, req.k, filters=filters_dict)
        
        results = []
        for res in search_results:
            meta = res.get('metadata', res)
            date_str = meta.get('date', '')
            
            # スコア取得ロジックを修正: rerank_scoreがあればそれを優先
            raw_score = res.get('rerank_score')
            if raw_score is None:
                raw_score = res.get('score', 0.0)
            
            # NaN チェック (JSON serialization エラー回避)
            if isinstance(raw_score, float) and math.isnan(raw_score):
                raw_score = 0.0
            
            # 必要に応じて正規化（もしRe-rankerのスコアが0-1の範囲外なら）
            if raw_score > 1.0 or raw_score < 0.0:
                # 簡易的な正規化（実際にはモデルの出力を確認して調整すべき）
                score = max(0.0, min(1.0, (raw_score + 10) / 20))
            else:
                score = raw_score
            
            # 念のための最終チェック
            if isinstance(score, float) and math.isnan(score):
                score = 0.0

            results.append(
                SearchResult(
                    doc_id=meta.get('doc_id', ''),
                    title=meta.get('title', '故障対応記録'),
                    summary=res.get('text', '')[:150] + '...',
                    score=score,
                    confidence=int(score * 100), # UI表示用 (0-100%)
                    snippet=res.get('text', '')[:200] + '...',
                    date=date_str,
                    machine=meta.get('machine'),
                    line=meta.get('line'),
                    category=meta.get('category', 'その他'),
                    match_fields={"text": score},
                    location=meta.get('location'),
                    symptom=meta.get('symptom'),
                    action_taken=meta.get('action_taken'),
                    parts_replaced=meta.get('parts_replaced'),
                    operator=meta.get('operator')
                )
            )
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Search completed: query='{req.query[:30]}...', results={len(results)}, time={processing_time}ms")
        
        return SearchResponse(results=results, total=len(results), processingTime=processing_time)
        
    except Exception as e:
        logger.error(f"Search endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/metadata", response_model=FilterMetadata)
async def get_filter_metadata(request: Request):
    """フィルター用のメタデータを返す"""
    if not hasattr(request.app.state, 'metadata') or not request.app.state.metadata:
        raise HTTPException(status_code=503, detail="Metadata not loaded")
    try:
        metadata_dict = _get_filter_metadata(request.app.state.metadata)
        return FilterMetadata(**metadata_dict)
    except Exception as e:
        logger.error(f"Failed to get filter metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/docs/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str, request: Request):
    """ドキュメント詳細を返す"""
    if not hasattr(request.app.state, 'metadata') or not request.app.state.metadata:
        raise HTTPException(status_code=503, detail="Metadata service not initialized.")

    # 線形探索だけど8000件程度なら問題ない
    doc = next((
        m for m in request.app.state.metadata 
        if m.get('metadata', {}).get('doc_id') == doc_id or m.get('doc_id') == doc_id
    ), None)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    meta = doc.get('metadata', doc)
    
    return DocumentDetail(
        doc_id=doc_id,
        title=meta.get('title', 'N/A'),
        content=doc.get('text', ''),
        metadata=doc,
        full_text=doc.get('text', ''),
        chunks=[{"chunk_id": f"{doc_id}_chunk_0", "text": doc.get('text', ''), "chunk_index": 0, "source_doc_id": doc_id}],
        attachments=[],
        action_taken=meta.get('action_taken'),
        parts_replaced=meta.get('parts_replaced'),
    )


@app.post("/api/feedback")
async def submit_feedback(doc_id: str, rating: int, helpful: bool, comment: Optional[str] = None):
    """フィードバック受付。今はログに出すだけ、将来的にはDBに保存したい"""
    logger.info(f"Feedback received: doc_id={doc_id}, rating={rating}, helpful={helpful}, comment='{comment}'")
    return {"success": True, "message": "フィードバックを受け付けました"}


@app.get("/api/stats")
async def get_stats(request: Request):
    """統計情報"""
    searcher = getattr(request.app.state, 'searcher', None)
    embedding_config = core_settings.get("embedding", {})
    model_name = embedding_config.get("model_name", "unknown")
    
    return {
        "total_documents": len(request.app.state.metadata) if hasattr(request.app.state, 'metadata') else 0,
        "model": model_name,
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
