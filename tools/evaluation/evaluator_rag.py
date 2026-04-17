"""
RAG 固有の品質評価（LLM-as-judge）

Faithfulness・Answer Relevancy・Context Precision の 3 メトリクスを
自前実装で評価する。Ragas 等の外部ライブラリには依存せず、OpenAI API を
直接呼び出して再現性の高い JSON 出力を取得する。

メトリクス:
    Faithfulness       : 回答中の主張が context で裏付けられているか [0, 1]
    Answer Relevancy   : 回答が元の質問に答えているか [0, 1]
    Context Precision  : 取得された context 内の relevant 率（MRR ベース） [0, 1]

参考:
    - https://docs.ragas.io/en/stable/concepts/metrics/
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)



@dataclass
class RagEvaluationCase:
    """1 クエリ分の入出力セット"""
    query: str
    answer: str
    contexts: List[str]
    relevant_doc_ids: List[str]          # 正解ラベル
    retrieved_doc_ids: List[str]         # 検索で返された doc_id


@dataclass
class RagEvaluationScores:
    """1 クエリあたりの RAG 品質スコア"""
    faithfulness: float
    answer_relevancy: float
    context_precision: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)



_FAITHFULNESS_PROMPT = """あなたは RAG 回答の品質評価者です。

以下のルールに従って回答を評価してください:
- Faithfulness は「回答中の事実主張のうち、context（根拠文）で裏付けられているものの割合」です
- 主張の数え方: 回答を独立した事実主張（claim）に分解し、各 claim を "裏付けあり/なし" に分類する
- 推論・意見・挨拶は評価対象に含めない
- 主張が 0 件の場合は 1.0 を返す（何も主張していないので不誠実になりようがない）

出力は以下の JSON 形式のみ（説明文や前置きなし）:
{
  "claims_total": <int>,
  "claims_supported": <int>,
  "faithfulness": <float in [0, 1]>
}
"""

_RELEVANCY_PROMPT = """あなたは RAG 回答の品質評価者です。

以下のルールに従って「回答が元の質問にどれだけ答えているか」を評価してください:
- 0.0 = 全く関係ない / 質問を誤解している
- 0.5 = 部分的に答えている / 一部ずれている
- 1.0 = 質問に的確かつ完全に答えている
- 挨拶や「情報不足」と正直に答えた場合は、誠実さを考慮して 0.6 付近とする

