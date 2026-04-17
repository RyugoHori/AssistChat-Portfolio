"""HybridSearcher と Reciprocal Rank Fusion のテスト。

pgvector や Re-ranker のモデル読み込みは避け、`HybridSearcher.__init__` を
スキップした薄いインスタンスで純粋ロジックを検証する。
"""

from __future__ import annotations

import math

import pytest

from rag_core.search import HybridSearcher, reciprocal_rank_fusion


class TestReciprocalRankFusion:
    """RRF は順位のみを使うため、スコアに依存せず検証可能"""

    def test_single_list_returns_expected_scores(self):
        rank_list = ["a", "b", "c"]
        result = reciprocal_rank_fusion([rank_list], k=60)

        assert result["a"] == pytest.approx(1.0 / 61)
        assert result["b"] == pytest.approx(1.0 / 62)
        assert result["c"] == pytest.approx(1.0 / 63)

    def test_empty_inputs(self):
        assert reciprocal_rank_fusion([]) == {}
        assert reciprocal_rank_fusion([[]]) == {}

    def test_two_lists_combine_scores_correctly(self):
        list1 = ["a", "b", "c"]
        list2 = ["c", "a", "d"]
        result = reciprocal_rank_fusion([list1, list2], k=60)

        expected_a = 1 / 61 + 1 / 62
        expected_c = 1 / 63 + 1 / 61
        assert result["a"] == pytest.approx(expected_a)
        assert result["c"] == pytest.approx(expected_c)

        # 両方のリストに現れる c と a が、1 つにしか現れない b/d より高スコアのはず
        assert result["a"] > result["b"]
        assert result["c"] > result["d"]

    def test_k_parameter_tunes_score_spread(self):
        """k が小さいほど上位と下位のスコア差が大きくなる"""
        rank_list = ["a", "b", "c", "d", "e"]
        small_k = reciprocal_rank_fusion([rank_list], k=10)
        large_k = reciprocal_rank_fusion([rank_list], k=100)

        spread_small = small_k["a"] - small_k["e"]
        spread_large = large_k["a"] - large_k["e"]
        assert spread_small > spread_large

    def test_ordering_preservation(self):
        rank_list = ["x", "y", "z"]
        result = reciprocal_rank_fusion([rank_list])
        # 辞書は順序を保持しないのでソートして検証
        sorted_items = sorted(result.items(), key=lambda x: -x[1])
        assert [doc for doc, _ in sorted_items] == ["x", "y", "z"]


@pytest.fixture
def hybrid_searcher() -> HybridSearcher:
    """
    __init__ をスキップして _apply_filters のテストに必要な最小限のインスタンスを生成

    重い依存（pgvector / BM25 / embedding モデル）を読み込まずに、
    フィルターロジックだけを検証できるようにする。
    """
    searcher = HybridSearcher.__new__(HybridSearcher)
    return searcher


class TestHybridSearcherFilters:
    """フィルター判定ロジックの単体テスト"""

    def test_no_filters_allows_everything(self, hybrid_searcher):
        item = {"metadata": {"category": "機械"}}
        assert hybrid_searcher._apply_filters(item, {}) is True

    def test_categories_filter_matches(self, hybrid_searcher):
        item = {"metadata": {"category": "機械"}}
        assert hybrid_searcher._apply_filters(item, {"categories": ["機械"]}) is True

    def test_categories_filter_excludes(self, hybrid_searcher):
        item = {"metadata": {"category": "機械"}}
        assert hybrid_searcher._apply_filters(item, {"categories": ["電気"]}) is False

    def test_equipment_hierarchy_filters(self, hybrid_searcher):
        item = {
            "metadata": {
                "category": "電気",
                "equipment1": "センサー",
                "equipment2": "圧力トランスミッタ",
                "equipment3": "PT-1",
            }
        }
        # 全階層マッチ
        assert hybrid_searcher._apply_filters(
            item,
            {
                "equipment1s": ["センサー"],
                "equipment2s": ["圧力トランスミッタ"],
                "equipment3s": ["PT-1"],
            },
        ) is True
        # 第2階層で不一致
        assert hybrid_searcher._apply_filters(
            item,
            {"equipment2s": ["温度センサ"]},
        ) is False

    def test_missing_metadata_field_excludes(self, hybrid_searcher):
        item = {"metadata": {"category": "機械"}}
        # equipment1 が無いので equipment1s フィルターで除外される
        assert hybrid_searcher._apply_filters(
            item,
            {"equipment1s": ["センサー"]},
        ) is False

    def test_empty_filter_list_is_ignored(self, hybrid_searcher):
        """空リストのフィルターは "未指定" として扱われる"""
        item = {"metadata": {"equipment1": "センサー"}}
        assert hybrid_searcher._apply_filters(item, {"equipment1s": []}) is True

    def test_location_and_line_filters(self, hybrid_searcher):
        item = {
            "metadata": {
                "location": "第1工場",
                "line": "A1000",
            }
        }
        assert hybrid_searcher._apply_filters(
            item,
            {"locations": ["第1工場"], "productionLines": ["A1000"]},
        ) is True
        assert hybrid_searcher._apply_filters(
            item,
            {"locations": ["第2工場"]},
        ) is False


