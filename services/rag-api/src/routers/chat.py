"""対話式 RAG（ストリーミング）エンドポイント。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import partial
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from rag_core import LLMService, sanitize_float_values

from ..api.models import ChatRequest
from ..deps import run_async_search
from ..middleware import detect_injection

logger = logging.getLogger(__name__)
router = APIRouter()


def _ndjson_line(payload: Dict[str, Any]) -> str:
    """NDJSON 1 行。NaN/Infinity は None に置換する。"""
    return json.dumps(sanitize_float_values(payload), ensure_ascii=False) + "\n"


async def _chat_event_stream(
    request: Request,
    req: ChatRequest,
) -> AsyncIterator[str]:
    """NDJSON で stage / meta / token / done / error を順に流す。"""
    llm: LLMService = request.app.state.llm
    start_time = time.time()
    request_id = getattr(request.state, "request_id", None)

    injection_hit = detect_injection(req.query) or next(
        (detect_injection(m.content) for m in req.messages if detect_injection(m.content)),
        None,
    )
    if injection_hit:
        logger.warning(
            "prompt_injection_suspected",
            extra={
                "request_id": request_id,
                "pattern": injection_hit,
                "query_preview": req.query[:80],
            },
        )

    try:
        history = [m.model_dump() for m in req.messages]

        yield _ndjson_line({"type": "stage", "stage": "rewriting"})
        loop = asyncio.get_running_loop()
        rewritten_query = await loop.run_in_executor(
            None,
            partial(llm.rewrite_query, query=req.query, history=history),
        )

        yield _ndjson_line({"type": "stage", "stage": "searching"})
        filters_dict = req.filters.model_dump(exclude_none=True) if req.filters else None
        search_results = await run_async_search(request, rewritten_query, filters=filters_dict)

        sources = llm.extract_sources(search_results)
        confidence = llm.assess_confidence(search_results)
        yield _ndjson_line({
            "type": "meta",
            "rewritten_query": rewritten_query,
            "original_query": req.query,
            "sources": sources,
            "result_count": len(search_results),
        })

        yield _ndjson_line({"type": "stage", "stage": "generating"})
        async for token in llm.stream_answer(
            query=req.query,
            search_results=search_results,
            history=history,
        ):
            if token:
                yield _ndjson_line({"type": "token", "content": token})

        processing_time_ms = int((time.time() - start_time) * 1000)
        yield _ndjson_line({
            "type": "done",
            "confidence": confidence,
            "processingTime": processing_time_ms,
        })

    except Exception as e:
        logger.error("chat stream failed: %s", e, exc_info=True)
        yield _ndjson_line({
            "type": "error",
            "message": "回答生成中にエラーが発生しました。しばらくしてから再度お試しください。",
            "detail": str(e)[:200],
        })


@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    """応答形式: `application/x-ndjson`。1 行ごとに JSON をパースする。"""
    llm = getattr(request.app.state, "llm", None)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service not initialized. Please check server logs.",
        )

    return StreamingResponse(
        _chat_event_stream(request, req),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
