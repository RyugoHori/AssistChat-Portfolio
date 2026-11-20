"""
検索ログ・閲覧ログ・フィードバックを search_id で結び付け、週ごとの件数を出す。
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
CANDIDATE_COLUMNS = ["saved_at", "search_id", "query", "reason"]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """1行1件のJSONLを読む。まだ利用がなくファイルがないときは0件として扱う。"""
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} の{n}行目がJSONとして読めません: {e}") from e
    return records


def week_of(saved_at: str) -> str:
    """UTCで保存した saved_at を日本時間に直し、ISO週（例：2026-W44）にする。"""
    # UTCのまま区切ると、日本時間の月曜0時〜9時の利用が前の週に入ってしまう
    year, week, _ = datetime.fromisoformat(saved_at).astimezone(JST).isocalendar()
    return f"{year}-W{week:02d}"


def summarize_weeks(
    searches: List[Dict[str, Any]], opens: List[Dict[str, Any]], feedback: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """週ごとに、検索数・何も開かれなかった検索の割合・開いた結果の平均順位・フィードバック数・役立ち率を出す。

    上位ほど開かれやすいので、方式の比較ではなく、週ごとの傾向を見るために使う。
    """
    # 週の変わり目をまたいで開かれた検索も「開かれた」に数えるよう、閲覧の有無は週ではなく search_id で判定する
    opened_ids = {o["search_id"] for o in opens}
    weeks: Dict[str, Dict[str, list]] = defaultdict(lambda: {"opened": [], "ranks": [], "helpful": []})
    for s in searches:
        weeks[week_of(s["saved_at"])]["opened"].append(s["search_id"] in opened_ids)
    for o in opens:
        if o.get("rank") is not None:
            weeks[week_of(o["saved_at"])]["ranks"].append(o["rank"])
    for fb in feedback:
        weeks[week_of(fb["saved_at"])]["helpful"].append(bool(fb["helpful"]))

    rows = []
    for week in sorted(weeks):
        opened, ranks, helpful = weeks[week]["opened"], weeks[week]["ranks"], weeks[week]["helpful"]
        rows.append(
            {
                "week": week,
                "searches": len(opened),
                "no_open_rate": opened.count(False) / len(opened) if opened else None,
                "mean_rank": sum(ranks) / len(ranks) if ranks else None,
                "feedback": len(helpful),
                "helpful_rate": helpful.count(True) / len(helpful) if helpful else None,
            }
        )
    return rows


def pick_candidates(
    searches: List[Dict[str, Any]], opens: List[Dict[str, Any]], feedback: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """「役に立たなかった」が付いた検索と、何も開かれなかった検索を、評価Aの質問候補として拾う。"""
    opened_ids = {o["search_id"] for o in opens}
    # search_id のないフィードバック（AIモードや、記録を始める前のもの）は、どの検索のものか分からないので使わない
    unhelpful_ids = {fb["search_id"] for fb in feedback if fb.get("search_id") and not fb["helpful"]}
    rows = []
    for s in searches:
        if s["search_id"] in unhelpful_ids:
            reason = "役に立たなかった"
        elif s["search_id"] not in opened_ids:
            reason = "開かれなかった"
        else:
            continue
        rows.append({"saved_at": s["saved_at"], "search_id": s["search_id"], "query": s["query"], "reason": reason})
    return rows


def _fmt(value: Optional[float], spec: str) -> str:
    return "-" if value is None else format(value, spec)


def print_table(rows: List[Dict[str, Any]]) -> None:
    print("週          検索数  未閲覧率  平均順位  FB数  役立ち率")
    for r in rows:
        print(
            f"{r['week']:<10}  {r['searches']:>6}  {_fmt(r['no_open_rate'], '.1%'):>8}  "
            f"{_fmt(r['mean_rank'], '.2f'):>8}  {r['feedback']:>4}  {_fmt(r['helpful_rate'], '.1%'):>8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="利用ログを週ごとに集計し、評価Aの質問候補を書き出す")
    parser.add_argument("--usage-dir", type=Path, default=TOOLS_DIR.parent / "data" / "usage")
    parser.add_argument("--feedback", type=Path, default=TOOLS_DIR.parent / "data" / "feedback" / "feedback.jsonl")
    parser.add_argument("--candidates", type=Path, default=TOOLS_DIR / "evaluation" / "candidates.csv")
    args = parser.parse_args()

    searches = read_jsonl(args.usage_dir / "search_log.jsonl")
    opens = read_jsonl(args.usage_dir / "open_log.jsonl")
    feedback = read_jsonl(args.feedback)
    print(f"検索 {len(searches)}件、閲覧 {len(opens)}件、フィードバック {len(feedback)}件")
    print_table(summarize_weeks(searches, opens, feedback))

    candidates = pick_candidates(searches, opens, feedback)
    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    with open(args.candidates, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_COLUMNS)
        writer.writeheader()
        writer.writerows(candidates)
    print(f"評価Aの質問候補: {len(candidates)}件（保存先: {args.candidates}）")


if __name__ == "__main__":
    main()
