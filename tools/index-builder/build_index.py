"""pgvector（Dense）+ BM25（Sparse）の両インデックスをまとめて構築する。"""

import json
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.chunking import Chunk
from rag_core.dense_index import PgvectorIndexManager
from rag_core.embeddings import EmbeddingService
from rag_core.sparse_index import BM25IndexManager
from rag_core.tokenization import tokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_chunks(filepath: Path):
    chunks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(Chunk(**json.loads(line)))
    return chunks


def build_index(input_file: str, output_dir: str):
    """Dense は pgvector、Sparse は BM25 ファイルに書き出す。"""
    input_path = Path(input_file)
    index_dir = Path(output_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    logger.info("loading chunks: %s", input_path)
    chunks = load_chunks(input_path)

    metadata = [chunk.to_dict() for chunk in chunks]
    texts = [chunk.text for chunk in chunks]
    logger.info("loaded chunks: %d", len(chunks))

    logger.info("building dense index (pgvector)")
    embedding_service = EmbeddingService()
    embeddings = embedding_service.encode(texts, show_progress=True)

    pgvector_manager = PgvectorIndexManager()
    pgvector_manager.build(embeddings, texts, metadata)
    pgvector_manager.close()

    logger.info("building sparse index (BM25)")
    tokenized_corpus = [tokenizer.tokenize(text) for text in texts]
    bm25_manager = BM25IndexManager(
        str(index_dir / "maintenance.bm25"),
        str(index_dir / "maintenance.bm25.meta.pkl"),
    )
    bm25_manager.build(tokenized_corpus)
    bm25_manager.save(metadata)

    logger.info("index build done")
    logger.info("  dense (pgvector): assistchat.documents")
    logger.info("  sparse (BM25): %s", index_dir / "maintenance.bm25")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/chunks.jsonl")
    parser.add_argument("--output", default="data/demo/indices")
    args = parser.parse_args()

    build_index(args.input, args.output)
