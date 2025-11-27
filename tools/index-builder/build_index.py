"""
インデックス構築スクリプト
前処理済みのチャンクからFAISSとBM25のインデックスを構築する
"""

import logging
from pathlib import Path
import sys
import json

# rag_coreをインポートできるようにパスを追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.dense_index import FaissIndexManager
from rag_core.sparse_index import BM25IndexManager
from rag_core.embeddings import EmbeddingService
from rag_core.tokenization import tokenizer
from rag_core.chunking import Chunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_chunks(filepath: Path):
    chunks = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            chunks.append(Chunk(**data))
    return chunks

def build_index(input_file: str, output_dir: str):
    input_path = Path(input_file)
    index_dir = Path(output_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"チャンクファイルを読み込み中: {input_path}")
    chunks = load_chunks(input_path)
    
    # メタデータとテキストを準備
    metadata = [chunk.to_dict() for chunk in chunks]
    texts = [chunk.text for chunk in chunks]
    
    # 1. Dense Index（FAISS）を構築
    logger.info("Dense Index (FAISS) を構築中...")
    embedding_service = EmbeddingService()
    embeddings = embedding_service.encode(texts, show_progress=True)
    
    faiss_manager = FaissIndexManager(
        str(index_dir / "maintenance.faiss"),
        str(index_dir / "maintenance.faiss.meta.json")
    )
    faiss_manager.build(embeddings)
    faiss_manager.save(metadata)
    
    # 2. Sparse Index（BM25）を構築
    logger.info("Sparse Index (BM25) を構築中...")
    tokenized_corpus = [tokenizer.tokenize(text) for text in texts]
    
    bm25_manager = BM25IndexManager(
        str(index_dir / "maintenance.bm25"),
        str(index_dir / "maintenance.bm25.meta.pkl")
    )
    bm25_manager.build(tokenized_corpus)
    bm25_manager.save(metadata)
    
    logger.info("インデックス構築完了！")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/chunks.jsonl")
    parser.add_argument("--output", default="data/demo/indices")
    args = parser.parse_args()
    
    build_index(args.input, args.output)
