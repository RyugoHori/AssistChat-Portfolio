"""
検索が上位5件に似た記録を出せるかを、4つの方式で測る。
指標はすべて上位5件、文書単位で数える。

このスクリプトが測るのは公開デモ（data/demo）。会社の保全記録の結果は docs/EVALUATION.md にまとめてある。
"""

import argparse
import csv
import hashlib
import json
import logging
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from make_pool import COLUMNS as JUDGE_COLUMNS
from make_pool import RECORD_FIELDS

logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parent
QUERIES_CSV = EVAL_DIR / "queries.csv"
LABELS_CSV = EVAL_DIR / "labels.csv"
BACKTEST_CSV = EVAL_DIR / "backtest.csv"
SPOTCHECK_CSV = EVAL_DIR / "spotcheck.csv"
RESULTS_DIR = EVAL_DIR / "results"
DATA_CSV = EVAL_DIR.parents[1] / "data" / "demo" / "demo_logs.csv"
INDEX_DIR = EVAL_DIR.parents[1] / "data" / "indices"
DATASET_NAME = "公開用ダミーデータ"
SET_NAMES = {"a": "評価A", "b": "評価B"}

# 画面には10件出るが、利用者は上から数件しか見ないので、すべて上位5件で数える
K = 5
MODES = ("dense", "sparse", "hybrid", "hybrid_rerank")
# 評価Bは未来の記録を検索の後で除くので、多めに取ってから5件に絞る
BACKTEST_FETCH = 10
SearchFn = Callable[[str, str, int], List[Dict[str, Any]]]  # (query, mode, top_k) -> 検索結果


def _doc_id(result: Dict[str, Any]) -> str:
    return result.get("doc_id") or result["metadata"]["doc_id"]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_doc_ids(results: List[Dict[str, Any]]) -> List[str]:
    """検索結果（チャンク単位）を文書単位にする。同じ記録が複数のチャンクで出たら、最初の順位だけを残す。"""
    return list(dict.fromkeys(_doc_id(result) for result in results))


def first_relevant_rank(doc_ids: List[str], relevant: Set[str], k: int = K) -> Optional[int]:
    """上位k件で最初に正解が出た順位（1始まり）。それより下は見つからなかった扱い。"""
    for rank, doc_id in enumerate(doc_ids[:k], start=1):
        if doc_id in relevant:
            return rank
    return None


def hit_rate(ranks: List[Optional[int]]) -> float:
    return sum(rank is not None for rank in ranks) / len(ranks)


def mrr(ranks: List[Optional[int]]) -> float:
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)


def win_tie_loss(ranks_a: List[Optional[int]], ranks_b: List[Optional[int]]) -> Dict[str, int]:
    """質問ごとに最初の正解の順位を比べる。平均の差が一部の質問だけによるものでないかを見るため。"""
    result = {"win": 0, "tie": 0, "loss": 0}
    for a, b in zip(ranks_a, ranks_b, strict=True):
        # 見つからなかった質問は、5件の外（6位）として比べる。両方見つからなければ引き分け
        a = K + 1 if a is None else a
        b = K + 1 if b is None else b
        if a < b:
            result["win"] += 1
        elif a > b:
            result["loss"] += 1
        else:
            result["tie"] += 1
    return result


def count_unjudged(doc_ids: List[str], judged: Set[str], k: int = K) -> int:
    """上位k件のうち、labels.csvに行がない記録の数。未判定は不正解として数えるので、出たら追加で判定する。"""
    return sum(doc_id not in judged for doc_id in doc_ids[:k])


