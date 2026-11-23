"""/api/chat ストリーミングの統合テスト。NDJSON のイベント順序を検証する。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _iter_ndjson(response) -> list:
    body = response.content.decode("utf-8")
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class TestChatEndpointStreaming:
    def test_returns_ndjson_media_type(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/chat", json={"query": "テスト", "messages": []})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        assert resp.headers.get("cache-control") == "no-cache, no-transform"

    def test_emits_stage_meta_token_done_in_order(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/chat", json={"query": "異音", "messages": []})
        events = _iter_ndjson(resp)

        types = [e["type"] for e in events]
        # stage が先、最後は done
        assert types[0] == "stage"
        assert types[-1] == "done"

        # meta イベントが 1 回出る
        meta_events = [e for e in events if e["type"] == "meta"]
        assert len(meta_events) == 1
        assert meta_events[0]["original_query"] == "異音"
        assert "sources" in meta_events[0]
        assert "result_count" in meta_events[0]

        # token イベントが複数出る
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) > 0
        assert all("content" in t for t in token_events)

    def test_done_event_includes_confidence(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/chat", json={"query": "異音", "messages": []})
        events = _iter_ndjson(resp)

        done = next(e for e in events if e["type"] == "done")
        assert done["confidence"] in ("high", "low", "unavailable", "unknown")
        assert isinstance(done["processingTime"], int)

    def test_rewrite_is_triggered_when_history_exists(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/chat",
            json={
                "query": "もっと詳しく",
                "messages": [
                    {"role": "user", "content": "モーター異音の原因は？"},
                    {"role": "assistant", "content": "ベアリング摩耗が考えられます"},
                ],
            },
        )
        events = _iter_ndjson(resp)
        meta = next(e for e in events if e["type"] == "meta")
        # スタブは履歴があるときだけ「（書き換え済み）」を付加する
        assert "書き換え済み" in meta["rewritten_query"]

    def test_validation_error_on_empty_query(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/chat", json={"query": "", "messages": []})
        assert resp.status_code == 422

    def test_validation_error_on_too_long_query(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/chat",
            json={"query": "あ" * 501, "messages": []},
        )
        assert resp.status_code == 422


class TestSearchEndpoint:
    def test_search_returns_results(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/search", json={"query": "異音", "k": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "total" in body
        assert "processingTime" in body

    def test_search_validation_min_length(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/search", json={"query": ""})
        assert resp.status_code == 422

    def test_k_above_10_is_rejected(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.post("/api/search", json={"query": "異音", "k": 11})
        assert resp.status_code == 422

    def test_top_k_limits_results(self, app_with_fakes, fake_searcher):
        base = fake_searcher._results[0]
        fake_searcher._results = [
            {
                **base,
                "chunk_id": f"c_{i}",
                "metadata": {**base["metadata"], "doc_id": f"doc_{i}"},
            }
            for i in range(5)
        ]
        client = TestClient(app_with_fakes)
        resp = client.post("/api/search", json={"query": "異音", "k": 3})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 3


class TestDisplayTitle:
    def test_uses_title_when_present(self):
        from src.routers.search import _display_title

        assert _display_title({"title": "見出し", "symptom": "現象"}) == "見出し"

    def test_uses_symptom_prefix_when_title_missing(self):
        from src.routers.search import _display_title

        assert _display_title({"symptom": "あ" * 50}) == "あ" * 40

    def test_falls_back_when_title_and_symptom_missing(self):
        from src.routers.search import _display_title

        assert _display_title({}) == "故障対応記録"


class TestHealthEndpoint:
    def test_health_returns_structured_response(self, app_with_fakes):
        client = TestClient(app_with_fakes)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("healthy", "degraded")
        assert "timestamp" in body
        assert body["llm_ready"] is True
