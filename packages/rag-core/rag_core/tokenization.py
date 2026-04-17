"""MeCab + unidic-lite による日本語トークナイザー（シングルトン）。"""

import logging
from typing import List, Optional

import MeCab
import unidic_lite

logger = logging.getLogger(__name__)


class TokenizerService:
    """名詞・動詞・形容詞・副詞のみ原形で返す。助詞助動詞は検索ノイズなので除外。"""

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
            base_form = features[6] if len(features) > 6 and features[6] != "*" else node.surface

            if pos.startswith(("名詞", "動詞", "形容詞", "副詞")):
                tokens.append(base_form)

            node = node.next

        return tokens


tokenizer = TokenizerService()
