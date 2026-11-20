"""利用ログの記録を確かめる。保存先は conftest.py の usage_log_dir で一時フォルダに向けている。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_search_returns_search_id_and_logs(app_with_fakes, usage_log_dir):
    client = TestClient(app_with_fakes)
    resp = client.post("/api/search", json={"query": "異音"})
    assert resp.status_code == 200
    search_id = resp.json()["searchId"]
    assert len(search_id) == 32

    lines = _read_lines(usage_log_dir / "search_log.jsonl")
    assert len(lines) == 1
    assert lines[0]["search_id"] == search_id
    assert lines[0]["query"] == "異音"
    assert lines[0]["filters"] is None
    assert lines[0]["doc_ids"] == ["doc_1"]
    assert isinstance(lines[0]["processing_ms"], int)
    assert lines[0]["saved_at"].endswith("Z")


def test_open_log_only_with_search_id(app_with_fakes, usage_log_dir):
    client = TestClient(app_with_fakes)
    open_log = usage_log_dir / "open_log.jsonl"

    assert client.get("/api/docs/doc_1").status_code == 200
    assert _read_lines(open_log) == []

    resp = client.get("/api/docs/doc_1", params={"search_id": "abc", "rank": 2})
    assert resp.status_code == 200
    lines = _read_lines(open_log)
    assert len(lines) == 1
    assert (lines[0]["search_id"], lines[0]["doc_id"], lines[0]["rank"]) == ("abc", "doc_1", 2)


def test_feedback_accepts_search_id_and_rank(app_with_fakes, tmp_path, monkeypatch):
    from src.api import feedback_store

    target = tmp_path / "feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_STORAGE_PATH", str(target))
    monkeypatch.setattr(feedback_store, "_default_store", None)
    client = TestClient(app_with_fakes)

    resp = client.post(
        "/api/feedback",
        json={
            "doc_id": "doc_1",
            "rating": 2,
            "helpful": False,
            "query": "異音",
            "mode": "search",
            "search_id": "abc",
            "rank": 3,
        },
    )
    assert resp.status_code == 200
    record = _read_lines(target)[0]
    assert (record["search_id"], record["rank"]) == ("abc", 3)

    # 順位は1始まり
    resp = client.post(
        "/api/feedback",
        json={"doc_id": "doc_1", "rating": 2, "helpful": False, "search_id": "abc", "rank": 0},
    )
    assert resp.status_code == 422


def test_search_succeeds_when_log_write_fails(app_with_fakes, tmp_path, monkeypatch):
    # 保存先にファイルを指定して、ディレクトリを作れないようにする
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("USAGE_LOG_DIR", str(blocker))

    client = TestClient(app_with_fakes)
    resp = client.post("/api/search", json={"query": "異音"})
    assert resp.status_code == 200
    assert resp.json()["searchId"]
