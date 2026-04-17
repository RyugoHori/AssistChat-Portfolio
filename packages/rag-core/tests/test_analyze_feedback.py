"""
tools/analyze_feedback.py のロジックテスト
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_TOOLS_ROOT = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(_TOOLS_ROOT))

analyze = importlib.import_module("analyze_feedback")


def _write_jsonl(path: Path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


class TestSummarize:
    def test_empty_records(self):
        assert analyze.summarize([]) == {"total": 0}

    def test_basic_counts(self):
        records = [
            {"doc_id": "a", "rating": 5, "helpful": True, "mode": "search"},
            {"doc_id": "b", "rating": 1, "helpful": False, "mode": "chat"},
            {"doc_id": "c", "rating": 4, "helpful": True, "mode": "search"},
        ]
        summary = analyze.summarize(records)
        assert summary["total"] == 3
        assert summary["helpful_count"] == 2
        assert summary["helpful_rate"] == pytest.approx(2 / 3)
        assert summary["average_rating"] == pytest.approx(3.33, rel=1e-2)
        assert summary["mode_distribution"] == {"search": 2, "chat": 1}


class TestExtractLowRated:
    def test_aggregates_by_doc(self):
        records = [
            {"doc_id": "bad", "rating": 1, "helpful": False, "comment": "使えない"},
            {"doc_id": "bad", "rating": 2, "helpful": False, "comment": "違う事例"},
            {"doc_id": "good", "rating": 5, "helpful": True},
        ]
        low = analyze.extract_low_rated_docs(records, threshold=2)
        assert len(low) == 1
        assert low[0]["doc_id"] == "bad"
        assert low[0]["count"] == 2
        assert "使えない" in low[0]["comments"]

    def test_respects_threshold(self):
        records = [
            {"doc_id": "a", "rating": 3, "helpful": True},
        ]
        # rating=3 は threshold=2 では除外されないが、helpful=True なので選ばれない
        assert analyze.extract_low_rated_docs(records, threshold=2) == []


class TestBuildTrainingPairs:
    def test_generates_positive_and_negative(self):
        records = [
            {"query": "異音", "doc_id": "a", "helpful": True, "rating": 5, "mode": "search"},
            {"query": "異音", "doc_id": "b", "helpful": False, "rating": 1, "mode": "search"},
            {"doc_id": "c", "helpful": True},  # query 欠損 → 除外
        ]
        pairs = analyze.build_training_pairs(records)
        assert len(pairs) == 2
        labels = {(p["doc_id"], p["label"]) for p in pairs}
        assert ("a", 1.0) in labels
        assert ("b", 0.0) in labels


class TestLoadFeedback:
    def test_loads_valid_jsonl(self, tmp_path):
        path = tmp_path / "feedback.jsonl"
        records = [{"doc_id": "a", "rating": 5, "helpful": True}]
        _write_jsonl(path, records)
        loaded = analyze.load_feedback(path)
        assert loaded == records

    def test_skips_malformed_lines(self, tmp_path):
        path = tmp_path / "feedback.jsonl"
        path.write_text(
            '{"doc_id":"a","rating":5,"helpful":true}\n'
            'NOT_JSON\n'
            '{"doc_id":"b","rating":3,"helpful":false}\n',
            encoding="utf-8",
        )
        loaded = analyze.load_feedback(path)
        assert len(loaded) == 2

    def test_missing_file_returns_empty(self, tmp_path):
        assert analyze.load_feedback(tmp_path / "nonexistent.jsonl") == []
