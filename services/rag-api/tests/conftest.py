"""
pytest フィクスチャ

FastAPI アプリは本番では PostgreSQL / OpenAI / Cross-Encoder を起動時に読み込むため、
テストではこれらを依存注入で置き換え、軽量な TestClient ベースの検証を可能にする。
"""

from __future__ import annotations

from typing import List

import pytest


class _FakeLLMService:
    """LLMService のふるまいをテスト用に置換するスタブ"""

    def __init__(self, available: bool = True, confidence: str = "high"):
        self.available = available
        self._confidence = confidence

    def rewrite_query(self, query: str, history=None) -> str:
        if history:
            return f"{query}（書き換え済み）"
        return query

    def assess_confidence(self, search_results) -> str:
        if not search_results:
            return "low"
        return self._confidence

    def extract_sources(self, search_results, top_k: int = 3):
        return [
            {
                "doc_id": r.get("metadata", {}).get("doc_id", r.get("doc_id", "?")),
                "title": r.get("metadata", {}).get("symptom", "テスト"),
                "score": 0.85,
            }
            for r in search_results[:top_k]
        ]

    async def stream_answer(self, query, search_results, history=None):
        for token in ["回答", "を", "生成", "しました"]:
            yield token


class _FakeSearcher:
    """HybridSearcher のふるまいをテスト用に置換するスタブ"""

    def __init__(self, results=None):
        self._results = results or []
        self.dense_searcher = type(
            "Dense",
            (),
            {"metadata": [{"metadata": {"doc_id": "doc_1"}, "text": "t"}]},
        )()
        self.reranker = None

    def search(self, query, filters=None):
        return self._results


@pytest.fixture
def fake_llm():
    return _FakeLLMService()


@pytest.fixture
def unavailable_llm():
    return _FakeLLMService(available=False, confidence="unavailable")


@pytest.fixture
def fake_searcher():
    return _FakeSearcher(results=[
        {
            "chunk_id": "c_1",
            "doc_id": "doc_1",
            "text": "ベアリング交換で復旧した事例",
            "score": 0.85,
            "metadata": {
                "doc_id": "doc_1",
                "symptom": "異音",
                "category": "機械",
            },
        }
    ])


@pytest.fixture
def app_with_fakes(fake_llm, fake_searcher):
    """
    FastAPI アプリを lifespan を回さずに取得し、state をスタブに差し替える

    `TestClient(app)` で通常の lifespan を通すと検索エンジン・LLM の初期化が走るため、
    app を import → state に手動注入 → TestClient を作る順序とする。
    """
    from contextlib import asynccontextmanager

    from src import main as main_module

    @asynccontextmanager
    async def _noop_lifespan(app):
        app.state.searcher = fake_searcher
        app.state.metadata = fake_searcher.dense_searcher.metadata
        app.state.llm = fake_llm
        yield

    # lifespan を差し替えた新しいアプリを作成
    original_lifespan = main_module.app.router.lifespan_context
    main_module.app.router.lifespan_context = _noop_lifespan
    try:
        yield main_module.app
    finally:
        main_module.app.router.lifespan_context = original_lifespan
