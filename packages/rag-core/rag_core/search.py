"""
ハイブリッド検索エンジン

PostgreSQL pgvector（Dense）+ BM25（Sparse）のハイブリッド検索。
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config import settings
from .dense_index import PgvectorIndexManager
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
    Dense(pgvector) + Sparse(BM25) のハイブリッド検索

    評価指標（MRR@5）: 0.76（Re-ranking 有効時。詳細は README.md 参照）
    """

    def __init__(self, index_dir: Optional[str] = None):
        logger.info("ハイブリッド検索エンジンを初期化中...")
        
        # インデックスのパス（BM25用のみ）
        if index_dir:
            base_dir = Path(index_dir)
        else:
            base_dir = Path(settings["data"]["index_path"])
            
        logger.info(f"インデックスディレクトリ（BM25）: {base_dir}")

        # Dense検索（PostgreSQL pgvector）
        self.dense_searcher = PgvectorIndexManager()

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
        # Cross-Encoderによる再順位付けは精度向上の一方で処理速度が低下
        self.reranker = None
        if settings["retrieval"].get("enable_reranking", False):
            self.reranker = Reranker(
                model_name=settings["retrieval"].get("reranker_model")
            )

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        ハイブリッド検索を実行
        
        フィルターは後処理で適用（ポストフィルタリング）。
        データ規模（500件程度）を考慮し、後処理でも十分な性能を確保。
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
        # k=60は論文（Cormack et al., 2009）で最適値として提示
        # dense/sparse の結果は既に順位順なので chunk_id の配列を渡すだけ
        dense_ranked = [res[0]['chunk_id'] for res in dense_results]
        sparse_ranked = [res[0]['chunk_id'] for res in sparse_results]
        fused_scores = reciprocal_rank_fusion([dense_ranked, sparse_ranked])
        fused_results = sorted(
            fused_scores.items(), key=lambda x: x[1], reverse=True
        )

        # 4. メタデータを付与
        # 元のスコアも保持（デバッグ・評価用）
        # DenseとSparse両方に存在するchunk_idは最大スコアを採用
        all_results_map = {}
        for res in dense_results + sparse_results:
            chunk_id = res[0]['chunk_id']
            if chunk_id not in all_results_map:
                all_results_map[chunk_id] = {
                    'item': res[0],
                    'original_score': res[1]
                }
            else:
                # より高いスコアで更新
                if res[1] > all_results_map[chunk_id]['original_score']:
                    all_results_map[chunk_id]['original_score'] = res[1]
        
        candidates = []
        for chunk_id, rrf_score in fused_results:
            if chunk_id in all_results_map:
                item = all_results_map[chunk_id]['item'].copy()
                item['score'] = rrf_score  # RRFスコア
                item['original_score'] = all_results_map[chunk_id]['original_score']  # 元のスコア
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

    def _apply_filters(self, item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """フィルター適用（条件不一致時はFalse）"""
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
