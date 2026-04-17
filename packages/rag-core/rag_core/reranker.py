"""Cross-Encoder による Re-ranking。Bi-Encoder より遅いが精度が上がる。"""

import logging
from typing import Any, Dict, List, Optional

from sentence_transformers import CrossEncoder

from .config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-Encoder で検索結果を再順位付けする。

    Bi-Encoder に比べ処理コストが高いので、上位候補のみに適用する運用が前提。
    """

    # 同一モデルを何度もロードしないためのプロセス内キャッシュ。
    _model_cache: Dict[str, CrossEncoder] = {}

    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: int = 32,
        device: Optional[str] = None,
    ):
        self.model_name = model_name or settings["retrieval"].get(
            "reranker_model",
            "cross-encoder/ms-marco-MiniLM-L-12-v2",
        )
        self.batch_size = batch_size
        self.device = device
        self.model: Optional[CrossEncoder] = None
        self._is_available = False

        self._load_model()

    def _load_model(self):
        try:
            if self.model_name in self._model_cache:
                self.model = self._model_cache[self.model_name]
                self._is_available = True
                return

            logger.info("loading CrossEncoder: %s", self.model_name)
            self.model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=512,
            )
            self._model_cache[self.model_name] = self.model
            self._is_available = True

        except Exception as e:
            self._is_available = False
            logger.error("CrossEncoder load failed: %s", e)
            logger.warning("reranking disabled")

    @property
    def is_available(self) -> bool:
        return self._is_available and self.model is not None

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """results に rerank_score を付けて降順ソートする。元のスコアは original_score へ退避。"""
        if not results or not self.is_available:
            return results[:top_k] if top_k else results

        pairs = []
        valid_indices = []
        for i, result in enumerate(results):
            text = result.get("text", "")
            if text:
                pairs.append([query, text])
                valid_indices.append(i)

        if not pairs:
            return results[:top_k] if top_k else results

        try:
            assert self.model is not None
            scores = self.model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            reranked = []
            for idx, score in zip(valid_indices, scores):
                r = results[idx].copy()
                r["rerank_score"] = float(score)
                r["original_score"] = r.get("score", 0.0)
                reranked.append(r)

            reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
            return reranked[:top_k] if top_k else reranked

        except Exception as e:
            logger.error("rerank failed: %s", e)
            return results[:top_k] if top_k else results
