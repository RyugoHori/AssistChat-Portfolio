"""ヘルスチェック / 統計エンドポイント。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from rag_core import settings as core_settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Docker Compose の healthcheck で叩かれる軽量エンドポイント。"""
    searcher = getattr(request.app.state, "searcher", None)
    llm = getattr(request.app.state, "llm", None)
    metadata = getattr(request.app.state, "metadata", [])

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


@router.get("/api/stats")
async def get_stats(request: Request):
    """ドキュメント件数と Embedding モデル名を返す。"""
    searcher = getattr(request.app.state, "searcher", None)
    metadata = getattr(request.app.state, "metadata", [])
    embedding_config = core_settings.get("embedding", {})

    return {
        "total_documents": len(metadata),
        "model": embedding_config.get("model_name", "unknown"),
        "status": "operational" if searcher else "initializing",
    }
