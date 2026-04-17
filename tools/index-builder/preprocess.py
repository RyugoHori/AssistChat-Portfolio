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

def clean_text(text: str) -> str:
    """
    実データ特有のノイズをクリーニング
    
    実装内容:
    - 全角英数字を半角に統一
    - 略語の展開（例: CV → コンベア）
    - 不要な空白・改行の削除
    
    実データはExcel手書き管理からCSV化したため、
    OCRエラー、略語、表記揺れが多く含まれる。
    これらを正規化することで検索精度を向上。
    """
    import re
    
    # 全角英数字を半角に統一
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ))
    
    # 製造現場でよく使われる略語を展開
    # 実際のAGC愛知工場で使用される略語
    abbreviations = {
        'CV': 'コンベア',
        'MTR': 'モーター',
        'PMP': 'ポンプ',
        'CYL': 'シリンダー',
        'BRG': 'ベアリング',
    }
    for abbr, full in abbreviations.items():
        # 単語境界を考慮（例: "CVTEST"は置換しない）
        text = re.sub(r'\b' + abbr + r'\b', full, text)
    
    # 連続する空白を1つに
    text = re.sub(r'\s+', ' ', text)
    
    # 前後の空白を削除
    text = text.strip()
    
    return text

def preprocess(input_csv: str, output_dir: str):
    input_path = Path(input_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"CSVファイルを読み込み中: {input_path}")
    df = pd.read_csv(input_path)
    
    # 実データのノイズをクリーニング
    if 'text' in df.columns:
        logger.info("テキストデータをクリーニング中...")
        df['text'] = df['text'].apply(lambda x: clean_text(str(x)) if pd.notna(x) else x)
    
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
