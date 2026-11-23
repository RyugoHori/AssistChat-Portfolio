"""
評価Bの質問と正解（backtest.csv）と、目で確かめるためのシート（spotcheck.csv）を作る。
検索エンジンは使わず、デモデータのCSVだけから作る
"""

import argparse
import calendar
import csv
import random
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

EVAL_DIR = Path(__file__).resolve().parent
OTHER_CATEGORY = "その他"

BACKTEST_COLUMNS = [
    "query_id",
    "query",
    "query_date",
    "query_doc_id",
    "equipment2",
    "cause_category",
    "relevant_doc_ids",
    "n_relevant",
]
SPOTCHECK_COLUMNS = [
    "query_id",
    "query_symptom",
    "query_root_cause",
    "relevant_doc_id",
    "relevant_symptom",
    "relevant_root_cause",
    "ok",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def months_before(day: date, months: int) -> date:
    """months か月前の同じ日。その月にない日（3/31の1か月前など）は月末にそろえる。"""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def build_items(records: List[Dict[str, str]], months: int) -> Tuple[List[Dict[str, Any]], Counter]:
    """最新日付から months か月以内の記録を質問にし、同じ設備種別・同じ原因分類の過去の記録を正解にする。"""
    # 境目の日は含めない（最新が2025-12-31で12か月なら、2025-01-01〜2025-12-31が質問になる）
    start = months_before(max(date.fromisoformat(r["date"]) for r in records), months).isoformat()
    items: List[Dict[str, Any]] = []
    excluded: Counter = Counter()
    for query in records:
        if query["date"] <= start:
            continue
        # 「その他」は原因が分からないまま入力された記録で、同じ原因の過去の記録を決められない
        if query["cause_category"] == OTHER_CATEGORY:
            excluded["その他"] += 1
            continue
        # 評価では検索の後に「質問より前の日付」で絞り込むので、正解も同じ条件にする。
        # 同じ日の記録を正解にすると、絞り込みで必ず消えて引けない正解になる（質問自身もこれで除かれる）
        relevant = [
            r["doc_id"]
            for r in records
            if r["date"] < query["date"]
            and r["equipment2"] == query["equipment2"]
            and r["cause_category"] == query["cause_category"]
        ]
        if not relevant:
            excluded["正解0件"] += 1
            continue
        items.append(
            {
                "query_id": f"B-{query['doc_id']}",
                "query": query["symptom"],
                "query_date": query["date"],
                "query_doc_id": query["doc_id"],
                "equipment2": query["equipment2"],
                "cause_category": query["cause_category"],
                "relevant_doc_ids": ";".join(relevant),
                "n_relevant": len(relevant),
            }
        )
    return items, excluded


def pick_spotcheck(
    items: List[Dict[str, Any]], records: List[Dict[str, str]], n: int, seed: int
) -> List[Dict[str, str]]:
    """質問と正解の組から n 組を選ぶ。自動で付けた正解が、同じ原因・同じ処置になっているかを目で確かめるため。"""
    by_id = {r["doc_id"]: r for r in records}
    pairs = [(item, doc_id) for item in items for doc_id in item["relevant_doc_ids"].split(";")]
    picked = random.Random(seed).sample(pairs, n)
    # 同じ質問の組が並ぶほうが確かめやすいので、選んだ後で並べ直す
    picked.sort(key=lambda pair: (pair[0]["query_id"], pair[1]))
    rows = []
    for item, doc_id in picked:
        query, relevant = by_id[item["query_doc_id"]], by_id[doc_id]
        rows.append(
            {
                "query_id": item["query_id"],
                "query_symptom": query["symptom"],
                "query_root_cause": query["root_cause"],
                "relevant_doc_id": doc_id,
                "relevant_symptom": relevant["symptom"],
                "relevant_root_cause": relevant["root_cause"],
                "ok": "",
            }
        )
    return rows


def spotcheck_is_filled(path: Path) -> bool:
    return path.exists() and any(row["ok"].strip() for row in read_csv(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="評価Bの質問と正解、目視確認用のシートを作る")
    parser.add_argument("--input", type=Path, default=EVAL_DIR.parents[1] / "data" / "demo" / "demo_logs.csv")
    parser.add_argument("--months", type=int, default=12, help="最新日付から何か月分の記録を質問にするか")
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "backtest.csv")
    parser.add_argument("--spotcheck", type=Path, default=EVAL_DIR / "spotcheck.csv")
    parser.add_argument("--spot-n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="記入済みの spotcheck.csv も上書きする")
    args = parser.parse_args()

    # backtest.csv だけ作り直すと、確認済みの組と正解の一覧が食い違うので、どちらも書かずに止める
    if spotcheck_is_filled(args.spotcheck) and not args.force:
        sys.exit(
            f"{args.spotcheck} の ok 列に記入済みの行があるため、何も書かずに止めました。作り直すときは --force を付けてください。"
        )

    records = read_csv(args.input)
    items, excluded = build_items(records, args.months)
    spotcheck = pick_spotcheck(items, records, args.spot_n, args.seed)
    write_csv(args.output, BACKTEST_COLUMNS, items)
    write_csv(args.spotcheck, SPOTCHECK_COLUMNS, spotcheck)

    print(
        f"質問数: {len(items)}（最新日付から{args.months}か月以内の記録 {len(items) + sum(excluded.values())}件のうち）"
    )
    print(f"除外: その他 {excluded['その他']}件、正解0件 {excluded['正解0件']}件")
    print(f"正解数の中央値: {statistics.median(item['n_relevant'] for item in items)}")
    print(f"目視確認の組: {len(spotcheck)}（保存先: {args.output}、{args.spotcheck}）")


if __name__ == "__main__":
    main()
