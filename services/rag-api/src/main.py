"""RAG バックエンドの FastAPI アプリ。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_core import HybridSearcher, LLMService

from src.config import configure_logging, settings
from src.middleware import RequestIdMiddleware
from src.routers import chat, feedback, health, search

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時に検索エンジンと LLM クライアントを初期化する。"""
    logger.info("RAG API startup")

    try:
        app.state.searcher = HybridSearcher()
        app.state.metadata = app.state.searcher.dense_searcher.metadata
        logger.info("searcher ready: documents=%d", len(app.state.metadata))

        app.state.llm = LLMService()
        if app.state.llm.available:
            logger.info("LLM ready (OpenAI)")
        else:
            logger.warning("LLM unavailable (OPENAI_API_KEY not set)")

    except Exception as e:
        logger.error("startup failed: %s", e, exc_info=True)
        app.state.searcher = None
        app.state.metadata = []
        app.state.llm = None

    yield
    logger.info("RAG API shutdown")


app = FastAPI(
    title="AssistChat RAG Service",
    description="保全記録検索 API - ハイブリッド検索 + LLM 対話機能",
    version="3.0.0",
    lifespan=lifespan,
)

# Request ID を最外側に置いて CORS 含む全処理をログに載せる。
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

app.include_router(health.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(feedback.router)


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )
