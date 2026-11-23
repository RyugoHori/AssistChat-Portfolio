"""
tools/evaluation/evaluate.py のテスト。
指標の計算はスタブで確かめる。キーワード検索の回帰テストだけ、デモデータからBM25を作る。
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

from rag_core.chunking import TextChunker
from rag_core.config import settings
from rag_core.normalize import normalize_text
from rag_core.sparse_index import BM25IndexManager
from rag_core.tokenization import tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "evaluation"))

ev = importlib.import_module("evaluate")

REPO = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO / "tools" / "evaluation"
# lemma-rescored-v1.4.json の評価A・キーワード検索の Hit@5（0.947）から 0.05 を引いた値。
# 40問規模では 0.05 未満の差は誤差の範囲として扱う。
SPARSE_HIT5_MIN = 0.897


def _chunk(doc_id: str, date: str = "2024-01-01") -> dict:
    return {"doc_id": doc_id, "metadata": {"doc_id": doc_id, "date": date}}


def _write_csv(path: Path, header: list, rows: list) -> Path:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _label_row_count(path: Path) -> int:
    """判定の行数だけ数える。中身が壊れていてもここでは止めず、load_set_a に気づかせる。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def _write_queries(tmp_path: Path) -> Path:
    return _write_csv(
        tmp_path / "queries.csv",
        ["query_id", "query", "type", "version"],
        [
            ("A001", "ALM1102 出て止まった", "error_code", "v1"),
            ("A002", "ベルトのとこから変な音", "paraphrase", "v1"),
            ("A003", "サーボアンプ 過負荷", "term", "v1"),
        ],
    )


def test_metrics():
    assert ev.first_relevant_rank(["d1", "d2", "d3"], {"d3"}) == 3
    # 6位の正解は画面に出ないので、見つからなかった扱い
    assert ev.first_relevant_rank(["d1", "d2", "d3", "d4", "d5", "d6"], {"d6"}) is None

    ranks = [1, None, 3]
    assert ev.hit_rate(ranks) == pytest.approx(2 / 3)
    assert ev.mrr(ranks) == pytest.approx((1 + 0 + 1 / 3) / 3)


def test_to_doc_ids_removes_duplicates():
    results = [_chunk("d2"), _chunk("d1"), _chunk("d2"), {"metadata": {"doc_id": "d3"}}, _chunk("d1")]
    assert ev.to_doc_ids(results) == ["d2", "d1", "d3"]


def test_win_tie_loss():
    assert ev.win_tie_loss([1, None, 2, None, 3], [2, 4, 2, None, None]) == {"win": 2, "tie": 2, "loss": 1}


def test_count_unjudged():
    # 6件目は上位5件の外なので数えない
    assert ev.count_unjudged(["d1", "d2", "d3", "d4", "d5", "d6"], {"d1", "d3"}) == 3


def test_filter_for_backtest():
    results = [
        _chunk("before", "2024-12-31"),
        _chunk("same_day", "2025-01-01"),
        _chunk("after", "2025-02-01"),
        _chunk("query_doc", "2024-06-01"),
    ]
    kept = ev.filter_for_backtest(results, "2025-01-01", "query_doc")
    assert ev.to_doc_ids(kept) == ["before"]


def test_load_set_a_rejects_blank_and_duplicate(tmp_path):
    """「一度付けた判定は変えず、足すだけ」を機械的に守るため、空欄と同じ組の2行目で止まる。"""
    queries = _write_queries(tmp_path)
    cases = [
        ([("A001", "d1", "1"), ("A001", "d2", "")], "1／0 以外"),
        ([("A001", "d1", "1"), ("A001", "d1", "0")], "2つ以上"),
    ]
    for rows, message in cases:
        labels = _write_csv(tmp_path / "labels.csv", ["query_id", "doc_id", "relevant"], rows)
        with pytest.raises(ValueError, match=message):
            ev.load_set_a(queries, labels)


def test_load_set_a_excludes_queries_without_relevant(tmp_path):
    """正解0件の質問は集計から除くが、検索して上位5件を残すので質問のリストには入れる。"""
    queries = _write_queries(tmp_path)
    labels = _write_csv(
        tmp_path / "labels.csv",
        ["query_id", "doc_id", "relevant"],
        [("A001", "d1", "1"), ("A001", "d2", "0"), ("A002", "d3", "0")],
    )
    items, excluded = ev.load_set_a(queries, labels)
    assert [item["query_id"] for item in items] == ["A001", "A002", "A003"]
    assert items[0]["relevant"] == {"d1"}
    assert items[0]["judged"] == {"d1", "d2"}
    assert (items[1]["relevant"], items[1]["judged"]) == (set(), {"d3"})
    assert (items[2]["relevant"], items[2]["judged"]) == (set(), set())
    assert excluded == ["A002", "A003"]


