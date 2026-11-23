"""
tools/evaluation/build_backtest.py のテスト
手作りの数件の記録で、評価Bの質問と正解の決め方を確かめる
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "evaluation"))

bt = importlib.import_module("build_backtest")

COLUMNS = ["doc_id", "date", "equipment2", "cause_category", "symptom", "root_cause"]


def _record(doc_id: str, day: str, equipment2: str = "切断機", cause_category: str = "摩耗・劣化") -> dict:
    return {
        "doc_id": doc_id,
        "date": day,
        "equipment2": equipment2,
        "cause_category": cause_category,
        "symptom": f"{doc_id}の症状",
        "root_cause": f"{doc_id}の原因",
    }


def _items_by_query(records: list, months: int = 12) -> dict:
    items, _ = bt.build_items(records, months)
    return {item["query_doc_id"]: item["relevant_doc_ids"].split(";") for item in items}


def test_relevant_are_before_query_date():
    records = [
        _record("d0", "2023-06-01"),
        _record("d1", "2024-12-31"),  # 最新日付のちょうど12か月前。質問にはならず、正解にはなる
        _record("d2", "2025-03-01"),
        _record("d3", "2025-03-01"),  # d2 と同じ日
        _record("d4", "2025-12-31"),
    ]
    by_query = _items_by_query(records)
    assert sorted(by_query) == ["d2", "d3", "d4"]
    # 同じ日の記録は、評価の絞り込み（質問より前の日付）で消えるので正解にしない
    assert by_query["d2"] == ["d0", "d1"]
    assert by_query["d3"] == ["d0", "d1"]
    assert by_query["d4"] == ["d0", "d1", "d2", "d3"]


def test_query_itself_is_not_relevant():
    records = [_record("d0", "2025-01-10"), _record("d1", "2025-06-01")]
    by_query = _items_by_query(records)
    assert "d1" not in by_query["d1"]
    assert by_query == {"d1": ["d0"]}


def test_excludes_other_and_no_relevant():
    records = [
        _record("d0", "2024-01-01"),
        _record("d1", "2024-01-01", equipment2="洗浄機"),
        _record("d2", "2025-02-01", cause_category="その他"),  # 同じ設備で過去の記録があっても除外
        _record("d3", "2025-03-01", equipment2="洗浄機", cause_category="部品破損"),  # 同じ設備・同じ原因の過去がない
        _record("d4", "2025-04-01", cause_category="緩み・ズレ"),  # 同じ設備・同じ原因の過去がない
        _record("d5", "2025-05-01"),
    ]
    items, excluded = bt.build_items(records, 12)
    assert [item["query_doc_id"] for item in items] == ["d5"]
    assert items[0]["n_relevant"] == 1
    assert excluded == {"その他": 1, "正解0件": 2}


def test_filled_spotcheck_is_not_overwritten(tmp_path, monkeypatch):
    data = tmp_path / "demo_logs.csv"
    with open(data, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows([_record("d0", "2024-06-01"), _record("d1", "2025-03-01"), _record("d2", "2025-06-01")])
    backtest, spotcheck = tmp_path / "backtest.csv", tmp_path / "spotcheck.csv"
    argv = [
        "build_backtest.py",
        "--input",
        str(data),
        "--output",
        str(backtest),
        "--spotcheck",
        str(spotcheck),
        "--spot-n",
        "2",
    ]

    monkeypatch.setattr(sys, "argv", argv)
    bt.main()
    rows = bt.read_csv(spotcheck)
    rows[0]["ok"] = "1"
    bt.write_csv(spotcheck, bt.SPOTCHECK_COLUMNS, rows)
    filled = spotcheck.read_bytes()
    backtest.unlink()

    # ok を1行でも記入したら、backtest.csv も含めて何も書かずに止まる
    with pytest.raises(SystemExit):
        bt.main()
    assert spotcheck.read_bytes() == filled
    assert not backtest.exists()

    monkeypatch.setattr(sys, "argv", argv + ["--force"])
    bt.main()
    assert backtest.exists()
    assert not bt.spotcheck_is_filled(spotcheck)
