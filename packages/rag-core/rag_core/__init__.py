"""
RAGプラットフォームのコアパッケージ

PostgreSQL pgvector + BM25 のハイブリッド検索と
OpenAI APIによるLLM統合を提供。
"""

from .config import settings
from .embeddings import EmbeddingService
from .chunking import TextChunker, Chunk
from .tokenization import tokenizer, TokenizerService
from .search import HybridSearcher
from .reranker import Reranker
from .dense_index import PgvectorIndexManager
from .sparse_index import BM25IndexManager
from .llm import LLMService, calculate_display_score, sanitize_float_values

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