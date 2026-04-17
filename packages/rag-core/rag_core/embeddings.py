"""テキスト埋め込みサービス。sentence-transformers のローカルモデルを使う。"""

import logging
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """paraphrase-multilingual-mpnet-base-v2 で日本語文を 768 次元ベクトル化する。"""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        cache_folder: Optional[str] = "models",
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.cache_folder = Path(cache_folder) if cache_folder else None
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        logger.info("embedding model init: %s device=%s", model_name, self.device)
        self._load_model()

    def _load_model(self):
        try:
            if self.cache_folder:
                self.cache_folder.mkdir(parents=True, exist_ok=True)

            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=str(self.cache_folder) if self.cache_folder else None,
                device=self.device,
            )
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.max_seq_length = self.model.max_seq_length

        except Exception as e:
            logger.error("failed to load embedding model: %s", e)
            raise

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]

        try:
            return self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress and len(texts) > 100,
                convert_to_numpy=convert_to_numpy,
                device=self.device,
            )
        except Exception as e:
            logger.error("encode failed: %s", e)
            raise
