"""検索を同時に実行しないことのテスト。"""

from __future__ import annotations

import asyncio
import time

from src.deps import run_async_search


class _SlowSearcher:
    def __init__(self):
        self.current = 0
        self.max_current = 0

    def search(self, query, filters=None, top_k=None):
        self.current += 1
        self.max_current = max(self.max_current, self.current)
        time.sleep(0.05)
        self.current -= 1
        return [{"query": query}]


class _Request:
    def __init__(self, searcher):
        self.app = type("App", (), {})()
        self.app.state = type("State", (), {"searcher": searcher})()


async def test_searches_run_one_at_a_time():
    searcher = _SlowSearcher()
    request = _Request(searcher)
    await asyncio.gather(*(run_async_search(request, f"q{i}") for i in range(4)))
    assert searcher.max_current == 1
