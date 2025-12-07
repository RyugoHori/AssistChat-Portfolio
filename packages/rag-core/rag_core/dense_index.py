"""
FAISSインデックスの管理

ベクトル検索用。500件程度ならFlatインデックスで十分速い。
数万件になったらIVFとか検討する必要あるかも。
"""

import faiss
import numpy as np
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from .config import settings

logger = logging.getLogger(__name__)

class FaissIndexManager:
    """FAISSインデックスの構築・保存・検索"""

    def __init__(self, index_path: str, metadata_path: str):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.index: faiss.Index | None = None
        self.metadata: List[Dict[str, Any]] = []

        # ファイルがあれば読み込む
        if self.index_path.exists() and self.metadata_path.exists():
            self.load()

    def build(self, embeddings: np.ndarray):
        """インデックス構築"""
        if not isinstance(embeddings, np.ndarray) or embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D numpy array.")

        dimension = embeddings.shape[1]
        index_type = settings["indexing"]["index_type"].strip()
        
        logger.info(f"FAISSインデックスを構築中: {index_type}, 次元数: {dimension}")
        
        self.index = faiss.index_factory(dimension, index_type)

        # コサイン類似度を使うために正規化
        if settings["embedding"]["normalize_embeddings"]:
            faiss.normalize_L2(embeddings)

        assert self.index is not None
        self.index.add(embeddings.astype(np.float32))

    def save(self, metadata: List[Dict[str, Any]]):
        """インデックスとメタデータを保存"""
        if self.index is None:
            raise RuntimeError("Index not built.")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        self.metadata = metadata

    def load(self):
        """インデックス読み込み"""
        logger.info(f"FAISSインデックスを読み込み中: {self.index_path}")
        self.index = faiss.read_index(str(self.index_path))
        
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)

    def search(self, query_vector: np.ndarray, top_k: int) -> List[Tuple[Dict[str, Any], float]]:
        """検索実行"""
        if self.index is None:
            logger.warning("インデックスが読み込まれていません。空の結果を返します。")
            return []

        # 1次元ベクトルなら2次元に変換
        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        if settings["embedding"]["normalize_embeddings"]:
            faiss.normalize_L2(query_vector.astype(np.float32))

        distances, indices = self.index.search(query_vector.astype(np.float32), top_k)
        
        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx != -1 and idx < len(self.metadata):
                results.append((self.metadata[idx], float(distances[0][i])))
        
        return results
