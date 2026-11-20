"""検索スコアの正規化と JSON サニタイズ。"""

from __future__ import annotations

import math
from typing import Any, Dict


def calculate_display_score(result: Dict[str, Any]) -> float:
    """rerank_score 優先で 0.0-1.0 のスコアに正規化する。

    Re-ranker のスコアは [-10, +10] 近辺の対数オッズ値を取り得るので、
    その場合は簡易的に [0, 1] にマッピングする。
    """
    is_rerank = result.get("rerank_score") is not None
    raw = result["rerank_score"] if is_rerank else result.get("score", 0.0)

    if isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)):
        return 0.0
    if raw is None:
        return 0.0

    raw = float(raw)
    # Re-ranker の値は 0〜1 に入っていても対数オッズ。ここだけ式を変えると順位と表示が逆転する。
    if not is_rerank and 0.0 <= raw <= 1.0:
        return raw

    normalized = (raw + 10.0) / 20.0
    return max(0.0, min(1.0, normalized))


def sanitize_float_values(data: Any) -> Any:
    """JSON が扱えない NaN / Infinity を None に再帰置換する。"""
    if isinstance(data, dict):
        return {k: sanitize_float_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_float_values(item) for item in data]
    if isinstance(data, float) and (math.isnan(data) or math.isinf(data)):
        return None
    return data
