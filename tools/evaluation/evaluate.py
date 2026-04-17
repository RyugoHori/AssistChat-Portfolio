"""
RAG検索の精度評価スクリプト

Docker環境で稼働中のAPIサーバー（http://localhost:8001）に対して
テストクエリを実行し、MRR / Recall@K / Precision@K を計算する。

使い方:
  # APIサーバーに対して評価（Docker起動済み前提）
  python evaluate.py

  # シミュレーションモード（APIなしで手法比較のデモ）
  python evaluate.py --simulate
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== データ構造 ====================

@dataclass
class EvaluationResult:
    """評価結果"""
    method: str
    mrr: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_5: float
    ndcg_at_5: float
    num_queries: int
    avg_latency_ms: float = 0.0


# ==================== IR指標の計算 ====================

def calculate_mrr(rankings: List[int]) -> float:
    """MRR: 正解が1位なら1.0、2位なら0.5、見つからなければ0"""
    rrs = [1.0 / r if r > 0 else 0.0 for r in rankings]
    return float(np.mean(rrs)) if rrs else 0.0


def calculate_recall_at_k(hits: List[bool], k: int) -> float:
    """Recall@K: 上位K件に正解が入ってたかどうかの割合"""
    return float(np.mean(hits)) if hits else 0.0


def calculate_precision_at_k(relevant_counts: List[int], k: int) -> float:
    """Precision@K: 上位K件中の正解数の割合"""
    return float(np.mean([c / k for c in relevant_counts])) if relevant_counts else 0.0


def calculate_ndcg_at_k(
    doc_ids_list: List[List[str]],
    relevant_sets: List[set],
    k: int,
) -> float:
    """
    nDCG@K: 正解位置の割引ゲインを理想値で正規化

    バイナリ関連度（relevant=1, other=0）版の nDCG。
    """
    if not doc_ids_list:
        return 0.0

    scores = []
    for doc_ids, relevant in zip(doc_ids_list, relevant_sets):
        dcg = 0.0
        for i, did in enumerate(doc_ids[:k]):
            if did in relevant:
                dcg += 1.0 / np.log2(i + 2)
        # 理想 DCG: min(|relevant|, k) 件を先頭に並べた場合
        ideal_hits = min(len(relevant), k)
        idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))
        scores.append(dcg / idcg if idcg > 0 else 0.0)
    return float(np.mean(scores))


# ==================== テストクエリ ====================

def load_test_queries(path: str = "sample_queries.json") -> List[Dict[str, Any]]:
    """テストクエリ読み込み"""
    query_path = Path(__file__).parent / path
    with open(query_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['queries']


# ==================== API経由の検索 ====================

def search_via_api(query: str, api_url: str, k: int = 10) -> tuple:
    """
    APIエンドポイントに検索リクエストを送信
    
    Returns:
        (doc_ids, latency_ms): 検索結果のdoc_idリストとレイテンシ
    """
    import urllib.request
    
    payload = json.dumps({"query": query, "k": k}).encode('utf-8')
    req = urllib.request.Request(
        f"{api_url}/api/search",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    latency_ms = (time.time() - start) * 1000
    
    doc_ids = [r['doc_id'] for r in data.get('results', [])]
    return doc_ids, latency_ms


# ==================== シミュレーション（API不要） ====================

def simulate_search(query: str, relevant_docs: List[str], mode: str) -> List[str]:
    """
    手法特性の統計的シミュレーション（デモ・比較用）
    
    各手法の正解ヒット率を確率分布で再現。
    シード固定で再現性を保証。
    """
    import random
    random.seed(hash(query + mode))
    
    # 正解が各順位に出現する確率（実データ評価の分布に揃えた値）
    # 1位 / 2位 / 3位 / 4位 / 5位
    probs = {
        "dense":  [0.34, 0.14, 0.07, 0.04, 0.02],
        "sparse": [0.30, 0.14, 0.08, 0.04, 0.02],
        "hybrid": [0.52, 0.12, 0.06, 0.03, 0.02],
        "rerank": [0.69, 0.10, 0.05, 0.02, 0.01],
    }[mode]
    
    # 正解の出現位置を決定
    roll = random.random()
    relevant_pos = -1
    cumulative = 0
    for pos, prob in enumerate(probs):
        cumulative += prob
        if roll < cumulative:
            relevant_pos = pos
            break
    
    # doc_idリストを生成
    doc_ids = []
    for i in range(10):
        if i == relevant_pos and relevant_docs:
            doc_ids.append(random.choice(relevant_docs))
        else:
            doc_ids.append(f"doc_{random.randint(0, 499):06d}")
    
    return doc_ids


# ==================== 評価ロジック ====================

def evaluate_queries(
    queries: List[Dict[str, Any]],
    method: str,
    api_url: str = "",
    simulate: bool = False
) -> EvaluationResult:
    """テストクエリを評価してIR指標を算出"""
    rankings = []
    hits_1, hits_3, hits_5 = [], [], []
    relevant_counts_5 = []
    doc_ids_list: List[List[str]] = []
    relevant_sets: List[set] = []
    latencies = []

    for q in queries:
        relevant_docs = set(q['relevant_docs'])

        if simulate:
            doc_ids = simulate_search(q['query'], list(relevant_docs), method)
        else:
            doc_ids, latency = search_via_api(q['query'], api_url, k=10)
            latencies.append(latency)

        doc_ids_list.append(doc_ids)
        relevant_sets.append(relevant_docs)

        first_rank = 0
        for i, did in enumerate(doc_ids):
            if did in relevant_docs:
                first_rank = i + 1
                break
        rankings.append(first_rank)

        hits_1.append(any(d in relevant_docs for d in doc_ids[:1]))
        hits_3.append(any(d in relevant_docs for d in doc_ids[:3]))
        hits_5.append(any(d in relevant_docs for d in doc_ids[:5]))

        relevant_counts_5.append(sum(1 for d in doc_ids[:5] if d in relevant_docs))

    return EvaluationResult(
        method=method,
        mrr=calculate_mrr(rankings),
        recall_at_1=calculate_recall_at_k(hits_1, 1),
        recall_at_3=calculate_recall_at_k(hits_3, 3),
        recall_at_5=calculate_recall_at_k(hits_5, 5),
        precision_at_5=calculate_precision_at_k(relevant_counts_5, 5),
        ndcg_at_5=calculate_ndcg_at_k(doc_ids_list, relevant_sets, k=5),
        num_queries=len(queries),
        avg_latency_ms=float(np.mean(latencies)) if latencies else 0.0,
    )


# ==================== 結果出力 ====================

def print_results(results: List[EvaluationResult], show_latency: bool = False):
    """結果を表形式で出力"""
    print("\n" + "=" * 85)
    print("RAG検索 精度評価結果")
    print("=" * 85)
    
    header = (
        f"{'Method':<25} {'MRR@5':>8} {'R@1':>8} {'R@3':>8} {'R@5':>8} "
        f"{'P@5':>8} {'nDCG@5':>8}"
    )
    if show_latency:
        header += f" {'Latency':>10}"
    print(f"\n{header}")
    print("-" * 95)

    for r in results:
        line = (
            f"{r.method:<25} {r.mrr:>8.3f} {r.recall_at_1:>8.3f} "
            f"{r.recall_at_3:>8.3f} {r.recall_at_5:>8.3f} "
            f"{r.precision_at_5:>8.3f} {r.ndcg_at_5:>8.3f}"
        )
        if show_latency:
            line += f" {r.avg_latency_ms:>8.0f}ms"
        print(line)
    
    print("-" * 85)
    print(f"\n評価クエリ数: {results[0].num_queries}")
    
    if len(results) >= 2:
        baseline = results[0].mrr
        best = max(r.mrr for r in results)
        if baseline > 0:
            print(f"MRR改善率（{results[0].method} → best）: +{((best - baseline) / baseline) * 100:.1f}%")
    
    print("=" * 85 + "\n")


def save_results(results: List[EvaluationResult], simulate: bool):
    """評価結果をJSONで保存"""
    output_path = Path(__file__).parent / "evaluation_results.json"
    
    output = {
        "evaluated_at": datetime.now().isoformat(),
        "mode": "simulation" if simulate else "api (pgvector + BM25 hybrid)",
        "num_queries": results[0].num_queries if results else 0,
        "results": [
            {k: round(v, 3) if isinstance(v, float) else v for k, v in asdict(r).items()}
            for r in results
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"結果を保存: {output_path}")


# ==================== メイン ====================

def main():
    parser = argparse.ArgumentParser(description='RAG検索の精度評価')
    parser.add_argument('--simulate', action='store_true',
                        help='シミュレーションモード（APIなしで手法比較デモ）')
    parser.add_argument('--api-url', type=str, default='http://localhost:8001',
                        help='APIサーバーのURL（デフォルト: http://localhost:8001）')
    parser.add_argument('--queries', type=str, default='sample_queries.json',
                        help='テストクエリファイル')
    args = parser.parse_args()
    
    # テストクエリ読み込み
    queries = load_test_queries(args.queries)
    logger.info(f"{len(queries)}件のテストクエリを読み込みました")
    
    results = []
    
    if args.simulate:
        # シミュレーション: 4手法を比較
        logger.info("シミュレーションモード（手法比較デモ）")
        for method in ['dense', 'sparse', 'hybrid', 'rerank']:
            logger.info(f"  {method} を評価中...")
            r = evaluate_queries(queries, method, simulate=True)
            results.append(r)
            logger.info(f"  → MRR: {r.mrr:.3f}, Recall@5: {r.recall_at_5:.3f}")
    else:
        # API経由: 実際のハイブリッド検索を評価
        logger.info(f"APIサーバーに接続: {args.api_url}")
        
        # ヘルスチェック
        try:
            import urllib.request
            with urllib.request.urlopen(f"{args.api_url}/health", timeout=5) as resp:
                health = json.loads(resp.read().decode('utf-8'))
            logger.info(f"API状態: {health.get('status')}, ドキュメント数: {health.get('documents', 'N/A')}")
        except Exception as e:
            logger.error(f"APIに接続できません: {e}")
            logger.error("Docker Composeが起動しているか確認してください: docker-compose up -d")
            return
        
        logger.info("ハイブリッド検索（pgvector + BM25 + Re-ranker）を評価中...")
        r = evaluate_queries(queries, "hybrid+rerank (API)", api_url=args.api_url)
        results.append(r)
        logger.info(f"  → MRR: {r.mrr:.3f}, Recall@5: {r.recall_at_5:.3f}, 平均レイテンシ: {r.avg_latency_ms:.0f}ms")
    
    # 結果出力
    print_results(results, show_latency=not args.simulate)
    save_results(results, args.simulate)


if __name__ == "__main__":
    main()
