"""pgvector（Dense）+ BM25（Sparse）のハイブリッド検索。"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import settings
from .dense_index import PgvectorIndexManager
from .embeddings import EmbeddingService
from .normalize import normalize_text
from .reranker import Reranker
from .sparse_index import BM25IndexManager
from .tokenization import tokenizer

logger = logging.getLogger(__name__)

SEARCH_MODES = ("dense", "sparse", "hybrid", "hybrid_rerank")

# hybrid では候補が最大20件になるが、本番の方式（並べ替え）の候補が10件なので、
# 方式によって上限が変わらないよう、全方式を10件までにそろえる。
MAX_TOP_K = 10


def reciprocal_rank_fusion(
    rank_lists: List[List[str]],
    k: int = 60,
) -> Dict[str, float]:
    """Reciprocal Rank Fusion。score = Σ 1/(k + rank)。

    k=60 はよく使われる値。スコアのスケールが違う2つの結果を、順位だけで足し合わせる。
    """
    fused_scores: Dict[str, float] = {}

    for rank_list in rank_lists:
        for rank, doc_id in enumerate(rank_list):
            fused_scores.setdefault(doc_id, 0.0)
            fused_scores[doc_id] += 1.0 / (k + rank + 1)

    return fused_scores


class HybridSearcher:
    """Dense + Sparse + RRF + Re-ranker を一本化した検索エンジン。"""

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
            self.reranker = Reranker(model_name=settings["retrieval"].get("reranker_model"))

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        mode: str = "hybrid_rerank",
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """検索を実行する。フィルターがあれば、条件に合う記録の中から候補を取る。

        mode は評価で方式を比べるための切り替え。本番（API）は既定の hybrid_rerank で呼ぶ。
        """
        if mode not in SEARCH_MODES:
            raise ValueError(f"mode は {', '.join(SEARCH_MODES)} のどれかにしてください: {mode}")
        if top_k is None:
            top_k = settings["retrieval"]["final_top_k"]
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k は 1〜{MAX_TOP_K} にしてください: {top_k}")
        # 索引の文には同じ正規化をかけている。質問だけ素のままだと、全角や略語が一致しない。
        query = normalize_text(query)
        if not query:
            return []

        # 上位の候補を取ってから絞ると、条件に合う記録が候補から漏れて件数が減る。先に対象を決めておく。
        chunk_ids = None
        if filters:
            chunk_ids = {m["chunk_id"] for m in self.sparse_searcher.metadata if self._apply_filters(m, filters)}
            if not chunk_ids:
                return []

        # 方式ごとの応答時間を正しく比べるため、使わない側の検索（埋め込みの計算を含む）は実行しない。
        dense_results: List[Tuple[Dict[str, Any], float]] = []
        if mode != "sparse":
            query_vector = self.embedding_service.encode(query, show_progress=False)
            dense_results = self.dense_searcher.search(
                query_vector=query_vector,
                top_k=settings["retrieval"]["dense_top_k"],
                chunk_ids=chunk_ids,
            )

        sparse_results: List[Tuple[Dict[str, Any], float]] = []
        if mode != "dense":
            tokenized_query = self.tokenizer.tokenize(query)
            sparse_results = self.sparse_searcher.search(
                tokenized_query=tokenized_query,
                top_k=settings["retrieval"]["sparse_top_k"],
                chunk_ids=chunk_ids,
            )

        if mode in ("dense", "sparse"):
            candidates = []
            for item, score in dense_results + sparse_results:
                # BM25 の結果は索引の metadata そのものなので、コピーしてから書き込む。
                item = item.copy()
                item["score"] = score
                candidates.append(item)
        else:
            candidates = self._fuse_with_rrf(dense_results, sparse_results)

        if mode == "hybrid_rerank" and self.reranker and self.reranker.is_available and candidates:
            rerank_candidates_count = settings["retrieval"].get("rerank_candidates", 10)
            to_rerank = candidates[:rerank_candidates_count]
            reranked = self.reranker.rerank(query, to_rerank)
            return reranked[:top_k]

        return candidates[:top_k]

    def _fuse_with_rrf(
        self,
        dense_results: List[Tuple[Dict[str, Any], float]],
        sparse_results: List[Tuple[Dict[str, Any], float]],
    ) -> List[Dict[str, Any]]:
        """Dense と Sparse の結果を RRF で統合し、スコアの高い順に並べる。"""
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

        return candidates

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

        year_range = filters.get("yearRange")
        if year_range:
            year = str(meta.get("date") or "")[:4]
            if not year.isdigit() or not year_range["startYear"] <= int(year) <= year_range["endYear"]:
                return False

        for eq_level in ("equipment1", "equipment2", "equipment3"):
            filter_key = f"{eq_level}s"
            if filters.get(filter_key):
                val = meta.get(eq_level)
                if not val or val not in filters[filter_key]:
                    return False

        return True
