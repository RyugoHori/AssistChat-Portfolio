"""
評価Aの判定用シート（judge_sheet.csv）を作る。
ベクトル検索とキーワード検索の上位の候補を合わせて重複を除き、方式名を隠してシャッフルする
"""

import argparse
import csv
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parent

RECORD_FIELDS = ["equipment_full", "symptom", "root_cause", "action_taken"]
COLUMNS = ["query_id", "query", "type", "doc_id", *RECORD_FIELDS, "relevant", "note"]


def read_queries(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pool_rows(query: Dict[str, str], results: List[Dict[str, Any]], seed: int) -> List[Dict[str, str]]:
    """1問分の候補を文書単位にまとめ、質問ごとに決まった順番でシャッフルする。"""
    candidates: Dict[str, Dict[str, Any]] = {}
    for result in results:
        candidates.setdefault(result["metadata"]["doc_id"], result["metadata"])
    # 検索の順位のまま並べると、上にある候補を正解と思い込みやすい。
    # どの方式が出したかも分からないよう、質問ごとのシードで順番を混ぜる（同じ入力なら同じ順番）
    doc_ids = list(candidates)
    random.Random(f"{seed}-{query['query_id']}").shuffle(doc_ids)
    return [
        {
            "query_id": query["query_id"],
            "query": query["query"],
            "type": query["type"],
            "doc_id": doc_id,
            **{key: candidates[doc_id][key] for key in RECORD_FIELDS},
            "relevant": "",
            "note": "",
        }
        for doc_id in doc_ids
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="評価Aの判定用シートを作る")
    parser.add_argument("--queries", type=Path, default=EVAL_DIR / "queries.csv")
    parser.add_argument("--output", type=Path, default=EVAL_DIR / "judge_sheet.csv")
    parser.add_argument("--depth", type=int, default=10, help="方式ごとに集める候補の数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="既にある判定用シートを上書きする")
    args = parser.parse_args()

    # モデルの読み込みに時間がかかるので、止まる条件は先に確かめる
    if args.output.exists() and not args.force:
        sys.exit(
            f"{args.output} が既にあります。記入中の判定を消さないよう、上書きしません。作り直すときは --force を付けてください。"
        )
    queries = read_queries(args.queries)
    if not queries:
        sys.exit(
            f"{args.queries} に質問がありません。質問を書いてから実行してください（列は query_id,query,type,version）。"
        )

    logging.basicConfig(level=logging.INFO)
    from rag_core.search import HybridSearcher

    # 設定の索引の場所は実行した場所からの相対パスで、別の場所から実行するとキーワード検索の候補が黙って0件になる
    searcher = HybridSearcher(index_dir=str(EVAL_DIR.parents[1] / "data" / "indices"))
    dense = searcher.dense_searcher
    # 候補を集めるときだけ、索引を使わず全件を比べる正確なベクトル検索にする。
    # 近似の取りこぼしで、改修後に上位に出てくる記録が候補から漏れないようにするため。
    # この接続の中だけの設定で、本番の検索は変わらない。search() が失敗時に rollback するので、先に確定させる
    dense.cursor.execute("SET enable_indexscan = off")
    dense.conn.commit()

    rows: List[Dict[str, str]] = []
    for query in queries:
        dense_results = searcher.search(query["query"], mode="dense", top_k=args.depth)
        sparse_results = searcher.search(query["query"], mode="sparse", top_k=args.depth)
        pooled = pool_rows(query, dense_results + sparse_results, args.seed)
        logger.info(
            "%s: dense %d, sparse %d, pool %d", query["query_id"], len(dense_results), len(sparse_results), len(pooled)
        )
        rows.extend(pooled)

    # 途中で再接続していると SET が外れ、近似の検索で候補を集めたことになるので、書き出す前に確かめる
    dense.cursor.execute("SHOW enable_indexscan")
    if dense.cursor.fetchone()["enable_indexscan"] != "off":
        sys.exit(
            "途中でDBに再接続したため、全件を比べるベクトル検索になっていませんでした。判定用シートは書いていません。もう一度実行してください。"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"質問数: {len(queries)}")
    print(f"候補の総数: {len(rows)}")
    print(f"1問あたりの平均候補数: {len(rows) / len(queries):.1f}")
    print(f"保存先: {args.output}")
    print("relevant 列に 1／0 を記入し、labels.csv という名前で保存してください。")


if __name__ == "__main__":
    main()
