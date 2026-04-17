"""Request ID ミドルウェアと簡易 Prompt Injection 検知。"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """X-Request-ID をリクエストに付与してログに載せる。

    クライアント由来のヘッダがあればそれを利用し、無ければ uuid4 を発行する。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


# 完全にブロックするのではなく、怪しい入力を検知してログに残すための監視用パターン。
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above)\s+(instructions?|rules?)", re.I),
    re.compile(r"(これまでの|以前の|今までの)\s*(指示|ルール|命令).*?(無視|忘れて|破棄)", re.I),
    re.compile(r"(あなたは|今から).{0,30}(になって|として振る舞|role\s*play)", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"jailbreak", re.I),
]


def detect_injection(text: str) -> Optional[str]:
    """疑わしいパターンがあれば最初にマッチしたものを返す。"""
    if not text:
        return None
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None
