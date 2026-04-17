"""
インデックス構築スクリプト

PostgreSQL pgvector（Dense）+ BM25（Sparse）のインデックスを構築。
"""

import logging
from pathlib import Path
import sys
import json

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.dense_index import PgvectorIndexManager
from rag_core.sparse_index import BM25IndexManager
from rag_core.embeddings import EmbeddingService
from rag_core.tokenization import tokenizer
from rag_core.chunking import Chunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_chunks(filepath: Path):
    """チャンクファイルを読み込み"""
    chunks = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            chunks.append(Chunk(**data))
    return chunks

def build_index(input_file: str, output_dir: str):
    """
    インデックス構築
    
    PostgreSQL pgvectorにベクトルを格納し、
    BM25はファイルベースで保存。
    """
    input_path = Path(input_file)
    index_dir = Path(output_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"チャンクファイルを読み込み中: {input_path}")
    chunks = load_chunks(input_path)
    
    metadata = [chunk.to_dict() for chunk in chunks]
    texts = [chunk.text for chunk in chunks]
    
    logger.info(f"{len(chunks)}個のチャンクを読み込みました")
    
    # 1. Dense Index（PostgreSQL pgvector）を構築
    logger.info("=" * 80)
    logger.info("Dense Index (PostgreSQL pgvector) を構築中...")
    logger.info("=" * 80)
    
    embedding_service = EmbeddingService()
    embeddings = embedding_service.encode(texts, show_progress=True)
    
    pgvector_manager = PgvectorIndexManager()
    pgvector_manager.build(embeddings, texts, metadata)
    pgvector_manager.close()
    
    # 2. Sparse Index（BM25）を構築
    logger.info("=" * 80)
    logger.info("Sparse Index (BM25) を構築中...")
    logger.info("=" * 80)
    
    tokenized_corpus = [tokenizer.tokenize(text) for text in texts]
    
    bm25_manager = BM25IndexManager(
        str(index_dir / "maintenance.bm25"),
        str(index_dir / "maintenance.bm25.meta.pkl")
    )
    bm25_manager.build(tokenized_corpus)
    bm25_manager.save(metadata)
    
    logger.info("=" * 80)
    logger.info("✅ インデックス構築完了！")
    logger.info("=" * 80)
    logger.info(f"  - Dense (pgvector): PostgreSQL assistchat.documents に保存")
    logger.info(f"  - Sparse (BM25): {index_dir / 'maintenance.bm25'} に保存")
    logger.info("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/chunks.jsonl")
    parser.add_argument("--output", default="data/demo/indices")
    args = parser.parse_args()
    
    build_index(args.input, args.output)
