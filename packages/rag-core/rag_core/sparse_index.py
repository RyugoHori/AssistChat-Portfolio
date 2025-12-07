"""
BM25インデックスの管理

キーワード検索用。エラーコードとか型番の完全一致に強い。
最初はElasticsearch使おうとしたけど、500件程度ならrank-bm25で十分だった。
"""

import pickle
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

class BM25IndexManager:
    """BM25インデックスの構築・保存・検索"""

    def __init__(self, index_path: str, metadata_path: str):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.index: BM25Okapi | None = None
        self.metadata: List[Dict[str, Any]] = []

        if self.index_path.exists() and self.metadata_path.exists():
            self.load()

    def build(self, tokenized_corpus: List[List[str]]):
        """インデックス構築。トークン化済みのテキストを渡す"""
        logger.info(f"BM25インデックスを構築中: {len(tokenized_corpus)}件のドキュメント")
        self.index = BM25Okapi(tokenized_corpus)

    def save(self, metadata: List[Dict[str, Any]]):
        """インデックスとメタデータを保存"""
        if self.index is None:
            raise RuntimeError("インデックスが構築されていません。")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, 'wb') as f:
            pickle.dump(self.index, f)

        with open(self.metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        
        self.metadata = metadata

    def load(self):
        """インデックス読み込み"""
        logger.info(f"BM25インデックスを読み込み中: {self.index_path}")
        with open(self.index_path, 'rb') as f:
            self.index = pickle.load(f)
        
        with open(self.metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)

    def search(self, tokenized_query: List[str], top_k: int) -> List[Tuple[Dict[str, Any], float]]:
        """検索実行。トークン化済みのクエリを渡す"""
        if self.index is None:
            logger.warning("BM25インデックスが読み込まれていません。")
            return []

        doc_scores = self.index.get_scores(tokenized_query)
        top_n_indices = np.argsort(doc_scores)[::-1][:top_k]

        results = []
        for idx in top_n_indices:
            score = doc_scores[idx]
            # スコア0は除外（キーワードが1つも一致しなかった）
            if score > 0:
                results.append((self.metadata[idx], float(score)))
        
        return results
