"""evaluator_rag.py のユニットテスト

LLM-as-judge 部分は API キー無しのヒューリスティックモードで検証する。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tools/evaluation を import パスに追加
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "tools" / "evaluation"))

from evaluator_rag import (  # noqa: E402
    RagEvaluationCase,
    RagEvaluator,
)


class TestContextPrecision:
    def test_all_relevant_top(self):
        score = RagEvaluator.evaluate_context_precision(
            retrieved_doc_ids=["a", "b", "c"],
            relevant_doc_ids=["a", "b", "c"],
        )
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_none_relevant(self):
        score = RagEvaluator.evaluate_context_precision(
            retrieved_doc_ids=["a", "b", "c"],
            relevant_doc_ids=["x", "y"],
        )
        assert score == 0.0

    def test_partial_weighted(self):
        # first position relevant → should be close to 1.0 for first-rank weighting
        score = RagEvaluator.evaluate_context_precision(
            retrieved_doc_ids=["a", "b", "c"],
            relevant_doc_ids=["a"],
        )
        # weighted_sum = 1/1 = 1.0, max_possible = 1.0 → 1.0
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_lower_rank_relevant(self):
        # relevant at rank 3 only
        score = RagEvaluator.evaluate_context_precision(
            retrieved_doc_ids=["x", "y", "a"],
            relevant_doc_ids=["a"],
        )
        # weighted_sum = 1/3, max_possible = 1.0
        assert score == pytest.approx(1.0 / 3, abs=1e-6)

    def test_empty_retrieved(self):
        assert RagEvaluator.evaluate_context_precision([], ["a"]) == 0.0


class TestHeuristicFaithfulness:
    def test_empty_answer(self):
        ev = RagEvaluator(api_key=None)
        assert ev.evaluate_faithfulness("", ["context"]) == 0.0

    def test_empty_contexts(self):
        ev = RagEvaluator(api_key=None)
        assert ev.evaluate_faithfulness("回答テキスト", []) == 0.0

    def test_fully_supported(self):
        ev = RagEvaluator(api_key=None)
        score = ev.evaluate_faithfulness(
            answer="インバータのアラーム原因は冷却ファン故障です",
            contexts=["インバータのアラーム原因は冷却ファン故障であり、交換が必要"],
        )
        assert score >= 0.5

    def test_unsupported(self):
        ev = RagEvaluator(api_key=None)
        score = ev.evaluate_faithfulness(
            answer="完全に無関係な主張ABCDEFG",
            contexts=["全く違う内容XYZ"],
        )
        assert score < 0.5


class TestHeuristicRelevancy:
    def test_relevant_answer(self):
        ev = RagEvaluator(api_key=None)
        score = ev.evaluate_answer_relevancy(
            query="インバータ アラーム 原因",
            answer="インバータのアラームは冷却ファンの故障が原因です",
        )
        assert score > 0.5

    def test_irrelevant_answer(self):
        ev = RagEvaluator(api_key=None)
        score = ev.evaluate_answer_relevancy(
            query="インバータ アラーム",
            answer="全く関係ない話",
        )
        assert score < 0.5


class TestEvaluateCase:
    def test_integrated(self):
        ev = RagEvaluator(api_key=None)
        case = RagEvaluationCase(
            query="インバータのアラーム原因",
            answer="インバータのアラームは冷却ファン故障が原因です",
            contexts=["インバータのアラーム原因は冷却ファン故障"],
            relevant_doc_ids=["doc_001"],
            retrieved_doc_ids=["doc_001", "doc_002"],
        )
        scores = ev.evaluate_case(case)
        assert 0.0 <= scores.faithfulness <= 1.0
        assert 0.0 <= scores.answer_relevancy <= 1.0
        assert 0.0 <= scores.context_precision <= 1.0
        assert scores.context_precision == pytest.approx(1.0, abs=1e-6)
