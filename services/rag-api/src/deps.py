"""Router 間で共有するヘルパ。"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any, Dict, List, Optional

from fastapi import Request

logger = logging.getLogger(__name__)


async def run_async_search(
    request: Request,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
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
        partial(searcher.search, query=query, filters=filters),
    )
