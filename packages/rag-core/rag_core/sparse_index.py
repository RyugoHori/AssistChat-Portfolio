"""BM25 インデックス。型番・エラーコード等の完全一致に強い。"""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25IndexManager:
    """BM25 インデックスの構築・保存・検索。"""

    def __init__(self, index_path: str, metadata_path: str):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.index: BM25Okapi | None = None
        self.metadata: List[Dict[str, Any]] = []

        if self.index_path.exists() and self.metadata_path.exists():
            self.load()

    def build(self, tokenized_corpus: List[List[str]]):
        logger.info("building BM25 index: docs=%d", len(tokenized_corpus))
        self.index = BM25Okapi(tokenized_corpus)

    def save(self, metadata: List[Dict[str, Any]]):
        if self.index is None:
            raise RuntimeError("インデックスが構築されていません")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump(self.index, f)

        with open(self.metadata_path, "wb") as f:
            pickle.dump(metadata, f)

        self.metadata = metadata

    def load(self):
        logger.info("loading BM25 index: %s", self.index_path)
        with open(self.index_path, "rb") as f:
            self.index = pickle.load(f)
        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)

    def search(self, tokenized_query: List[str], top_k: int) -> List[Tuple[Dict[str, Any], float]]:
        if self.index is None:
            logger.warning("BM25 index not loaded")
            return []

        doc_scores = self.index.get_scores(tokenized_query)
        top_n_indices = np.argsort(doc_scores)[::-1][:top_k]

        results = []
        for idx in top_n_indices:
            score = doc_scores[idx]
            # スコア 0 はキーワード一致 0 件なので除外する。
            if score > 0:
                results.append((self.metadata[idx], float(score)))

        return results