class _StubDenseSearcher:
    """pgvector を模したスタブ"""

    def __init__(self, results):
        self._results = results

    def search(self, query_vector, top_k):
        return self._results[:top_k]


class _StubSparseSearcher:
    """BM25 を模したスタブ"""

    def __init__(self, results):
        self._results = results

    def search(self, tokenized_query, top_k):
        return self._results[:top_k]


class _StubEmbeddingService:
    """Embedding モデルを模したスタブ"""

    def encode(self, text, show_progress=False):
        return [0.1, 0.2, 0.3]


class _StubTokenizer:
    def tokenize(self, text):
        return text.split()


class _FixedRetrievalSettings(dict):
    """settings["retrieval"] のスタブ"""


def _make_result(chunk_id: str, score: float) -> tuple:
    return (
        {
            "chunk_id": chunk_id,
            "doc_id": f"doc_{chunk_id}",
            "text": f"テスト本文 {chunk_id}",
            "metadata": {"category": "機械", "equipment1": "センサー"},
        },
        score,
    )


class TestHybridSearcherSearch:
    """search() の統合動作（RRF + メタデータ付与 + フィルター + Re-ranker スキップ）"""

    def test_search_merges_dense_and_sparse(self, monkeypatch, hybrid_searcher):
        # Dense: A → B, Sparse: B → C なら RRF で B が 1 位
        dense_results = [_make_result("A", 0.9), _make_result("B", 0.6)]
        sparse_results = [_make_result("B", 0.8), _make_result("C", 0.5)]

        hybrid_searcher.dense_searcher = _StubDenseSearcher(dense_results)
        hybrid_searcher.sparse_searcher = _StubSparseSearcher(sparse_results)
        hybrid_searcher.embedding_service = _StubEmbeddingService()
        hybrid_searcher.tokenizer = _StubTokenizer()
        hybrid_searcher.reranker = None

        from rag_core import search as search_module

        monkeypatch.setattr(
            search_module,
            "settings",
            {
                "retrieval": {
                    "dense_top_k": 10,
                    "sparse_top_k": 10,
                    "final_top_k": 5,
                    "enable_reranking": False,
                },
                "data": {"index_path": "/tmp"},
                "embedding": {"model_name": "x", "cache_folder": "/tmp"},
            },
        )

        results = hybrid_searcher.search("テスト")

        chunk_ids = [r["chunk_id"] for r in results]
        # B は両方にヒットするので上位
        assert chunk_ids[0] == "B"
        assert set(chunk_ids) == {"A", "B", "C"}
        # RRF スコアが付与されている
        assert all("score" in r and math.isfinite(r["score"]) for r in results)

    def test_search_empty_query_returns_empty(self, hybrid_searcher):
        assert hybrid_searcher.search("") == []

    def test_search_applies_filter_before_reranking(self, monkeypatch, hybrid_searcher):
        """フィルターで除外されたアイテムは Re-ranker に渡されないこと"""
        # 2 件取るが、1 件はカテゴリー不一致で除外される想定
        dense_results = [
            (
                {
                    "chunk_id": "keep",
                    "doc_id": "doc_keep",
                    "text": "残す",
                    "metadata": {"category": "機械"},
                },
                0.9,
            ),
            (
                {
                    "chunk_id": "drop",
                    "doc_id": "doc_drop",
                    "text": "除外される",
                    "metadata": {"category": "電気"},
                },
                0.8,
            ),
        ]
        hybrid_searcher.dense_searcher = _StubDenseSearcher(dense_results)
        hybrid_searcher.sparse_searcher = _StubSparseSearcher([])
        hybrid_searcher.embedding_service = _StubEmbeddingService()
        hybrid_searcher.tokenizer = _StubTokenizer()
        hybrid_searcher.reranker = None

        from rag_core import search as search_module

        monkeypatch.setattr(
            search_module,
            "settings",
            {
                "retrieval": {
                    "dense_top_k": 10,
                    "sparse_top_k": 10,
                    "final_top_k": 5,
                    "enable_reranking": False,
                },
            },
        )

        results = hybrid_searcher.search("テスト", filters={"categories": ["機械"]})
        assert [r["chunk_id"] for r in results] == ["keep"]
