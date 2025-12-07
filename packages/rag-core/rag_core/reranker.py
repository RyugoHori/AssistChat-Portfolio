"""
Re-ranker（再順位付け）

Cross-Encoderで検索結果を並べ替える。
Bi-Encoder（FAISSとか）より精度高いけど遅い。
上位10件だけ再順位付けすることで速度と精度のバランスを取ってる。
"""

import logging
from typing import Dict, List, Any, Optional
from sentence_transformers import CrossEncoder
from .config import settings

logger = logging.getLogger(__name__)

class Reranker:
    """
    Cross-Encoderによるリランカー
    
    Bi-Encoder（FAISS）は高速だけど、クエリと文書を別々にエンコードするので
    細かいニュアンスを捉えきれない。
    Cross-Encoderはクエリと文書のペアを一緒にエンコードするので精度が高い。
    ただし遅いので、上位候補だけに適用する。
    """
    
    # モデルのキャッシュ（同じモデルを何度も読み込まないように）
    _model_cache: Dict[str, CrossEncoder] = {}
    
    def __init__(
        self, 
        model_name: Optional[str] = None,
        batch_size: int = 32,
        device: Optional[str] = None
    ):
        self.model_name = model_name or settings["retrieval"].get(
            "reranker_model", 
            "cross-encoder/ms-marco-MiniLM-L-12-v2"
        )
        self.batch_size = batch_size
        self.device = device
        self.model = None
        self._is_available = False
        
        self._load_model()
    
    def _load_model(self):
        """モデル読み込み"""
        try:
            # キャッシュにあればそれを使う
            if self.model_name in self._model_cache:
                self.model = self._model_cache[self.model_name]
                self._is_available = True
                return
            
            logger.info(f"CrossEncoderを読み込み中: {self.model_name}")
            self.model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=512
            )
            
            self._model_cache[self.model_name] = self.model
            self._is_available = True
            
        except Exception as e:
            self._is_available = False
            logger.error(f"CrossEncoderの読み込みに失敗しました: {e}")
            logger.warning("リランキングは無効化されました。")

    @property
    def is_available(self) -> bool:
        return self._is_available and self.model is not None

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        検索結果を再順位付け
        
        元のスコアは original_score に保存して、
        新しいスコアは rerank_score に入れる。
        """
        if not results or not self.is_available:
            return results[:top_k] if top_k else results
            
        # クエリと文書のペアを作成
        pairs = []
        valid_indices = []
        
        for i, result in enumerate(results):
            text = result.get('text', '')
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
                convert_to_numpy=True
            )
            
            reranked_results = []
            for idx, score in zip(valid_indices, scores):
                result = results[idx].copy()
                result['rerank_score'] = float(score)
                result['original_score'] = result.get('score', 0.0)
                reranked_results.append(result)
            
            # 新しいスコアで降順ソート
            reranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            return reranked_results[:top_k] if top_k else reranked_results
            
        except Exception as e:
            logger.error(f"リランキングに失敗しました: {e}")
            return results[:top_k] if top_k else results
