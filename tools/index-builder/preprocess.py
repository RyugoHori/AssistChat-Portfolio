"""CSV をチャンク分割し JSONL に落とす前処理スクリプト。"""

import logging
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.chunking import TextChunker
from rag_core.normalize import normalize_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def preprocess(input_csv: str, output_dir: str):
    input_path = Path(input_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("loading csv: %s", input_path)
    df = pd.read_csv(input_path)

    if "text" in df.columns:
        logger.info("cleaning text column")
        # 検索側と同じ正規化。索引だけ整えると、質問の全角や略語が一致しなくなる。
        df["text"] = df["text"].apply(lambda x: normalize_text(str(x)) if pd.notna(x) else x)

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
