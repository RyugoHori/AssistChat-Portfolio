"""テキストのチャンク分割。日本語の文末（。！？）を区切り位置とする。"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """ドキュメントのチャンク。Embedding に適したサイズの単位。"""

    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    chunk_index: int
    doc_id: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
            "doc_id": self.doc_id,
        }


class TextChunker:
    """テキストを固定長（既定 500 字）でチャンクに分割する。

    保全記録は 200-500 字が多く、短文なら 1 文書 1 チャンクに収まる想定。
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        self.sentence_endings = ["。", "！", "？", "\n"]

    def chunk_text(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """テキストを文末区切り優先で chunk_size 以下に切り分ける。"""
        if not text:
            return []

        if doc_id is None:
            doc_id = self._generate_doc_id(text)
        if metadata is None:
            metadata = {}

        chunks: List[Chunk] = []
        sentences = self._split_sentences(text)

        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            potential_chunk = current_chunk + sentence

            if current_chunk and len(potential_chunk) > self.chunk_size:
                if current_chunk:
                    self._add_chunk(chunks, current_chunk, doc_id, metadata, chunk_index)
                    chunk_index += 1

                    # 前チャンク末尾を次チャンク先頭にオーバーラップさせ、文脈切れを緩和する。
                    if self.chunk_overlap > 0:
                        overlap_text = self._get_overlap(current_chunk)
                        current_chunk = overlap_text + sentence
                    else:
                        current_chunk = sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk = potential_chunk

        if current_chunk:
            self._add_chunk(chunks, current_chunk, doc_id, metadata, chunk_index)

        return chunks

    def _add_chunk(self, chunks, text, doc_id, metadata, index):
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}_chunk_{index}",
                text=text.strip(),
                metadata={**metadata, "chunk_index": index},
                chunk_index=index,
                doc_id=doc_id,
            )
        )

    def _split_sentences(self, text: str) -> List[str]:
        pattern = "|".join(re.escape(ending) for ending in self.sentence_endings)
        sentences = re.split(f"({pattern})", text)

        result = []
        current = ""
        for part in sentences:
            if part in self.sentence_endings:
                current += part
                result.append(current)
                current = ""
            else:
                current = part
        if current:
            result.append(current)
        return [s for s in result if s.strip()]

    def _get_overlap(self, text: str) -> str:
        if len(text) <= self.chunk_overlap:
            return text
        return text[len(text) - self.chunk_overlap:]

    def _generate_doc_id(self, text: str) -> str:
        hash_obj = hashlib.md5(text[:100].encode())
        return f"doc_{hash_obj.hexdigest()[:8]}"

    def chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        text_field: str = "text",
        doc_id_field: str = "doc_id",
    ) -> List[Chunk]:
        all_chunks = []
        for doc in documents:
            text = doc.get(text_field, "")
            doc_id = doc.get(doc_id_field, self._generate_doc_id(text))
            metadata = {k: v for k, v in doc.items() if k != text_field}
            all_chunks.extend(self.chunk_text(text, doc_id, metadata))

        logger.info("chunked %d docs -> %d chunks", len(documents), len(all_chunks))
        return all_chunks

    def save_chunks(
        self,
        chunks: List[Chunk],
        filepath: Path,
        format: str = "jsonl",
    ):
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if format == "jsonl":
            with open(filepath, "w", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