出力は以下の JSON 形式のみ:
{
  "reasoning": "<短い理由 1 文>",
  "answer_relevancy": <float in [0, 1]>
}
"""



class RagEvaluator:
    """
    LLM-as-judge による RAG 品質評価器

    OpenAI API を gpt-4o-mini（または任意のモデル）で呼び出し、
    Faithfulness と Answer Relevancy をスコアリングする。

    API キー未設定時はヒューリスティックフォールバックを使用する
    （CI 等で API 無しでも壊れないようにするため）。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Any = None

        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY 未設定のため、LLM-as-judge はヒューリスティックモードで動作します。"
            )

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """回答中の主張が context で裏付けられているかを判定"""
        if not answer.strip():
            return 0.0
        if not contexts:
            return 0.0

        if not self.api_key:
            return self._heuristic_faithfulness(answer, contexts)

        prompt = (
            f"{_FAITHFULNESS_PROMPT}\n\n"
            f"# 回答\n{answer}\n\n"
            f"# Context（根拠文）\n"
            + "\n---\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
            + "\n\n出力:"
        )
        try:
            data = self._call_judge(prompt)
            score = float(data.get("faithfulness", 0.0))
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.warning("Faithfulness 評価失敗、ヒューリスティックに切替: %s", e)
            return self._heuristic_faithfulness(answer, contexts)

    @staticmethod
    def _heuristic_faithfulness(answer: str, contexts: List[str]) -> float:
        """
        API キー無し環境用のフォールバック

        回答中の「名詞 n-gram（3 文字以上）」のうち context 内に現れる割合を代理指標とする。
        粒度が荒いが、方向性（改善しているか）は把握できる。
        """
        import re

        tokens = set(re.findall(r"[ぁ-んァ-ヶ一-龥a-zA-Z0-9]{3,}", answer))
        if not tokens:
            return 0.5  # 主張が無い場合

        context_text = " ".join(contexts)
        supported = sum(1 for t in tokens if t in context_text)
        return supported / len(tokens)

    def evaluate_answer_relevancy(self, query: str, answer: str) -> float:
        """回答が元の質問にどれだけ答えているかを判定"""
        if not answer.strip():
            return 0.0

        if not self.api_key:
            return self._heuristic_relevancy(query, answer)

        prompt = (
            f"{_RELEVANCY_PROMPT}\n\n"
            f"# 質問\n{query}\n\n"
            f"# 回答\n{answer}\n\n"
            "出力:"
        )
        try:
            data = self._call_judge(prompt)
            score = float(data.get("answer_relevancy", 0.0))
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.warning("Answer Relevancy 評価失敗、ヒューリスティックに切替: %s", e)
            return self._heuristic_relevancy(query, answer)

    @staticmethod
    def _heuristic_relevancy(query: str, answer: str) -> float:
        """質問の主要語が回答に含まれる割合"""
        import re

        query_tokens = set(re.findall(r"[ぁ-んァ-ヶ一-龥a-zA-Z0-9]{2,}", query))
        if not query_tokens:
            return 0.5
        covered = sum(1 for t in query_tokens if t in answer)
        return min(1.0, covered / len(query_tokens) * 1.2)

    @staticmethod
    def evaluate_context_precision(
        retrieved_doc_ids: List[str],
        relevant_doc_ids: List[str],
    ) -> float:
        """
        Context Precision: 検索された context の「正解含有率（重み付き）」

        MRR スタイルの定義を採用:
            Σ (rank^-1 * relevant_at_rank) / |retrieved|
        これにより「正解が上位に多いほど高スコア」となる。
        """
        if not retrieved_doc_ids:
            return 0.0
        relevant = set(relevant_doc_ids)

        weighted_sum = 0.0
        for i, did in enumerate(retrieved_doc_ids):
            if did in relevant:
                weighted_sum += 1.0 / (i + 1)

        # 正規化: 全部 relevant だったときの理論最大値で割る
        max_possible = sum(
            1.0 / (i + 1) for i in range(min(len(relevant), len(retrieved_doc_ids)))
        )
        if max_possible == 0:
            return 0.0
        return min(1.0, weighted_sum / max_possible)

    def _call_judge(self, prompt: str) -> Dict[str, Any]:
        """OpenAI API を叩いて JSON レスポンスを取得"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise RAG evaluator. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def evaluate_case(self, case: RagEvaluationCase) -> RagEvaluationScores:
        """1 ケース（query / answer / contexts）を総合評価"""
        faith = self.evaluate_faithfulness(case.answer, case.contexts)
        relevancy = self.evaluate_answer_relevancy(case.query, case.answer)
        precision = self.evaluate_context_precision(
            case.retrieved_doc_ids,
            case.relevant_doc_ids,
        )
        return RagEvaluationScores(
            faithfulness=faith,
            answer_relevancy=relevancy,
            context_precision=precision,
        )

    def evaluate_batch(
        self,
        cases: List[RagEvaluationCase],
        sleep_between: float = 0.0,
    ) -> Dict[str, float]:
        """複数ケースを評価して平均スコアを返す"""
        scores_list: List[RagEvaluationScores] = []
        for i, case in enumerate(cases):
            logger.info("[%d/%d] 評価中: %s", i + 1, len(cases), case.query[:30])
            scores_list.append(self.evaluate_case(case))
            if sleep_between > 0:
                time.sleep(sleep_between)

        if not scores_list:
            return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0}

        return {
            "faithfulness": sum(s.faithfulness for s in scores_list) / len(scores_list),
            "answer_relevancy": sum(s.answer_relevancy for s in scores_list) / len(scores_list),
            "context_precision": sum(s.context_precision for s in scores_list) / len(scores_list),
        }
