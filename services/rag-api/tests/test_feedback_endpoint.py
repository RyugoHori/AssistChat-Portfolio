"""
/api/feedback エンドポイントのテスト

JSONL 永続化とバリデーションを検証する。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_feedback_path(tmp_path, monkeypatch):
    """
    テスト用に JSONL の保存先を tmp_path に差し替える

    `get_default_store` のシングルトンキャッシュもリセットする。
    """
    from src.api import feedback_store

    target = tmp_path / "feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_STORAGE_PATH", str(target))
    monkeypatch.setattr(feedback_store, "_default_store", None)
    return target


class TestFeedbackEndpoint:
    def test_accepts_valid_payload(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/feedback",
            json={
                "doc_id": "doc_1",
                "rating": 5,
                "helpful": True,
                "comment": "ばっちり役に立ちました",
                "query": "モーター異音",
                "mode": "search",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "saved_at" in body

        # JSONL に 1 行追記されていること
        assert tmp_feedback_path.exists()
        lines = tmp_feedback_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["doc_id"] == "doc_1"
        assert record["rating"] == 5
        assert record["helpful"] is True
        assert record["comment"] == "ばっちり役に立ちました"

    def test_rating_validation_lower_bound(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/feedback",
            json={"doc_id": "d", "rating": 0, "helpful": False},
        )
        assert resp.status_code == 422

    def test_rating_validation_upper_bound(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/feedback",
            json={"doc_id": "d", "rating": 6, "helpful": False},
        )
        assert resp.status_code == 422

    def test_missing_required_fields(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/feedback",
            json={"comment": "doc_id と rating が無い"},
        )
        assert resp.status_code == 422

    def test_multiple_submissions_accumulate(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        for i in range(3):
            resp = client.post(
                "/api/feedback",
                json={
                    "doc_id": f"doc_{i}",
                    "rating": i + 1,
                    "helpful": i % 2 == 0,
                    "mode": "chat",
                },
            )
            assert resp.status_code == 200

        lines = tmp_feedback_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3

    def test_invalid_mode_rejected(self, app_with_fakes, tmp_feedback_path):
        client = TestClient(app_with_fakes)
        resp = client.post(
            "/api/feedback",
            json={
                "doc_id": "d",
                "rating": 3,
                "helpful": True,
                "mode": "unknown_mode",
            },
        )
        assert resp.status_code == 422