def load_set_a(queries_csv: Path, labels_csv: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """評価Aの質問と正解を読む。正解が1件もない質問は、集計から除く質問として query_id も返す。"""
    relevant: Dict[str, Set[str]] = {}
    judged: Dict[str, Set[str]] = {}
    for row in _read_csv(labels_csv):
        query_id, doc_id, value = row["query_id"], row["doc_id"], row["relevant"].strip()
        # 「一度付けた判定は変えず、足すだけ」を守るため、空欄や同じ組の2行目を黙って読み流さずに止める
        if value not in ("0", "1"):
            raise ValueError(f"labels.csv の relevant が 1／0 以外（空欄を含む）です: {query_id} {doc_id} {value!r}")
        if doc_id in judged.setdefault(query_id, set()):
            raise ValueError(f"labels.csv に同じ質問と記録の行が2つ以上あります: {query_id} {doc_id}")
        judged[query_id].add(doc_id)
        if value == "1":
            relevant.setdefault(query_id, set()).add(doc_id)

    items: List[Dict[str, Any]] = []
    excluded: List[str] = []
    for row in _read_csv(queries_csv):
        query_id = row["query_id"]
        # 正解0件の質問も検索して上位5件を残す。改修で新しい候補が出たときに、追加で判定して計算し直せるようにするため
        if query_id not in relevant:
            excluded.append(query_id)
        items.append(
            {
                "query_id": query_id,
                "query": row["query"],
                "type": row["type"],
                "relevant": relevant.get(query_id, set()),
                "judged": judged.get(query_id, set()),
            }
        )
    return items, excluded


def load_set_b(backtest_csv: Path) -> List[Dict[str, Any]]:
    return [
        {
            "query_id": row["query_id"],
            "query": row["query"],
            "query_date": row["query_date"],
            "query_doc_id": row["query_doc_id"],
            "relevant": set(row["relevant_doc_ids"].split(";")),
        }
        for row in _read_csv(backtest_csv)
    ]


def filter_for_backtest(results: List[Dict[str, Any]], before_date: str, exclude_doc_id: str) -> List[Dict[str, Any]]:
    """質問の記録より前の日付の記録だけを残す。故障が起きた時点で引けたはずの記録だけで評価するため。"""
    # 日付はYYYY-MM-DDなので、文字列のまま比べてよい
    return [
        result for result in results if result["metadata"]["date"] < before_date and _doc_id(result) != exclude_doc_id
    ]


def run_set(items: List[Dict[str, Any]], search_fn: SearchFn, mode: str, backtest: bool) -> Dict[str, Any]:
    """1つの方式で全質問を検索し、質問ごとの上位5件（文書単位）、順位、応答時間の中央値を返す。"""
    runs: Dict[str, List[str]] = {}
    ranks: List[Optional[int]] = []
    latencies: List[float] = []
    for item in items:
        start = time.perf_counter()
        results = search_fn(item["query"], mode, BACKTEST_FETCH if backtest else K)
        latencies.append((time.perf_counter() - start) * 1000)
        if backtest:
            # 絞り込みは検索の後なので、上位10件から未来の記録を除くと5件に満たないことがある
            results = filter_for_backtest(results, item["query_date"], item["query_doc_id"])
        doc_ids = to_doc_ids(results)[:K]
        runs[item["query_id"]] = doc_ids
        ranks.append(first_relevant_rank(doc_ids, item["relevant"]))
    return {"runs": runs, "ranks": ranks, "latency_ms_median": statistics.median(latencies)}


def score_runs(runs: Dict[str, Dict[str, List[str]]], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """保存した上位5件と正解から、指標・種類別・勝ち負け・未判定数を計算する。

    通常の実行と --rescore の両方で使い、計算の仕方を1か所にまとめる。正解0件の質問は指標に入れない。
    """
    missing = [item["query_id"] for item in items if any(item["query_id"] not in run for run in runs.values())]
    if missing:
        raise ValueError(f"上位5件が保存されていない質問があります。検索からやり直してください: {', '.join(missing)}")
    items = [item for item in items if item["relevant"]]

    # 評価Bの質問には種類と判定済みの一覧がないので、種類別と未判定数は評価Aだけで出す
    is_set_a = "judged" in items[0]
    ranks_by_mode: Dict[str, List[Optional[int]]] = {}
    modes: Dict[str, Dict[str, Any]] = {}
    for mode, run in runs.items():
        ranks = [first_relevant_rank(run[item["query_id"]], item["relevant"]) for item in items]
        ranks_by_mode[mode] = ranks
        scores: Dict[str, Any] = {"hit5": round(hit_rate(ranks), 3), "mrr5": round(mrr(ranks), 3)}
        if is_set_a:
            scores["unjudged5"] = sum(count_unjudged(run[item["query_id"]], item["judged"]) for item in items)
            by_type: Dict[str, Dict[str, Any]] = {}
            for query_type in dict.fromkeys(item["type"] for item in items):
                type_ranks = [rank for item, rank in zip(items, ranks) if item["type"] == query_type]
                by_type[query_type] = {"n": len(type_ranks), "hit5": round(hit_rate(type_ranks), 3)}
            scores["by_type"] = by_type
        modes[mode] = scores

    comparisons: Dict[str, Dict[str, int]] = {}
    if "hybrid_rerank" in ranks_by_mode:
        for mode in MODES:
            if mode != "hybrid_rerank" and mode in ranks_by_mode:
                comparisons[f"hybrid_rerank_vs_{mode}"] = win_tie_loss(
                    ranks_by_mode["hybrid_rerank"], ranks_by_mode[mode]
                )
    return {"modes": modes, "comparisons": comparisons}


def dataset_meta(path: Path) -> Dict[str, Any]:
    """データの件数とハッシュ。別のデータで測った結果を取り違えて比べないよう、結果ファイルに残す。"""
    return {
        "name": DATASET_NAME,
        "records": len(_read_csv(path)),
        "sha256_12": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
    }


def spotcheck_meta(path: Path) -> Optional[Dict[str, int]]:
    """評価Bの自動の正解のうち、目で確かめた組の数と、正しかった組の数。ok が未記入なら None。"""
    if not path.exists():
        return None
    filled = [row["ok"].strip() for row in _read_csv(path) if row["ok"].strip()]
    if not filled:
        return None
    return {"checked": len(filled), "ok": filled.count("1")}


def load_sets(
    wanted: List[str], version: str, rescoring: bool
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """今の正解ファイルから評価A・Bの質問を読み、版と問題数（eval_set）をまとめる。"""
    items_by_set: Dict[str, List[Dict[str, Any]]] = {}
    eval_set: Dict[str, Any] = {
        "version": version,
        "a_queries": None,
        "a_excluded": None,
        "a_judged_rows": None,
        "b_queries": None,
    }
    if "a" in wanted:
        judged_rows = len(_read_csv(LABELS_CSV)) if LABELS_CSV.exists() else 0
        if judged_rows:
            items, excluded = load_set_a(QUERIES_CSV, LABELS_CSV)
            items_by_set["a"] = items
            # 判定を足したのに版を上げ忘れても、行数の違いで気づけるようにする
            eval_set.update(a_queries=len(items) - len(excluded), a_excluded=excluded, a_judged_rows=judged_rows)
        elif rescoring:
            sys.exit(f"{LABELS_CSV} がない、または空のため、評価Aを計算し直せません。")
        else:
            logger.warning("skip set A: labels.csv missing or empty")
    if "b" in wanted:
        items = load_set_b(BACKTEST_CSV) if BACKTEST_CSV.exists() else []
        if items:
            items_by_set["b"] = items
            eval_set["b_queries"] = len(items)
        elif rescoring:
            sys.exit(f"{BACKTEST_CSV} がない、または空のため、評価Bを計算し直せません。")
        else:
            logger.warning("skip set B: backtest.csv missing or empty")
    return items_by_set, eval_set


def search_all(
    items_by_set: Dict[str, List[Dict[str, Any]]], modes: List[str], search_fn: SearchFn
) -> Tuple[Dict[str, Dict[str, Dict[str, List[str]]]], Dict[str, Dict[str, float]]]:
    """評価ごと・方式ごとに全質問を検索し、上位5件（runs）と応答時間の中央値を返す。"""
    # 初回の検索はモデルや索引の読み込みで遅くなる。応答時間に含めないよう、方式ごとに1回だけ空打ちする
    first_query = next(iter(items_by_set.values()))[0]["query"]
    for mode in modes:
        search_fn(first_query, mode, K)

    runs_by_set: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    latencies_by_set: Dict[str, Dict[str, float]] = {}
    for set_name, items in items_by_set.items():
        runs_by_set[set_name], latencies_by_set[set_name] = {}, {}
        for mode in modes:
            print(f"{SET_NAMES[set_name]} {mode}: {len(items)}問を検索中", flush=True)
            result = run_set(items, search_fn, mode, backtest=set_name == "b")
            runs_by_set[set_name][mode] = result["runs"]
            latencies_by_set[set_name][mode] = result["latency_ms_median"]
            print(f"  完了（応答時間の中央値 {result['latency_ms_median']:.0f} ms）", flush=True)
    return runs_by_set, latencies_by_set


def build_result(
    meta: Dict[str, Any],
    items_by_set: Dict[str, List[Dict[str, Any]]],
    runs_by_set: Dict[str, Dict[str, Dict[str, List[str]]]],
    latencies_by_set: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"meta": meta}
    for set_name in ("a", "b"):
        if set_name not in items_by_set:
            result[set_name] = {"modes": {}, "comparisons": {}, "runs": {}}
            continue
        scored = score_runs(runs_by_set[set_name], items_by_set[set_name])
        for mode, latency in latencies_by_set[set_name].items():
            scored["modes"][mode]["latency_ms_median"] = round(latency, 3)
        result[set_name] = {**scored, "runs": runs_by_set[set_name]}
    return result


def rescore(path: Path, version: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """保存した上位5件を、今の正解で計算し直す。検索はしないので、応答時間などは元のファイルの値を引き継ぐ。"""
    source = json.loads(path.read_text(encoding="utf-8"))
    # 別のデータで測った順位を今の正解で採点すると、順位と正解が食い違ったまま数字が出てしまう
    current = dataset_meta(DATA_CSV)["sha256_12"]
    if current != source["meta"]["dataset"]["sha256_12"]:
        sys.exit(
            f"デモデータが {path.name} を測ったときと違うため止めました"
            f"（元 {source['meta']['dataset']['sha256_12']}、今 {current}）。検索からやり直してください。"
        )
    wanted = [set_name for set_name in ("a", "b") if source[set_name]["runs"]]
    items_by_set, eval_set = load_sets(wanted, version, rescoring=True)
    meta = {
        **source["meta"],
        "label": f"{source['meta']['label']}-rescored-{version}",
        "eval_set": eval_set,
        "b_label_check": spotcheck_meta(SPOTCHECK_CSV),
        "rescored_from": path.name,
    }
    meta.pop("run_at", None)
    meta.pop("commit", None)
    runs_by_set = {set_name: source[set_name]["runs"] for set_name in wanted}
    latencies_by_set = {
        set_name: {mode: scores["latency_ms_median"] for mode, scores in source[set_name]["modes"].items()}
        for set_name in wanted
    }
    return build_result(meta, items_by_set, runs_by_set, latencies_by_set), items_by_set


def write_unjudged(
    path: Path, items: List[Dict[str, Any]], runs: Dict[str, Dict[str, List[str]]], records: Dict[str, Dict[str, str]]
) -> int:
    """上位5件に出た未判定の記録を、判定用シートと同じ列で書き出す。書いた行数を返す。"""
    rows: List[Dict[str, str]] = []
    for item in items:
        doc_ids = sorted(
            {doc_id for run in runs.values() for doc_id in run[item["query_id"]] if doc_id not in item["judged"]}
        )
        # 判定用シートと同じく、どの方式が出した記録か分からないよう、質問ごとに決まった順番で混ぜる
        random.Random(item["query_id"]).shuffle(doc_ids)
        for doc_id in doc_ids:
            rows.append(
                {
                    "query_id": item["query_id"],
                    "query": item["query"],
                    "type": item["type"],
                    "doc_id": doc_id,
                    **{key: records[doc_id][key] for key in RECORD_FIELDS},
                    "relevant": "",
                    "note": "",
                }
            )
    if rows:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=JUDGE_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def _mode_table(section: Dict[str, Any], with_unjudged: bool) -> List[str]:
    columns = ["方式", "Hit@5", "MRR@5", "応答時間の中央値（ms）"] + (["未判定数"] if with_unjudged else [])
    lines = ["| " + " | ".join(columns) + " |", "|---" * len(columns) + "|"]
    for mode, scores in section["modes"].items():
        cells = [f"`{mode}`", f"{scores['hit5']:.3f}", f"{scores['mrr5']:.3f}", f"{scores['latency_ms_median']:.0f}"]
        if with_unjudged:
            cells.append(str(scores["unjudged5"]))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def to_markdown(result: Dict[str, Any]) -> str:
    """結果ファイルの Markdown。表と、データ名・版・モデル名を書く。"""
    meta, a, b = result["meta"], result["a"], result["b"]
    eval_set, dataset = meta["eval_set"], meta["dataset"]
    check = meta["b_label_check"]
    check_text = f"{check['ok']}/{check['checked']}組が正しい" if check else "未記入"
    lines = [
        f"# 評価結果：{meta['label']}",
        "",
        f"- データ：{dataset['name']}（{dataset['records']}件、SHA-256の先頭12文字 {dataset['sha256_12']}）",
        f"- 評価セットの版：{eval_set['version']}",
        f"- 問題数：評価A {eval_set['a_queries'] or '-'}問、評価B {eval_set['b_queries'] or '-'}問",
        f"- 評価Aで除外した質問（正解0件）：{', '.join(eval_set['a_excluded'] or []) or 'なし'}",
        f"- 評価Aの判定済みの行数：{eval_set['a_judged_rows'] or '-'}",
        f"- 評価Bの正解の目視確認：{check_text}",
        f"- モデル：埋め込み {meta['models']['embedding']}、並べ替え {meta['models']['reranker']}",
    ]
    if meta["rescored_from"]:
        lines.append(f"- {meta['rescored_from']} の上位5件を計算し直した結果（応答時間は元の値）")

    if a["modes"]:
        lines += ["", f"## 評価A：方式比較（{eval_set['a_queries']}問）", "", *_mode_table(a, with_unjudged=True)]
        modes = list(a["modes"])
        lines += [
            "",
            "## 評価A：種類別 Hit@5",
            "",
            "| 種類 | 問題数 | " + " | ".join(f"`{mode}`" for mode in modes) + " |",
            "|---|---|" + "---|" * len(modes),
        ]
        for query_type, scores in a["modes"][modes[0]]["by_type"].items():
            values = " | ".join(f"{a['modes'][mode]['by_type'][query_type]['hit5']:.3f}" for mode in modes)
            lines.append(f"| {query_type} | {scores['n']} | {values} |")
    if b["modes"]:
        lines += ["", f"## 評価B：方式比較（{eval_set['b_queries']}問）", "", *_mode_table(b, with_unjudged=False)]

    pairs = list(dict.fromkeys([*a["comparisons"], *b["comparisons"]]))
    if pairs:
        lines += [
            "",
            "## 質問ごとの勝ち負け（hybrid_rerank から見て、勝ち／引き分け／負け）",
            "",
            "| 比較 | 評価A | 評価B |",
            "|---|---|---|",
        ]
        for pair in pairs:
            cells = [
                "{win}／{tie}／{loss}".format(**section["comparisons"][pair]) if pair in section["comparisons"] else "-"
                for section in (a, b)
            ]
            lines.append(f"| `{pair.replace('_vs_', '` 対 `')}` | {cells[0]} | {cells[1]} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="評価A・Bを検索方式ごとに実行し、結果を保存する")
    parser.add_argument("--label", help="結果ファイルの名前に付ける（例：baseline）")
    parser.add_argument("--sets", default="a,b")
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--eval-version", default="v1")
    parser.add_argument("--rescore", type=Path, help="検索をやり直さず、この結果ファイルの上位5件から計算し直す")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.rescore:
        # コンテナの作業場所は /app なので、results/... と書かれたらこのディレクトリから探す
        path = args.rescore if args.rescore.exists() else EVAL_DIR / args.rescore
        result, items_by_set = rescore(path, args.eval_version)
    else:
        sets = args.sets.split(",")
        modes = args.modes.split(",")
        if not args.label:
            parser.error("--label を指定してください（例：--label baseline）")
        if not set(sets) <= set(SET_NAMES) or not set(modes) <= set(MODES):
            parser.error(f"--sets は a,b、--modes は {','.join(MODES)} から選んでください")

        # モデルの読み込みに時間がかかるので、止まる条件は先に確かめる
        items_by_set, eval_set = load_sets(sets, args.eval_version, rescoring=False)
        if not items_by_set:
            sys.exit("評価できる質問がありません（labels.csv と backtest.csv を確かめてください）。")
        for set_name, items in items_by_set.items():
            excluded = eval_set["a_excluded"] if set_name == "a" else []
            suffix = f"（うち集計から除く{len(excluded)}問）" if excluded else ""
            print(f"{SET_NAMES[set_name]}: {len(items)}問{suffix}")

        from rag_core.config import settings
        from rag_core.search import HybridSearcher

        meta = {
            "label": args.label,
            "dataset": dataset_meta(DATA_CSV),
            "models": {
                "embedding": settings["embedding"]["model_name"],
                "reranker": settings["retrieval"]["reranker_model"],
            },
            "eval_set": eval_set,
            "b_label_check": spotcheck_meta(SPOTCHECK_CSV),
            "rescored_from": None,
        }
        # 設定の索引の場所は実行した場所からの相対パスで、別の場所から実行するとキーワード検索が黙って0件になる
        searcher = HybridSearcher(index_dir=str(INDEX_DIR))
        # 並べ替えモデルが読めないと、検索は並べ替えなしの結果を返す。それを並べ替えありとして記録しないよう止める
        if "hybrid_rerank" in modes and not (searcher.reranker and searcher.reranker.is_available):
            sys.exit(
                "並べ替えモデルが使えないため止めました（設定の enable_reranking とモデルの読み込みを確かめてください）。"
            )

        def search_fn(query: str, mode: str, top_k: int) -> List[Dict[str, Any]]:
            results = searcher.search(query, mode=mode, top_k=top_k)
            # 並べ替えは推論に失敗しても、並べ替えていない結果を黙って返すので、1問ごとに確かめる
            if mode == "hybrid_rerank" and results and "rerank_score" not in results[0]:
                raise RuntimeError(f"並べ替えに失敗したため止めました（ログを確かめてください）: {query}")
            return results

        runs_by_set, latencies_by_set = search_all(items_by_set, modes, search_fn)
        result = build_result(meta, items_by_set, runs_by_set, latencies_by_set)

    label = result["meta"]["label"]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"{label}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = to_markdown(result)
    json_path.with_suffix(".md").write_text(markdown, encoding="utf-8")

    print()
    print(markdown)
    print(f"保存先: {json_path}（同名の .md も）")
    if result["a"]["runs"]:
        records = {row["doc_id"]: row for row in _read_csv(DATA_CSV)}
        unjudged_path = RESULTS_DIR / f"unjudged_{label}.csv"
        n_unjudged = write_unjudged(unjudged_path, items_by_set["a"], result["a"]["runs"], records)
        if n_unjudged:
            print(
                f"未判定の記録: {n_unjudged}件（{unjudged_path}）。判定を足して版を上げ、--rescore で計算し直してください。"
            )


if __name__ == "__main__":
    main()
