"""
tools/analyze_usage.py のテスト
手作りの数件のログで、週ごとの集計と、評価Aの質問候補の抽出を確かめる
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

au = importlib.import_module("analyze_usage")


def _search(search_id: str, saved_at: str, query: str = "異音") -> dict:
    return {"saved_at": saved_at, "search_id": search_id, "query": query, "doc_ids": [], "processing_ms": 100}


def test_summarize_weeks_in_jst():
    searches = [
        _search("s1", "2026-10-25T14:59:00Z"),  # 日本時間 10/25（日）23:59 → W43
        _search("s2", "2026-10-25T15:00:00Z"),  # 日本時間 10/26（月）0:00 → W44
        _search("s3", "2026-10-26T01:00:00Z"),
    ]
    opens = [
        {"saved_at": "2026-10-25T15:01:00Z", "search_id": "s1", "doc_id": "d1", "rank": 1},  # s1 を週をまたいで開いた
        {"saved_at": "2026-10-26T01:01:00Z", "search_id": "s3", "doc_id": "d2", "rank": 3},
    ]
    feedback = [
        {"saved_at": "2026-10-26T01:02:00Z", "doc_id": "d2", "helpful": True, "search_id": "s3", "rank": 3},
        {"saved_at": "2026-10-26T01:03:00Z", "doc_id": "d2", "helpful": False},
    ]
    rows = {r["week"]: r for r in au.summarize_weeks(searches, opens, feedback)}

    assert sorted(rows) == ["2026-W43", "2026-W44"]
    assert rows["2026-W43"]["searches"] == 1
    assert rows["2026-W43"]["no_open_rate"] == 0.0
    assert rows["2026-W43"]["mean_rank"] is None
    assert rows["2026-W43"]["helpful_rate"] is None
    assert rows["2026-W44"]["searches"] == 2
    assert rows["2026-W44"]["no_open_rate"] == pytest.approx(0.5)
    assert rows["2026-W44"]["mean_rank"] == pytest.approx(2.0)
    assert rows["2026-W44"]["feedback"] == 2
    assert rows["2026-W44"]["helpful_rate"] == pytest.approx(0.5)


def test_pick_candidates():
    searches = [
        _search("s1", "2026-10-26T01:00:00Z", "ALM1102 止まった"),
        _search("s2", "2026-10-26T02:00:00Z", "ベルト 変な音"),
        _search("s3", "2026-10-26T03:00:00Z", "INV 過電流"),
    ]
    opens = [
        {"saved_at": "2026-10-26T01:01:00Z", "search_id": "s1", "doc_id": "d1", "rank": 1},
        {"saved_at": "2026-10-26T03:01:00Z", "search_id": "s3", "doc_id": "d3", "rank": 2},
    ]
    feedback = [
        {"saved_at": "2026-10-26T01:02:00Z", "doc_id": "d1", "helpful": False, "search_id": "s1", "rank": 1},
        {"saved_at": "2026-10-26T03:02:00Z", "doc_id": "d3", "helpful": True, "search_id": "s3", "rank": 2},
        # search_id のない古いフィードバックは、どの検索のものか分からないので候補にしない
        {"saved_at": "2026-10-26T04:00:00Z", "doc_id": "d9", "helpful": False, "query": "INV 過電流"},
    ]
    candidates = au.pick_candidates(searches, opens, feedback)

    assert [(c["search_id"], c["query"], c["reason"]) for c in candidates] == [
        ("s1", "ALM1102 止まった", "役に立たなかった"),
        ("s2", "ベルト 変な音", "開かれなかった"),
    ]
    assert candidates[0]["saved_at"] == "2026-10-26T01:00:00Z"
