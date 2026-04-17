"""
フィードバック永続化層

JSONL ファイル追記方式を採用:
- スキーマ進化に強い（カラム増加が既存レコードを壊さない）
- 並列書き込みに安全（1 レコード = 1 行、O_APPEND）
- 可搬性が高い（本番では S3 + Athena でもそのまま扱える）

将来ファインチューニング用データセットとして BigQuery / DWH に取り込む想定。
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# プロセス内シングルライター化（マルチスレッドで崩れないよう flush をロックで保護）
_lock = threading.Lock()


class FeedbackStore:
    """
    フィードバックを JSONL に追記する永続化クラス

    FastAPI の Depends 経由で使えるように、明示的なインスタンス化を行う。
    """

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("FeedbackStore initialized: %s", self.storage_path)

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        フィードバックレコードを追記

        Returns:
            タイムスタンプ等を付与した最終レコード
        """
        payload = {
            "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            **record,
        }
        line = json.dumps(payload, ensure_ascii=False) + "\n"

        with _lock:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()

        logger.info(
            "Feedback saved: doc_id=%s helpful=%s rating=%d",
            payload.get("doc_id"),
            payload.get("helpful"),
            payload.get("rating", 0),
        )
        return payload

    def iter_records(self) -> Iterator[Dict[str, Any]]:
        """保存済みレコードを順に読み出すイテレータ"""
        if not self.storage_path.exists():
            return iter([])

        def _gen():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed feedback line")

        return _gen()

    def count(self) -> int:
        return sum(1 for _ in self.iter_records())


_default_store: Optional[FeedbackStore] = None


def get_default_store(storage_path: Optional[Path] = None) -> FeedbackStore:
    """
    プロセス共有のデフォルト FeedbackStore を返す

    環境変数 `FEEDBACK_STORAGE_PATH` で保存先を上書きできる。
    """
    global _default_store
    if _default_store is not None:
        return _default_store

    import os

    path = storage_path or Path(
        os.environ.get("FEEDBACK_STORAGE_PATH", "/app/data/feedback/feedback.jsonl")
    )
    _default_store = FeedbackStore(path)
    return _default_store
