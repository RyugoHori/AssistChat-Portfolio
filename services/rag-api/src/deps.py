"""Router 間で共有するヘルパ。"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import partial
from typing import Any, Dict, List, Optional

from fastapi import Request

logger = logging.getLogger(__name__)

# 検索で使う DB のカーソルと、埋め込み・並べ替えのモデルのトークナイザーは全リクエストで共有していて、
# どちらも別々のスレッドから同時には使えない。検索は 1 本ずつ通す（1 回 0.3 秒ほどなので待ちは短い）。
_search_lock = threading.Lock()


def _search_one_at_a_time(searcher, **kwargs):
    with _search_lock:
        return searcher.search(**kwargs)


async def run_async_search(
    request: Request,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """CPU バウンドな検索を別スレッドで実行する。

    イベントループを詰まらせないよう `run_in_executor` に委譲する。
    """
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        logger.error("searcher not initialized")
        return []

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(_search_one_at_a_time, searcher, query=query, filters=filters, top_k=top_k),
    )
