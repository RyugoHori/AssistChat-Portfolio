"""
データ前処理スクリプト
CSVの生データをチャンク分割してJSONL形式に変換する
インデックス構築の前準備
"""

import pandas as pd
import logging
from pathlib import Path
import sys
import os

# rag_coreをインポートできるようにパスを追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.chunking import TextChunker
from rag_core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preprocess(input_csv: str, output_dir: str):
    input_path = Path(input_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"CSVファイルを読み込み中: {input_path}")
    df = pd.read_csv(input_path)
    
    documents = df.to_dict('records')
    logger.info(f"{len(documents)}件のドキュメントを読み込みました")
    
    # チャンカーを初期化
    chunker = TextChunker(
        chunk_size=500,
        chunk_overlap=50
    )
    
    # ドキュメントをチャンク分割
    logger.info("ドキュメントをチャンク分割中...")
    chunks = chunker.chunk_documents(documents, text_field="text", doc_id_field="doc_id")
    
    # チャンクを保存
    chunks_file = output_path / "chunks.jsonl"
    chunker.save_chunks(chunks, chunks_file)
    logger.info(f"{len(chunks)}個のチャンクを保存しました: {chunks_file}")

if __name__ == "__main__":
    # デモ用のデフォルトパス
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/demo/demo_logs.csv")
    parser.add_argument("--output", default="data/processed")
    args = parser.parse_args()
    
    preprocess(args.input, args.output)
