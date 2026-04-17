"""RAG プラットフォームのコアパッケージ。

pgvector + BM25 のハイブリッド検索と OpenAI による回答生成を提供する。
"""

from .chunking import Chunk, TextChunker
from .config import settings
from .dense_index import PgvectorIndexManager
from .embeddings import EmbeddingService
from .llm import LLMService
from .reranker import Reranker
from .scoring import calculate_display_score, sanitize_float_values
from .search import HybridSearcher
from .sparse_index import BM25IndexManager
from .tokenization import TokenizerService, tokenizer

__all__ = [
    "settings",
    "EmbeddingService",
    "TextChunker",
    "Chunk",
    "tokenizer",
    "TokenizerService",
    "HybridSearcher",
    "Reranker",
    "PgvectorIndexManager",
    "BM25IndexManager",
    "LLMService",
    "calculate_display_score",
    "sanitize_float_values",
]

__version__ = "3.0.0"
