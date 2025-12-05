"""
RAG設定

デフォルト設定を定義。必要に応じてコード内で直接変更可能。
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_CONFIG = {
    "project": {"name": "kairag-portfolio"},
    "data": {
        "index_path": "data/indices",
    },
    "embedding": {
        # 多言語対応のモデル。日本語もそこそこいける
        "model_name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "cache_folder": "models",
        "normalize_embeddings": True
    },
    "indexing": {
        "index_type": "Flat"  # 1万件件程度ならFlatで十分
    },
    "retrieval": {
        "enable_hybrid_search": True,
        "dense_top_k": 10,
        "sparse_top_k": 10,
        "final_top_k": 5,
        "enable_reranking": True,
        # 多言語対応のCross-Encoder
        "reranker_model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        "rerank_batch_size": 32,
        "rerank_candidates": 10
    }
}

def load_config() -> Dict[str, Any]:
    """設定を返す（デフォルト設定を使用）"""
    return DEFAULT_CONFIG

settings = load_config()
