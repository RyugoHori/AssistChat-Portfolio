"""
テキストをベクトルに変換するやつ

sentence-transformersを使ってる。
最初はOpenAIのAPI使おうとしたけど、コスト的に厳しいのでローカルモデルに変更。
"""

import logging
from typing import List, Union, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path
import torch

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    テキスト埋め込みサービス
    
    multilingual-mpnet-base-v2 を使ってる。
    日本語専用モデルも試したけど、これで十分だった。
    """
    
    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        cache_folder: Optional[str] = "models",
        device: Optional[str] = None
    ):
        self.model_name = model_name
        self.cache_folder = Path(cache_folder) if cache_folder else None
        
        # GPU使えるなら使う
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"埋め込みモデルを初期化中: {model_name}")
        logger.info(f"使用デバイス: {self.device}")
        
        self._load_model()
        
    def _load_model(self):
        """モデル読み込み。初回はダウンロードに時間かかる"""
        try:
            if self.cache_folder:
                self.cache_folder.mkdir(parents=True, exist_ok=True)
                
            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=str(self.cache_folder) if self.cache_folder else None,
                device=self.device
            )
            
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.max_seq_length = self.model.max_seq_length
            
        except Exception as e:
            logger.error(f"モデルの読み込みに失敗しました: {e}")
            raise
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = True,
        convert_to_numpy: bool = True
    ) -> np.ndarray:
        """テキストをベクトルに変換"""
        if isinstance(texts, str):
            texts = [texts]
            
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress and len(texts) > 100,
                convert_to_numpy=convert_to_numpy,
                device=self.device
            )
            return embeddings
        except Exception as e:
            logger.error(f"エンコーディングに失敗しました: {e}")
            raise
