"""MeCab + unidic-lite による日本語トークナイザー（シングルトン）。"""

import logging
from typing import List, Optional

import MeCab
import unidic_lite

logger = logging.getLogger(__name__)


class TokenizerService:
    """名詞・動詞・形容詞・副詞だけを語彙素で返す。読みだと「異音」と「イオン」が同じ単語になるので、語彙素を使う。助詞助動詞は検索ノイズなので除外。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, system_dic_path: Optional[str] = None):
        if hasattr(self, "tagger"):
            return

        try:
            # Windows の "Program Files" 等スペース入りパスでも動くようクォートして渡す。
            dic_path = system_dic_path or unidic_lite.DICDIR
            tagger_args = f'-d "{dic_path}"'
            self.tagger = MeCab.Tagger(tagger_args)
            logger.info("MeCab ready: %s", tagger_args)
        except RuntimeError as e:
            logger.error("MeCab init failed, falling back to whitespace split: %s", e)
            self.tagger = None

    def tokenize(self, text: str) -> List[str]:
        if not self.tagger:
            return text.split() if text else []

        if not text or not isinstance(text, str):
            return []

        node = self.tagger.parseToNode(text)
        tokens: List[str] = []

        while node:
            if node.surface == "":
                node = node.next
                continue

            features = node.feature.split(",")
            pos = features[0] if features else ""
            # unidic-lite の features[6] は語彙素の読み。「異音」が「イオン」、「停止」が「テイシ」になる。
            # 同じ読みの別の語を区別するため、語彙素（features[7]）を使う。* のときは表層形。
            lemma = features[7] if len(features) > 7 and features[7] != "*" else node.surface
            # 外来語の語彙素は「モーター-motor」のように英語の注記が付く。英字の注記だけ外す。
            head, sep, tail = lemma.partition("-")
            if sep and tail.isascii() and tail.isalpha():
                lemma = head

            if pos.startswith(("名詞", "動詞", "形容詞", "副詞")):
                tokens.append(lemma)

            node = node.next

        return tokens


tokenizer = TokenizerService()
