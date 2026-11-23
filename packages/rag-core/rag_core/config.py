"""RAG コアの設定。環境変数で上書き可能な辞書を返す。"""

import os
from typing import Any, Dict


DEFAULT_CONFIG = {
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
        # 日本語の保全記録でも使える多言語モデル。専用の日本語モデルより手元で扱いやすい。
        "model_name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "cache_folder": "models",
        "normalize_embeddings": True,
    },
    "retrieval": {
        "dense_top_k": 10,
        "sparse_top_k": 10,
        "final_top_k": 5,
        "enable_reranking": True,
        "reranker_model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "rerank_candidates": 10,
    },
}


def load_config() -> Dict[str, Any]:
    return DEFAULT_CONFIG


settings = load_config()
