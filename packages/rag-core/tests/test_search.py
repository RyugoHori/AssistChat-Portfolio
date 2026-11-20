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
        assert (
            hybrid_searcher._apply_filters(
                item,
                {
                    "equipment1s": ["センサー"],
                    "equipment2s": ["圧力トランスミッタ"],
                    "equipment3s": ["PT-1"],
                },
            )
            is True
        )
        # 第2階層で不一致
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"equipment2s": ["温度センサ"]},
            )
            is False
        )

    def test_missing_metadata_field_excludes(self, hybrid_searcher):
        item = {"metadata": {"category": "機械"}}
        # equipment1 が無いので equipment1s フィルターで除外される
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"equipment1s": ["センサー"]},
            )
            is False
        )

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
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"locations": ["第1工場"], "productionLines": ["A1000"]},
            )
            is True
        )
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"locations": ["第2工場"]},
            )
            is False
        )

    def test_year_range_keeps_in_range(self, hybrid_searcher):
        item = {"metadata": {"date": "2024-03-15"}}
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"yearRange": {"startYear": 2023, "endYear": 2024}},
            )
            is True
        )

    def test_year_range_excludes_outside(self, hybrid_searcher):
        item = {"metadata": {"date": "2020-01-01"}}
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"yearRange": {"startYear": 2023, "endYear": 2024}},
            )
            is False
        )

    def test_year_range_excludes_missing_date(self, hybrid_searcher):
        item = {"metadata": {}}
        assert (
            hybrid_searcher._apply_filters(
                item,
                {"yearRange": {"startYear": 2023, "endYear": 2024}},
            )
            is False
        )


class _StubDenseSearcher:
    """pgvector を模したスタブ"""

    def __init__(self, results):
        self._results = results
        self.received_chunk_ids = None

    def search(self, query_vector, top_k, chunk_ids=None):
        self.received_chunk_ids = chunk_ids
        results = self._results
        if chunk_ids is not None:
            results = [item for item in results if item[0]["chunk_id"] in chunk_ids]
        return results[:top_k]


class _StubSparseSearcher:
    """BM25 を模したスタブ"""

    def __init__(self, results, metadata=None):
        self._results = results
        self.metadata = [item for item, _score in results] if metadata is None else metadata

    def search(self, tokenized_query, top_k, chunk_ids=None):
        results = self._results
        if chunk_ids is not None:
            results = [item for item in results if item[0]["chunk_id"] in chunk_ids]
        return results[:top_k]


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
        """絞り込みは候補を取る前にかかり、条件に合わない記録は検索にも並べ替えにも渡らないこと"""
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
        dense = _StubDenseSearcher(dense_results)
        hybrid_searcher.dense_searcher = dense
        hybrid_searcher.sparse_searcher = _StubSparseSearcher(
            [],
            metadata=[item for item, _score in dense_results],
        )
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

        hybrid_searcher.search("テスト")
        assert dense.received_chunk_ids is None

        results = hybrid_searcher.search("テスト", filters={"categories": ["機械"]})
        assert dense.received_chunk_ids == {"keep"}
        assert [r["chunk_id"] for r in results] == ["keep"]


class _StubReranker:
    """Re-ranker を模したスタブ。受け取った候補を記録し、逆順にして返す"""

    is_available = True

    def __init__(self):
        self.received = None

    def rerank(self, query, results, top_k=None):
        self.received = [r["chunk_id"] for r in results]
        return list(reversed(results))


class _RecordingEmbedding(_StubEmbeddingService):
    def __init__(self):
        self.texts = []

    def encode(self, text, show_progress=False):
        self.texts.append(text)
        return super().encode(text, show_progress)


class _RecordingTokenizer(_StubTokenizer):
    def __init__(self):
        self.texts = []

    def tokenize(self, text):
        self.texts.append(text)
        return super().tokenize(text)


class _RecordingReranker(_StubReranker):
    def __init__(self):
        super().__init__()
        self.queries = []

    def rerank(self, query, results, top_k=None):
        self.queries.append(query)
        return super().rerank(query, results, top_k)


