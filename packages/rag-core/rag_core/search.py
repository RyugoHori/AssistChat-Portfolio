"""
ハイブリッド検索エンジン

FAISSとBM25を組み合わせて、RRFで結果を統合する。
ベクトル検索だけだと専門用語やエラーコードの検索精度が低かったので、
キーワード検索も組み合わせることにした。
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config import settings
from .dense_index import FaissIndexManager
from .sparse_index import BM25IndexManager
from .tokenization import tokenizer
from .embeddings import EmbeddingService
from .reranker import Reranker

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rank_lists: List[List[str]],
    k: int = 60
) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion (RRF) アルゴリズム
    
    複数のランキングリストを統合する。
    Score = Σ(1 / (k + rank))
    
    k=60は論文（Cormack et al., 2009）で最適とされた値。
    
    Args:
        rank_lists: ランキングリストのリスト。各リストはdoc_idのリスト（順位順）
        k: RRFのパラメータ（デフォルト60）
    
    Returns:
        doc_idごとの統合スコアの辞書
    """
    fused_scores: Dict[str, float] = {}
    
    for rank_list in rank_lists:
        for rank, doc_id in enumerate(rank_list):
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0.0
            fused_scores[doc_id] += 1.0 / (k + rank + 1)
    
    return fused_scores


class HybridSearcher:
    """
    Dense(FAISS) + Sparse(BM25) のハイブリッド検索
    
    最初はFAISSだけで作ったけど、「E-1234」みたいなエラーコードの
    検索精度がイマイチだったのでBM25も追加した。
    RRFで結果を統合すると、両方の良いとこ取りができる。
    """

    def __init__(self, index_dir: Optional[str] = None):
        logger.info("ハイブリッド検索エンジンを初期化中...")
        
        # インデックスのパス
        if index_dir:
            base_dir = Path(index_dir)
        else:
            base_dir = Path(settings["data"]["index_path"])
            
        logger.info(f"インデックスディレクトリ: {base_dir}")

        # Dense検索（ベクトル検索）
        self.dense_searcher = FaissIndexManager(
            str(base_dir / "maintenance.faiss"), 
            str(base_dir / "maintenance.faiss.meta.json")
        )

        # Sparse検索（キーワード検索）
        self.sparse_searcher = BM25IndexManager(
            str(base_dir / "maintenance.bm25"), 
            str(base_dir / "maintenance.bm25.meta.pkl")
        )

        self.embedding_service = EmbeddingService(
            model_name=settings["embedding"]["model_name"],
            cache_folder=settings["embedding"]["cache_folder"]
        )
        
        self.tokenizer = tokenizer

        # Re-ranker（オプション）
        # Cross-Encoderで再順位付けすると精度上がるけど遅くなる
        self.reranker = None
        if settings["retrieval"].get("enable_reranking", False):
            self.reranker = Reranker(
                model_name=settings["retrieval"].get("reranker_model")
            )

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        ハイブリッド検索を実行
        
        フィルターは後処理で適用（ポストフィルタリング）。
        本当は検索時にフィルタリングした方が効率いいけど、
        500件程度なら後処理でも十分速い。
        """
        if not query:
            return []

        # 1. Dense検索
        query_vector = self.embedding_service.encode(query, show_progress=False)
        dense_results = self.dense_searcher.search(
            query_vector=query_vector,
            top_k=settings["retrieval"]["dense_top_k"]
        )

        # 2. Sparse検索
        tokenized_query = self.tokenizer.tokenize(query)
        sparse_results = self.sparse_searcher.search(
            tokenized_query=tokenized_query,
            top_k=settings["retrieval"]["sparse_top_k"]
        )

        # 3. RRFで統合
        # k=60は論文で最適とされてた値。変えてもあんまり変わらなかった
        fused_results = self._reciprocal_rank_fusion([
            {res[0]['chunk_id']: res[1] for res in dense_results},
            {res[0]['chunk_id']: res[1] for res in sparse_results}
        ])

        # 4. メタデータを付与
        all_results_map = {
            res[0]['chunk_id']: res[0] 
            for res in dense_results + sparse_results
        }
        
        candidates = []
        for chunk_id, score in fused_results:
            if chunk_id in all_results_map:
                item = all_results_map[chunk_id].copy()
                item['score'] = score
                candidates.append(item)

        # 5. フィルター適用
        if filters:
            filtered_candidates = []
            for item in candidates:
                if self._apply_filters(item, filters):
                    filtered_candidates.append(item)
            candidates = filtered_candidates

        # 6. Re-ranking（有効な場合）
        final_top_k = settings["retrieval"]["final_top_k"]
        
        if self.reranker and self.reranker.is_available and candidates:
            rerank_candidates_count = settings["retrieval"].get("rerank_candidates", 10)
            to_rerank = candidates[:rerank_candidates_count]
            reranked = self.reranker.rerank(query, to_rerank)
            return reranked[:final_top_k]
        
        return candidates[:final_top_k]

    def _reciprocal_rank_fusion(self, result_sets: List[Dict[str, float]], k: int = 60):
        """
        RRFスコア計算
        
        Score = Σ(1 / (k + rank))
        
        k=60は論文（Cormack et al., 2009）で最適とされてた値。
        試しに30とか120とかも試したけど、大差なかったのでデフォルトのまま。
        """
        fused_scores = {}
        
        for result_set in result_sets:
            sorted_docs = sorted(result_set.items(), key=lambda x: x[1], reverse=True)
            for rank, (doc_id, _) in enumerate(sorted_docs):
                if doc_id not in fused_scores:
                    fused_scores[doc_id] = 0.0
                fused_scores[doc_id] += 1.0 / (k + rank + 1)
                
        return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

    def _apply_filters(self, item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """フィルター適用。条件に合わなければFalse"""
        meta = item.get('metadata', {})
        
        # カテゴリ
        if filters.get('categories'):
            if meta.get('category') not in filters['categories']:
                return False
                
        # 故障分類
        if filters.get('workTypes'):
            if meta.get('work_type') not in filters['workTypes']:
                return False
                
        # 生産ライン
        if filters.get('productionLines'):
            if meta.get('line') not in filters['productionLines']:
                return False

        # 工場
        if filters.get('locations'):
            if meta.get('location') not in filters['locations']:
                return False
                
        # 設備階層（equipment1, 2, 3）
        for eq_level in ['equipment1', 'equipment2', 'equipment3']:
            filter_key = f"{eq_level}s"
            if filters.get(filter_key) and len(filters[filter_key]) > 0:
                val = meta.get(eq_level)
                if not val or val not in filters[filter_key]:
                    return False
                    
        return True
