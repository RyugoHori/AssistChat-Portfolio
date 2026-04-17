"""フィードバック受付エンドポイント。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from ..api.feedback_store import FeedbackStore, get_default_store
from ..api.models import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    """フィードバックを JSONL に追記する。

    蓄積されたデータは `tools/analyze_feedback.py` で集計し、
    Re-ranker 学習用の正解ペア抽出などに使う想定。
    """
    store: FeedbackStore = get_default_store()
    payload = store.append(feedback.model_dump())
    return FeedbackResponse(
        success=True,
        message="フィードバックを受け付けました。改善に活用させていただきます。",
        saved_at=datetime.fromisoformat(payload["saved_at"].rstrip("Z")),
    )
