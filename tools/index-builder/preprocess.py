"""CSV をチャンク分割し JSONL に落とす前処理スクリプト。"""

import logging
import re
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.chunking import TextChunker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_ABBREVIATIONS = {
    "CV": "コンベア",
    "MTR": "モーター",
    "PMP": "ポンプ",
    "CYL": "シリンダー",
    "BRG": "ベアリング",
}

_FULLWIDTH_TABLE = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
)


def clean_text(text: str) -> str:
    """全角→半角、現場略語の展開、空白整形まで済ませた形で返す。"""
    text = text.translate(_FULLWIDTH_TABLE)

    for abbr, full in _ABBREVIATIONS.items():
        # 単語境界を見て "CVTEST" のような別単語を巻き込まないようにする。
        text = re.sub(r"\b" + abbr + r"\b", full, text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess(input_csv: str, output_dir: str):
    input_path = Path(input_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("loading csv: %s", input_path)
    df = pd.read_csv(input_path)

    if "text" in df.columns:
        logger.info("cleaning text column")
        df["text"] = df["text"].apply(lambda x: clean_text(str(x)) if pd.notna(x) else x)

    documents = df.to_dict("records")
    logger.info("loaded documents: %d", len(documents))

    chunker = TextChunker(chunk_size=500, chunk_overlap=50)
    logger.info("chunking documents")
    chunks = chunker.chunk_documents(documents, text_field="text", doc_id_field="doc_id")

    chunks_file = output_path / "chunks.jsonl"
    chunker.save_chunks(chunks, chunks_file)
    logger.info("saved chunks: %d -> %s", len(chunks), chunks_file)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/demo/demo_logs.csv")
    parser.add_argument("--output", default="data/processed")
    args = parser.parse_args()

    preprocess(args.input, args.output)
