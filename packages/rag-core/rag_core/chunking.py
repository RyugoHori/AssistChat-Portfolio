"""
テキストのチャンク分割

長い文書を検索しやすいサイズに分割する。
日本語の文末（。！？）で区切るようにしてる。
"""

import logging
import re
import hashlib
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    """チャンク（文書の断片）"""
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
            "doc_id": self.doc_id
        }

class TextChunker:
    """
    テキストをチャンクに分割するやつ
    
    chunk_size=500、overlap=50 がデフォルト。
    保全記録は1件あたり200〜500文字くらいなので、
    ほとんどの場合1文書=1チャンクになる。
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        # 日本語の文末
        self.sentence_endings = ["。", "！", "？", "\n"]
    
    def chunk_text(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """テキストをチャンクに分割"""
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
            
            # チャンクサイズを超えたら保存して次へ
            if current_chunk and len(potential_chunk) > self.chunk_size:
                if current_chunk:
                    self._add_chunk(chunks, current_chunk, doc_id, metadata, chunk_index)
                    chunk_index += 1
                    
                    # オーバーラップ（前のチャンクの末尾を次のチャンクの先頭に含める）
                    if self.chunk_overlap > 0:
                        overlap_text = self._get_overlap(current_chunk)
                        current_chunk = overlap_text + sentence
                    else:
                        current_chunk = sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk = potential_chunk
        
        # 最後のチャンクを保存
        if current_chunk:
            self._add_chunk(chunks, current_chunk, doc_id, metadata, chunk_index)
            
        return chunks

    def _add_chunk(self, chunks, text, doc_id, metadata, index):
        chunk_id = f"{doc_id}_chunk_{index}"
        chunks.append(Chunk(
            chunk_id=chunk_id,
            text=text.strip(),
            metadata={**metadata, "chunk_index": index},
            chunk_index=index,
            doc_id=doc_id
        ))
    
    def _split_sentences(self, text: str) -> List[str]:
        """文に分割（日本語対応）"""
        pattern = '|'.join(re.escape(ending) for ending in self.sentence_endings)
        sentences = re.split(f'({pattern})', text)
        
        # 分割された文末記号を文に結合
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
        """オーバーラップ部分を取得"""
        if len(text) <= self.chunk_overlap:
            return text
        return text[len(text) - self.chunk_overlap:]
    
    def _generate_doc_id(self, text: str) -> str:
        """テキストからドキュメントIDを生成"""
        text_sample = text[:100]
        hash_obj = hashlib.md5(text_sample.encode())
        return f"doc_{hash_obj.hexdigest()[:8]}"

    def chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        text_field: str = "text",
        doc_id_field: str = "doc_id"
    ) -> List[Chunk]:
        """複数文書をまとめてチャンク化"""
        all_chunks = []
        for doc in documents:
            text = doc.get(text_field, "")
            doc_id = doc.get(doc_id_field, self._generate_doc_id(text))
            
            # text以外のフィールドはメタデータとして保持
            metadata = {k: v for k, v in doc.items() if k != text_field}
            
            chunks = self.chunk_text(text, doc_id, metadata)
            all_chunks.extend(chunks)
        
        logger.info(f"{len(documents)}件のドキュメントを{len(all_chunks)}個のチャンクに分割しました")
        return all_chunks

    def save_chunks(
        self,
        chunks: List[Chunk],
        filepath: Path,
        format: str = "jsonl"
    ):
        """チャンクをファイルに保存"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "jsonl":
            with open(filepath, 'w', encoding='utf-8') as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + '\n')
