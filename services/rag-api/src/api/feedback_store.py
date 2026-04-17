"""フィードバック永続化。JSONL 追記でスキーマ進化と並列書き込みに耐える形にする。"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# プロセス内でシングルライター化するための flush ロック。
_lock = threading.Lock()


class FeedbackStore:
    """フィードバックを JSONL に追記する。"""

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("feedback store: %s", self.storage_path)

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """レコードを 1 行追記し、タイムスタンプ付きの最終 payload を返す。"""
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
            "feedback saved: doc_id=%s helpful=%s rating=%d",
            payload.get("doc_id"),
            payload.get("helpful"),
            payload.get("rating", 0),
        )
        return payload

    def iter_records(self) -> Iterator[Dict[str, Any]]:
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
                        logger.warning("skipping malformed feedback line")

        return _gen()

    def count(self) -> int:
        return sum(1 for _ in self.iter_records())


_default_store: Optional[FeedbackStore] = None


def get_default_store(storage_path: Optional[Path] = None) -> FeedbackStore:
    """プロセス共有のデフォルトストア。`FEEDBACK_STORAGE_PATH` で保存先上書き可。"""
    global _default_store
    if _default_store is not None:
        return _default_store

    path = storage_path or Path(
        os.environ.get("FEEDBACK_STORAGE_PATH", "/app/data/feedback/feedback.jsonl")
    )
    _default_store = FeedbackStore(path)
    return _default_store
