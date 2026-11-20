"""検索と閲覧を JSONL に追記する。保存に失敗しても検索は止めない。"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def append_usage_log(filename: str, record: Dict[str, Any]) -> None:
    """USAGE_LOG_DIR配下のJSONLに1行追記する。保存の失敗で検索や閲覧を止めないよう、例外は出さずに警告ログだけ残す。"""
    payload = {
        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **record,
    }
    try:
        # テストで monkeypatch により差し替えられるよう、呼び出しのたびに環境変数から決める
        log_dir = Path(os.environ.get("USAGE_LOG_DIR", "/app/data/usage"))
        log_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with _lock:
            with open(log_dir / filename, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        logger.warning("usage log write failed: %s: %s", filename, e)