def test_score_runs_matches_run_set():
    """保存した上位5件から計算し直しても、検索したときの順位と同じ指標になる。"""
    items = [
        {"query_id": "A001", "query": "q1", "type": "error_code", "relevant": {"a"}, "judged": {"a", "x"}},
        {"query_id": "A002", "query": "q2", "type": "term", "relevant": {"b"}, "judged": {"b"}},
        {"query_id": "A003", "query": "q3", "type": "term", "relevant": {"c"}, "judged": {"c"}},
    ]
    responses = {
        ("q1", "hybrid_rerank"): ["a", "a", "x", "y", "z"],
        ("q2", "hybrid_rerank"): ["y", "b"],
        ("q3", "hybrid_rerank"): ["y"],
        ("q1", "dense"): ["x", "a"],
        ("q2", "dense"): ["b"],
        ("q3", "dense"): [],
    }

    def search(query: str, mode: str, top_k: int) -> list:
        assert top_k == ev.K
        return [_chunk(doc_id) for doc_id in responses[(query, mode)]][:top_k]

    results = {mode: ev.run_set(items, search, mode, backtest=False) for mode in ("hybrid_rerank", "dense")}
    assert results["hybrid_rerank"]["runs"]["A001"] == ["a", "x", "y", "z"]

    scored = ev.score_runs({mode: result["runs"] for mode, result in results.items()}, items)
    for mode, result in results.items():
        assert scored["modes"][mode]["hit5"] == round(ev.hit_rate(result["ranks"]), 3)
        assert scored["modes"][mode]["mrr5"] == round(ev.mrr(result["ranks"]), 3)
    assert scored["modes"]["hybrid_rerank"] == {
        "hit5": 0.667,
        "mrr5": 0.5,
        "unjudged5": 4,
        "by_type": {"error_code": {"n": 1, "hit5": 1.0}, "term": {"n": 2, "hit5": 0.5}},
    }
    assert scored["modes"]["dense"]["unjudged5"] == 0
    assert scored["comparisons"] == {"hybrid_rerank_vs_dense": {"win": 1, "tie": 1, "loss": 1}}


def test_sparse_regression(tmp_path):
    """デモデータからキーワード検索の索引を作り、Hit@5 が基準を下回っていないことを見る。

    モデルとDBが要る評価はCIでは回さない。正規化や単語の分け方を変えたときに、精度の落ちにここで気づく。
    """
    labels = EVAL_DIR / "labels.csv"
    if not labels.exists():
        pytest.skip("labels.csv がない")
    if _label_row_count(labels) == 0:
        pytest.skip("labels.csv の判定の行が0")

    df = pd.read_csv(REPO / "data" / "demo" / "demo_logs.csv")
    # 前処理と同じ正規化。索引のテキストだけ整えないと、検索側の単語と一致しない。
    df["text"] = df["text"].apply(lambda x: normalize_text(str(x)) if pd.notna(x) else x)
    chunks = TextChunker(chunk_size=500, chunk_overlap=50).chunk_documents(
        df.to_dict("records"), text_field="text", doc_id_field="doc_id"
    )

    index_path = tmp_path / "maintenance.bm25"
    meta_path = tmp_path / "maintenance.bm25.meta.pkl"
    built = BM25IndexManager(str(index_path), str(meta_path))
    built.build([tokenizer.tokenize(chunk.text) for chunk in chunks])
    built.save([chunk.to_dict() for chunk in chunks])
    # 本番は保存した索引を読み直して検索する。save するまで metadata が空なので、読み込み経路を通す。
    searcher = BM25IndexManager(str(index_path), str(meta_path))

    items, _excluded = ev.load_set_a(EVAL_DIR / "queries.csv", labels)
    ranks = []
    for item in items:
        # 正解0件の質問は指標に入れない（score_runs と同じ）。
        if not item["relevant"]:
            continue
        # 検索時と同じく、質問も正規化してから単語に分ける。
        tokens = tokenizer.tokenize(normalize_text(item["query"]))
        hits = searcher.search(tokens, top_k=settings["retrieval"]["sparse_top_k"])
        results = [meta for meta, _score in hits][: ev.K]
        ranks.append(ev.first_relevant_rank(ev.to_doc_ids(results), item["relevant"]))
    if not ranks:
        raise ValueError("集計できる質問がありません（正解が1件もない）")

    hit5 = round(ev.hit_rate(ranks), 3)
    assert hit5 >= SPARSE_HIT5_MIN, f"sparse Hit@5={hit5}"


def test_score_runs_skips_queries_without_relevant():
    """正解0件の質問は上位5件を残しても指標に入れない。追加の判定で正解が付けば、同じ上位5件から計算し直せる。"""
    items = [
        {"query_id": "A001", "query": "q1", "type": "term", "relevant": {"a"}, "judged": {"a"}},
        {"query_id": "A002", "query": "q2", "type": "term", "relevant": set(), "judged": {"x"}},
    ]
    runs = {"hybrid_rerank": {"A001": ["a"], "A002": ["y", "b"]}}
    scored = ev.score_runs(runs, items)["modes"]["hybrid_rerank"]
    assert (scored["hit5"], scored["unjudged5"], scored["by_type"]["term"]["n"]) == (1.0, 0, 1)

    items[1]["relevant"] = {"b"}
    rescored = ev.score_runs(runs, items)["modes"]["hybrid_rerank"]
    assert (rescored["hit5"], rescored["mrr5"], rescored["by_type"]["term"]["n"]) == (1.0, 0.75, 2)