class _ForbiddenStub:
    """呼ばれたら失敗するスタブ。使わない側の検索が動いていないことを確かめる"""

    def search(self, *args, **kwargs):
        raise AssertionError("使わない検索が呼ばれた")

    def encode(self, *args, **kwargs):
        raise AssertionError("使わない埋め込みが呼ばれた")

    def tokenize(self, *args, **kwargs):
        raise AssertionError("使わないトークン化が呼ばれた")


def _setup_searcher(monkeypatch, searcher, dense_results, sparse_results, reranker=None):
    from rag_core import search as search_module

    searcher.dense_searcher = _StubDenseSearcher(dense_results)
    searcher.sparse_searcher = _StubSparseSearcher(
        sparse_results,
        metadata=[item for item, _score in dense_results + sparse_results],
    )
    searcher.embedding_service = _StubEmbeddingService()
    searcher.tokenizer = _StubTokenizer()
    searcher.reranker = reranker
    monkeypatch.setattr(
        search_module,
        "settings",
        {
            "retrieval": {
                "dense_top_k": 10,
                "sparse_top_k": 10,
                "final_top_k": 5,
                "rerank_candidates": 10,
            },
        },
    )


class TestHybridSearcherModes:
    """mode と top_k の切り替え（評価で4方式を同じ条件で比べるため）"""

    def test_each_mode_returns_expected_results(self, monkeypatch, hybrid_searcher):
        dense_results = [_make_result("A", 0.9), _make_result("B", 0.6)]
        sparse_results = [_make_result("B", 8.0), _make_result("C", 5.0)]
        reranker = _StubReranker()
        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results, reranker)

        dense = hybrid_searcher.search("テスト", mode="dense")
        assert [(r["chunk_id"], r["score"]) for r in dense] == [("A", 0.9), ("B", 0.6)]

        sparse = hybrid_searcher.search("テスト", mode="sparse")
        assert [(r["chunk_id"], r["score"]) for r in sparse] == [("B", 8.0), ("C", 5.0)]
        # 索引側の metadata に score を書き込んでいない
        assert "score" not in sparse_results[0][0]

        hybrid = hybrid_searcher.search("テスト", mode="hybrid")
        assert [r["chunk_id"] for r in hybrid] == ["B", "A", "C"]
        # Re-ranker が使える状態でも hybrid では呼ばない
        assert reranker.received is None
        assert [r["chunk_id"] for r in hybrid_searcher.search("テスト", mode="hybrid", top_k=2)] == ["B", "A"]

        rerank = hybrid_searcher.search("テスト", mode="hybrid_rerank")
        assert reranker.received == ["B", "A", "C"]
        assert [r["chunk_id"] for r in rerank] == ["C", "A", "B"]

    def test_unused_retriever_is_not_called(self, monkeypatch, hybrid_searcher):
        dense_results = [_make_result("A", 0.9)]
        sparse_results = [_make_result("B", 8.0)]

        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results)
        hybrid_searcher.sparse_searcher = _ForbiddenStub()
        hybrid_searcher.tokenizer = _ForbiddenStub()
        assert [r["chunk_id"] for r in hybrid_searcher.search("テスト", mode="dense")] == ["A"]

        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results)
        hybrid_searcher.dense_searcher = _ForbiddenStub()
        hybrid_searcher.embedding_service = _ForbiddenStub()
        assert [r["chunk_id"] for r in hybrid_searcher.search("テスト", mode="sparse")] == ["B"]

    def test_filters_apply_to_all_modes(self, monkeypatch, hybrid_searcher):
        dense_results = [_make_result("D1", 0.9), _make_result("D2", 0.8)]
        sparse_results = [_make_result("S1", 8.0), _make_result("S2", 5.0)]
        dense_results[1][0]["metadata"] = {"category": "電気"}
        sparse_results[1][0]["metadata"] = {"category": "電気"}
        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results, _StubReranker())

        expected = {
            "dense": {"D1"},
            "sparse": {"S1"},
            "hybrid": {"D1", "S1"},
            "hybrid_rerank": {"D1", "S1"},
        }
        for mode, chunk_ids in expected.items():
            results = hybrid_searcher.search("テスト", filters={"categories": ["機械"]}, mode=mode)
            assert {r["chunk_id"] for r in results} == chunk_ids, mode

    def test_invalid_mode_and_top_k_raise(self, monkeypatch, hybrid_searcher):
        _setup_searcher(monkeypatch, hybrid_searcher, [], [])

        with pytest.raises(ValueError):
            hybrid_searcher.search("テスト", mode="bm25")
        for top_k in (0, 11):
            with pytest.raises(ValueError):
                hybrid_searcher.search("テスト", top_k=top_k)

    def test_default_matches_hybrid_rerank_top5(self, monkeypatch, hybrid_searcher):
        # 統合後の候補が16件あり、Re-ranker に渡す10件と返す5件の両方で切られる
        dense_results = [_make_result(f"D{i}", 0.9 - i / 100) for i in range(8)]
        sparse_results = [_make_result(f"S{i}", 8.0 - i) for i in range(8)]
        reranker = _StubReranker()
        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results, reranker)

        default = hybrid_searcher.search("テスト")
        received = reranker.received
        hybrid_top10 = hybrid_searcher.search("テスト", mode="hybrid", top_k=10)

        assert received == [r["chunk_id"] for r in hybrid_top10]
        assert len(default) == 5
        assert default == hybrid_searcher.search("テスト", mode="hybrid_rerank", top_k=5)

    def test_top_k_three_returns_at_most_three(self, monkeypatch, hybrid_searcher):
        dense_results = [_make_result(f"D{i}", 0.9 - i / 100) for i in range(8)]
        sparse_results = [_make_result(f"S{i}", 8.0 - i) for i in range(8)]
        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, sparse_results, _StubReranker())

        results = hybrid_searcher.search("テスト", top_k=3)
        assert len(results) <= 3

    def test_query_is_normalized_before_search(self, monkeypatch, hybrid_searcher):
        """質問の全角や略語を、索引と同じ形にしてから各方式に渡す。"""
        dense_results = [_make_result("A", 0.9)]
        embedding = _RecordingEmbedding()
        tokenizer = _RecordingTokenizer()
        reranker = _RecordingReranker()
        _setup_searcher(monkeypatch, hybrid_searcher, dense_results, [], reranker)
        hybrid_searcher.embedding_service = embedding
        hybrid_searcher.tokenizer = tokenizer

        for mode in ("dense", "sparse", "hybrid", "hybrid_rerank"):
            embedding.texts.clear()
            tokenizer.texts.clear()
            reranker.queries.clear()
            hybrid_searcher.search("ＣＶ　停止", mode=mode)
            if mode != "sparse":
                assert embedding.texts == ["コンベア 停止"], mode
            if mode != "dense":
                assert tokenizer.texts == ["コンベア 停止"], mode
            if mode == "hybrid_rerank":
                assert reranker.queries == ["コンベア 停止"]


def test_bm25_chunk_ids_returns_hit_outside_top_k_and_skips_zero_score():
    """top_k の外でも指定した記録は返し、キーワードが無い記録は返さない。"""
    from rank_bm25 import BM25Okapi

    from rag_core.sparse_index import BM25IndexManager

    tokenized = [
        ["軸受", "交換"],
        ["軸受"],
        ["コンベア"],
        ["モーター"],
        ["センサー"],
        ["配管"],
    ]
    manager = BM25IndexManager.__new__(BM25IndexManager)
    manager.index = BM25Okapi(tokenized)
    manager.metadata = [{"chunk_id": f"c{i}"} for i in range(len(tokenized))]

    top = manager.search(["軸受"], top_k=1)
    assert len(top) == 1
    top_id = top[0][0]["chunk_id"]
    other = "c0" if top_id == "c1" else "c1"
    picked = manager.search(["軸受"], top_k=1, chunk_ids={other})
    assert [item["chunk_id"] for item, _score in picked] == [other]
    assert manager.search(["軸受"], top_k=1, chunk_ids={"c2"}) == []
