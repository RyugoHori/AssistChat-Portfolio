"""pgvector（Dense）+ BM25（Sparse）のハイブリッド検索。"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings
from .dense_index import PgvectorIndexManager
from .embeddings import EmbeddingService
from .reranker import Reranker
from .sparse_index import BM25IndexManager
from .tokenization import tokenizer

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rank_lists: List[List[str]],
    k: int = 60,
) -> Dict[str, float]:
    """Reciprocal Rank Fusion。score = Σ 1/(k + rank)。

    k=60 は Cormack et al. (2009) で良好とされた値。
    """
    fused_scores: Dict[str, float] = {}

    for rank_list in rank_lists:
        for rank, doc_id in enumerate(rank_list):
            fused_scores.setdefault(doc_id, 0.0)
            fused_scores[doc_id] += 1.0 / (k + rank + 1)

    return fused_scores


class HybridSearcher:
    """Dense + Sparse + RRF + Re-ranker を一本化した検索エンジン。

    評価指標 MRR@5 = 0.76（Re-ranker 有効時。詳細は README）。
    """

    def __init__(self, index_dir: Optional[str] = None):
        logger.info("HybridSearcher init")

        base_dir = Path(index_dir) if index_dir else Path(settings["data"]["index_path"])
        logger.info("BM25 index dir: %s", base_dir)

        self.dense_searcher = PgvectorIndexManager()
        self.sparse_searcher = BM25IndexManager(
            str(base_dir / "maintenance.bm25"),
            str(base_dir / "maintenance.bm25.meta.pkl"),
        )

        self.embedding_service = EmbeddingService(
            model_name=settings["embedding"]["model_name"],
            cache_folder=settings["embedding"]["cache_folder"],
        )
        self.tokenizer = tokenizer

        # Re-ranker は精度↑ / 速度↓ のトレードオフ。設定で ON/OFF を切替可能。
        self.reranker = None
        if settings["retrieval"].get("enable_reranking", False):
            self.reranker = Reranker(
                model_name=settings["retrieval"].get("reranker_model")
            )

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """ハイブリッド検索を実行する。フィルターは後処理（post-filter）で適用。"""
        if not query:
            return []

        query_vector = self.embedding_service.encode(query, show_progress=False)
        dense_results = self.dense_searcher.search(
            query_vector=query_vector,
            top_k=settings["retrieval"]["dense_top_k"],
        )

        tokenized_query = self.tokenizer.tokenize(query)
        sparse_results = self.sparse_searcher.search(
            tokenized_query=tokenized_query,
            top_k=settings["retrieval"]["sparse_top_k"],
        )

        dense_ranked = [res[0]["chunk_id"] for res in dense_results]
        sparse_ranked = [res[0]["chunk_id"] for res in sparse_results]
        fused_scores = reciprocal_rank_fusion([dense_ranked, sparse_ranked])
        fused_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

        # Dense / Sparse 両方に出た chunk は元スコアの最大値を保持（デバッグ用）。
        all_results_map: Dict[str, Dict[str, Any]] = {}
        for res in dense_results + sparse_results:
            chunk_id = res[0]["chunk_id"]
            if chunk_id not in all_results_map:
                all_results_map[chunk_id] = {"item": res[0], "original_score": res[1]}
            elif res[1] > all_results_map[chunk_id]["original_score"]:
                all_results_map[chunk_id]["original_score"] = res[1]

        candidates = []
        for chunk_id, rrf_score in fused_results:
            if chunk_id in all_results_map:
                item = all_results_map[chunk_id]["item"].copy()
                item["score"] = rrf_score
                item["original_score"] = all_results_map[chunk_id]["original_score"]
                candidates.append(item)

        if filters:
            candidates = [c for c in candidates if self._apply_filters(c, filters)]

        final_top_k = settings["retrieval"]["final_top_k"]

        if self.reranker and self.reranker.is_available and candidates:
            rerank_candidates_count = settings["retrieval"].get("rerank_candidates", 10)
            to_rerank = candidates[:rerank_candidates_count]
            reranked = self.reranker.rerank(query, to_rerank)
            return reranked[:final_top_k]

        return candidates[:final_top_k]

    def _apply_filters(self, item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        meta = item.get("metadata", {})

        if filters.get("categories") and meta.get("category") not in filters["categories"]:
            return False
        if filters.get("workTypes") and meta.get("work_type") not in filters["workTypes"]:
            return False
        if filters.get("productionLines") and meta.get("line") not in filters["productionLines"]:
            return False
        if filters.get("locations") and meta.get("location") not in filters["locations"]:
            return False

        for eq_level in ("equipment1", "equipment2", "equipment3"):
            filter_key = f"{eq_level}s"
            if filters.get(filter_key):
                val = meta.get(eq_level)
                if not val or val not in filters[filter_key]:
                    return False

        return True
