"""
フィードバック集計スクリプト

`data/feedback/feedback.jsonl` に蓄積されたユーザー評価を集計し、
- 低評価ドキュメントの抽出
- モード別（検索/AI）満足度
- ファインチューニング用データセットの生成
を行う。

使い方:
    python tools/analyze_feedback.py \\
        --input data/feedback/feedback.jsonl \\
        --output-training data/feedback/training_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger("feedback")


def load_feedback(path: Path) -> List[Dict[str, Any]]:
    """JSONL フィードバックを読み込み"""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        logger.warning("Feedback file not found: %s", path)
        return records

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed line")
    return records


def summarize(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """基本統計を集計"""
    records = list(records)
    total = len(records)
    if total == 0:
        return {"total": 0}

    helpful_count = sum(1 for r in records if r.get("helpful"))
    rating_hist = Counter(r.get("rating", 0) for r in records)
    mode_hist = Counter(r.get("mode", "unknown") for r in records)

    ratings = [r.get("rating", 0) for r in records if isinstance(r.get("rating"), int)]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    return {
        "total": total,
        "helpful_count": helpful_count,
        "helpful_rate": helpful_count / total,
        "average_rating": round(avg_rating, 2),
        "rating_distribution": dict(sorted(rating_hist.items())),
        "mode_distribution": dict(mode_hist),
    }


def extract_low_rated_docs(
    records: Iterable[Dict[str, Any]],
    threshold: int = 2,
) -> List[Dict[str, Any]]:
    """
    低評価（rating <= threshold or helpful=False）のドキュメントを集約

    同じ doc_id に複数件寄せられている場合は件数・コメント一覧を束ねる。
    """
    aggregated: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "doc_id": None,
            "count": 0,
            "ratings": [],
            "comments": [],
            "queries": [],
        }
    )

    for r in records:
        is_negative = (
            r.get("helpful") is False or (r.get("rating") or 5) <= threshold
        )
        if not is_negative:
            continue
        doc_id = r.get("doc_id")
        if not doc_id:
            continue
        bucket = aggregated[doc_id]
        bucket["doc_id"] = doc_id
        bucket["count"] += 1
        if isinstance(r.get("rating"), int):
            bucket["ratings"].append(r["rating"])
        if r.get("comment"):
            bucket["comments"].append(r["comment"])
        if r.get("query"):
            bucket["queries"].append(r["query"])

    return sorted(aggregated.values(), key=lambda x: -x["count"])


def build_training_pairs(
    records: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    ファインチューニング用の (query, doc_id, label) ペアを生成

    label:
        1.0 = helpful=True (ポジティブサンプル)
        0.0 = helpful=False (ハードネガティブ)
    """
    pairs: List[Dict[str, Any]] = []
    for r in records:
        query = r.get("query")
        doc_id = r.get("doc_id")
        if not (query and doc_id):
            continue
        pairs.append({
            "query": query,
            "doc_id": doc_id,
            "label": 1.0 if r.get("helpful") else 0.0,
            "rating": r.get("rating"),
            "mode": r.get("mode", "unknown"),
            "saved_at": r.get("saved_at"),
        })
    return pairs


def pretty_print(summary: Dict[str, Any], low_rated: List[Dict[str, Any]]) -> None:
    """CLI 向けの見やすいレポート出力"""
    print("\n" + "=" * 64)
    print(" フィードバック分析レポート")
    print("=" * 64)
    if summary["total"] == 0:
        print("  フィードバックがまだ蓄積されていません。")
        print("=" * 64)
        return

    print(f"  総件数          : {summary['total']}")
    print(
        f"  役に立った件数  : {summary['helpful_count']}"
        f"  ({summary['helpful_rate']:.1%})"
    )
    print(f"  平均評価        : {summary['average_rating']} / 5.0")
    print(f"  評価分布        : {summary['rating_distribution']}")
    print(f"  モード内訳      : {summary['mode_distribution']}")

    if low_rated:
        print("\n  低評価ドキュメント TOP 5:")
        for entry in low_rated[:5]:
            avg = (
                sum(entry["ratings"]) / len(entry["ratings"])
                if entry["ratings"] else 0.0
            )
            print(
                f"    - {entry['doc_id']}: "
                f"{entry['count']} 件 / 平均 {avg:.1f}"
            )
    print("=" * 64 + "\n")


def main():
    parser = argparse.ArgumentParser(description="フィードバック分析")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/feedback/feedback.jsonl"),
    )
    parser.add_argument(
        "--output-training",
        type=Path,
        default=None,
        help="ファインチューニング用ペアの出力先 JSONL",
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=None,
        help="集計結果 JSON の出力先",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="低評価閾値（rating <= この値 or helpful=False）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    records = load_feedback(args.input)
    summary = summarize(records)
    low_rated = extract_low_rated_docs(records, threshold=args.threshold)
    pretty_print(summary, low_rated)

    if args.output_summary:
        args.output_summary.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_summary, "w", encoding="utf-8") as f:
            json.dump(
                {"summary": summary, "low_rated_docs": low_rated},
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info("Summary saved: %s", args.output_summary)

    if args.output_training:
        pairs = build_training_pairs(records)
        args.output_training.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_training, "w", encoding="utf-8") as f:
            for p in pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        logger.info("Training pairs saved: %d rows → %s", len(pairs), args.output_training)


if __name__ == "__main__":
    main()
