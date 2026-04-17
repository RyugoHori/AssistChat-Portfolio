"""
RAG 品質の LLM-as-judge 評価 + MLflow 記録

検索精度（MRR など）に加えて、RAG 固有の品質メトリクス
（Faithfulness / Answer Relevancy / Context Precision）を測定し、
MLflow に記録する。

使い方:
    # API 経由で実行
    python evaluate_rag.py --api-url http://localhost:8000 --num-queries 10

    # API 無し・ヒューリスティックのみ（CI 用）
    OPENAI_API_KEY 未設定で自動的にヒューリスティックにフォールバック

    # MLflow tracking URI を指定
    MLFLOW_TRACKING_URI=file:./mlruns python evaluate_rag.py

設計方針:
    - 重い LLM 呼び出しを含むため CI では実行せず、手動／ローカル運用
    - サンプルクエリは sample_queries.json の先頭 N 件（--num-queries で制御）
    - MLflow が未インストールでも動くように optional import
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).parent))

from evaluator_rag import RagEvaluationCase, RagEvaluator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ==================== データ取得 ====================

def fetch_rag_response(
    api_url: str,
    query: str,
    k: int = 5,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """
    /api/chat をストリーミングで呼び出し、回答と context を取得する

    Returns:
        {
            "answer": str,
            "contexts": List[str],
            "retrieved_doc_ids": List[str],
        }
    """
    url = f"{api_url.rstrip('/')}/api/chat"
    payload = {
        "query": query,
        "k": k,
        "history": [],
    }

    answer_parts: List[str] = []
    sources: List[Dict[str, Any]] = []

    with requests.post(url, json=payload, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "token":
                answer_parts.append(event.get("content", ""))
            elif etype == "meta":
                sources = event.get("sources", []) or []
            elif etype == "error":
                raise RuntimeError(f"Chat API error: {event.get('message')}")

    contexts = [s.get("snippet", "") for s in sources if s.get("snippet")]
    retrieved_ids = [s.get("docId", "") for s in sources if s.get("docId")]

    return {
        "answer": "".join(answer_parts).strip(),
        "contexts": contexts,
        "retrieved_doc_ids": retrieved_ids,
    }


def load_queries(path: Path, num: int) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = data.get("queries", [])
    return queries[:num]


# ==================== MLflow 記録 ====================

def setup_mlflow(experiment_name: str) -> Optional[Any]:
    """
    MLflow をオプショナル初期化。未インストールなら None を返す
    """
    try:
        import mlflow
    except ImportError:
        logger.info("mlflow 未インストール。記録はスキップします。")
        return None

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    logger.info("MLflow tracking_uri=%s, experiment=%s", tracking_uri, experiment_name)
    return mlflow


# ==================== メイン ====================

def run_evaluation(
    api_url: str,
    queries_path: Path,
    num_queries: int,
    model: str,
    experiment_name: str,
    output_path: Optional[Path],
) -> Dict[str, Any]:
    queries = load_queries(queries_path, num_queries)
    logger.info("対象クエリ数: %d", len(queries))

    evaluator = RagEvaluator(model=model)

    cases: List[RagEvaluationCase] = []
    fetch_errors: List[str] = []

    for q in queries:
        query_text = q["query"]
        try:
            result = fetch_rag_response(api_url, query_text)
        except Exception as e:
            logger.warning("クエリ取得失敗: %s (%s)", query_text, e)
            fetch_errors.append(query_text)
            continue

        cases.append(
            RagEvaluationCase(
                query=query_text,
                answer=result["answer"],
                contexts=result["contexts"],
                relevant_doc_ids=q.get("relevant_docs", []),
                retrieved_doc_ids=result["retrieved_doc_ids"],
            )
        )

    if not cases:
        raise RuntimeError("有効な評価ケースが 0 件でした。API 接続を確認してください。")

    logger.info("評価実行中（%d 件、model=%s）", len(cases), model)
    per_case_scores = []
    for i, case in enumerate(cases):
        logger.info("  [%d/%d] %s", i + 1, len(cases), case.query[:30])
        per_case_scores.append(evaluator.evaluate_case(case))

    scores = {
        "faithfulness": sum(s.faithfulness for s in per_case_scores) / len(per_case_scores),
        "answer_relevancy": sum(s.answer_relevancy for s in per_case_scores) / len(per_case_scores),
        "context_precision": sum(s.context_precision for s in per_case_scores) / len(per_case_scores),
    }

    per_case = [
        {
            "query": c.query,
            "answer": c.answer[:200],
            "faithfulness": s.faithfulness,
            "answer_relevancy": s.answer_relevancy,
            "context_precision": s.context_precision,
        }
        for c, s in zip(cases, per_case_scores)
    ]

    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": model,
        "num_cases": len(cases),
        "num_fetch_errors": len(fetch_errors),
        "aggregate": scores,
    }

    logger.info("--- 集計結果 ---")
    for k, v in scores.items():
        logger.info("  %-20s %.3f", k, v)

    mlflow = setup_mlflow(experiment_name)
    if mlflow is not None:
        with mlflow.start_run(run_name=f"rag-eval-{datetime.utcnow():%Y%m%d-%H%M%S}"):
            mlflow.log_params({
                "judge_model": model,
                "num_queries": len(cases),
                "api_url": api_url,
                "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
            })
            for metric_name, value in scores.items():
                mlflow.log_metric(metric_name, value)

            artifact_payload = {
                "summary": summary,
                "per_case": per_case,
            }
            artifact_path = Path("mlflow_rag_eval.json")
            artifact_path.write_text(
                json.dumps(artifact_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            mlflow.log_artifact(str(artifact_path))
            artifact_path.unlink(missing_ok=True)

    if output_path:
        output_path.write_text(
            json.dumps({"summary": summary, "per_case": per_case}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("結果を保存: %s", output_path)

    return summary


def main():
    parser = argparse.ArgumentParser(description="RAG 品質の LLM-as-judge 評価")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--queries", default="tools/evaluation/sample_queries.json")
    parser.add_argument("--num-queries", type=int, default=10)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--experiment", default="assistchat-rag-eval")
    parser.add_argument("--output", default="tools/evaluation/rag_evaluation_results.json")
    args = parser.parse_args()

    queries_path = Path(args.queries)
    if not queries_path.exists():
        # Fall back: try relative to this script
        queries_path = Path(__file__).parent / "sample_queries.json"

    output_path = Path(args.output) if args.output else None

    summary = run_evaluation(
        api_url=args.api_url,
        queries_path=queries_path,
        num_queries=args.num_queries,
        model=args.model,
        experiment_name=args.experiment,
        output_path=output_path,
    )

    print("\n========== RAG Quality Evaluation ==========")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
