"""LLMService の単体テスト。OpenAI API は呼ばずロジックのみ検証する。"""

from __future__ import annotations

import pytest

from rag_core.llm import LLMService
from rag_core.scoring import calculate_display_score, sanitize_float_values


class TestCalculateDisplayScore:
    def test_rerank_score_in_range(self):
        assert calculate_display_score({"rerank_score": 0.8, "score": 0.1}) == 0.8

    def test_rerank_score_priority_over_score(self):
        assert calculate_display_score({"rerank_score": 0.5, "score": 0.9}) == 0.5

    def test_falls_back_to_score(self):
        assert calculate_display_score({"score": 0.42}) == 0.42

    def test_out_of_range_positive(self):
        # 3.0 は Cross-Encoder の logit 典型値。[0,1] に正規化される。
        v = calculate_display_score({"rerank_score": 3.0})
        assert 0.5 < v < 1.0

    def test_out_of_range_negative(self):
        v = calculate_display_score({"rerank_score": -3.0})
        assert 0.0 < v < 0.5

    def test_nan_returns_zero(self):
        assert calculate_display_score({"rerank_score": float("nan")}) == 0.0

    def test_inf_returns_zero(self):
        assert calculate_display_score({"rerank_score": float("inf")}) == 0.0

    def test_missing_scores_returns_zero(self):
        assert calculate_display_score({}) == 0.0

    def test_extreme_out_of_range_is_clipped(self):
        assert calculate_display_score({"rerank_score": 100.0}) == 1.0
        assert calculate_display_score({"rerank_score": -100.0}) == 0.0


class TestSanitizeFloatValues:
    def test_handles_nested_structure(self):
        payload = {
            "score": float("nan"),
            "inner": {"val": float("inf"), "ok": 1.0},
            "list": [1.0, float("nan"), 2.0],
        }
        cleaned = sanitize_float_values(payload)
        assert cleaned["score"] is None
        assert cleaned["inner"]["val"] is None
        assert cleaned["inner"]["ok"] == 1.0
        assert cleaned["list"] == [1.0, None, 2.0]

    def test_primitives_pass_through(self):
        assert sanitize_float_values(1) == 1
        assert sanitize_float_values("s") == "s"
        assert sanitize_float_values(None) is None
        assert sanitize_float_values(True) is True


@pytest.fixture
def llm() -> LLMService:
    return LLMService(api_key="dummy", model="gpt-test", score_threshold=0.6)


@pytest.fixture
def llm_unavailable() -> LLMService:
    import os

    backup = os.environ.pop("OPENAI_API_KEY", None)
    try:
        service = LLMService(api_key=None)
    finally:
        if backup is not None:
            os.environ["OPENAI_API_KEY"] = backup
    return service


class TestAssessConfidence:
    def test_returns_unavailable_when_no_key(self, llm_unavailable):
        assert llm_unavailable.assess_confidence([{"score": 0.9}]) == "unavailable"

    def test_returns_low_when_no_results(self, llm):
        assert llm.assess_confidence([]) == "low"

    def test_returns_low_when_below_threshold(self, llm):
        results = [{"score": 0.3}, {"score": 0.5}]
        assert llm.assess_confidence(results) == "low"

    def test_returns_high_when_above_threshold(self, llm):
        results = [{"score": 0.3}, {"score": 0.8}]
        assert llm.assess_confidence(results) == "high"

    def test_uses_max_score_across_results(self, llm):
        results = [{"score": 0.1}, {"score": 0.2}, {"score": 0.7}]
        assert llm.assess_confidence(results) == "high"


class TestPreflightCheck:
    def test_returns_message_when_unavailable(self, llm_unavailable):
        result = llm_unavailable._preflight_check([{"score": 0.9}])
        assert result is not None
        assert result["confidence"] == "unavailable"

    def test_returns_message_when_no_results(self, llm):
        result = llm._preflight_check([])
        assert result is not None
        assert result["confidence"] == "low"

    def test_returns_message_when_below_threshold(self, llm):
        result = llm._preflight_check([{"score": 0.3}])
        assert result is not None
        assert result["confidence"] == "low"

    def test_returns_none_when_all_checks_pass(self, llm):
        result = llm._preflight_check([{"score": 0.9}])
        assert result is None


class TestTrimHistory:
    def test_empty_history_returns_empty(self, llm):
        assert llm._trim_history(None) == []
        assert llm._trim_history([]) == []

    def test_filters_invalid_roles(self, llm):
        history = [
            {"role": "system", "content": "無視"},
            {"role": "user", "content": "質問1"},
            {"role": "tool", "content": "無視"},
            {"role": "assistant", "content": "回答1"},
        ]
        trimmed = llm._trim_history(history)
        assert len(trimmed) == 2
        assert trimmed[0]["role"] == "user"
        assert trimmed[1]["role"] == "assistant"

    def test_drops_empty_content(self, llm):
        history = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "有効"},
        ]
        assert len(llm._trim_history(history)) == 1

    def test_limits_to_max_messages(self, llm):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
            for i in range(20)
        ]
        trimmed = llm._trim_history(history)
        assert len(trimmed) == LLMService._MAX_HISTORY_MESSAGES
        assert trimmed[-1]["content"] == "msg19"


class TestExtractSources:
    def test_returns_top_k(self, llm):
        results = [
            {"doc_id": f"doc_{i}", "score": 0.9 - i * 0.1, "symptom": f"症状{i}"}
            for i in range(5)
        ]
        sources = llm.extract_sources(results, top_k=3)
        assert len(sources) == 3

    def test_builds_title_from_symptom(self, llm):
        results = [{"doc_id": "d1", "score": 0.9, "symptom": "モーターから異音"}]
        sources = llm.extract_sources(results)
        assert sources[0]["title"] == "モーターから異音"

    def test_falls_back_to_doc_id(self, llm):
        results = [{"doc_id": "d1", "score": 0.9}]
        sources = llm.extract_sources(results)
        assert sources[0]["title"] == "d1"

    def test_score_is_normalized(self, llm):
        results = [{"doc_id": "d1", "score": 0.7, "rerank_score": 2.0}]
        sources = llm.extract_sources(results)
        assert 0.0 <= sources[0]["score"] <= 1.0


class TestBuildStructuredContext:
    def test_empty_results(self, llm):
        assert "該当記録なし" in llm._build_structured_context([])

    def test_truncates_long_text(self, llm):
        long_text = "あ" * 1000
        ctx = llm._build_structured_context([{
            "doc_id": "d1",
            "score": 0.9,
            "text": long_text,
        }])
        assert "…" in ctx
        assert len(ctx) < len(long_text)

    def test_includes_equipment_hierarchy(self, llm):
        ctx = llm._build_structured_context([{
            "doc_id": "d1",
            "score": 0.9,
            "text": "本文",
            "equipment1": "センサー",
            "equipment2": "圧力",
            "equipment3": "PT-1",
        }])
        assert "センサー" in ctx
        assert "圧力" in ctx
        assert "PT-1" in ctx
        assert ">" in ctx


class TestHumanizeError:
    def test_quota_error(self):
        msg = LLMService._humanize_error("429 quota exceeded")
        assert "利用制限" in msg

    def test_unauthorized(self):
        msg = LLMService._humanize_error("401 Unauthorized")
        assert "キー" in msg

    def test_timeout(self):
        msg = LLMService._humanize_error("Request timeout")
        assert "タイムアウト" in msg

    def test_unknown_error_includes_detail(self):
        msg = LLMService._humanize_error("Something unexpected")
        assert "Something unexpected" in msg
