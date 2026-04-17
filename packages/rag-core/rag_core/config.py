"""RAG コアの設定。環境変数で上書き可能な辞書を返す。"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "project": {"name": "assistchat"},
    "data": {
        "index_path": "data/indices",  # BM25 インデックス置き場（pgvector は DB 側）
    },
    "database": {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "name": os.getenv("DB_NAME", "assistchat"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    },
    "embedding": {
        # 多言語対応。日本語もそこそこ通る。
        "model_name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "cache_folder": "models",
        "normalize_embeddings": True,
    },
    "retrieval": {
        "enable_hybrid_search": True,
        "dense_top_k": 10,
        "sparse_top_k": 10,
        "final_top_k": 5,
        "enable_reranking": True,
        "reranker_model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "rerank_batch_size": 32,
        "rerank_candidates": 10,
    },
}


def load_config() -> Dict[str, Any]:
    return DEFAULT_CONFIG


settings = load_config()
