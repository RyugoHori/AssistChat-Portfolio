"""
日本語トークナイザー

MeCabで形態素解析してる。
WindowsのローカルでMeCab動かすの大変だったのでDocker使うことにした。
"""

import MeCab
import unidic_lite
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class TokenizerService:
    """
    日本語トークナイザー（シングルトン）
    
    MeCab + unidic-lite を使用。
    最初はJanomeも試したけど、MeCabの方が速かった。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, system_dic_path: Optional[str] = None):
        if hasattr(self, 'tagger'):
            return
            
        try:
            # unidic-liteの辞書を使う
            # Windowsだとパス解決で問題が起きることがあったので明示的に指定
            dic_path = system_dic_path or unidic_lite.DICDIR
            
            # パスにスペースが含まれてるとエラーになるので
            # ダブルクォートで囲む（Program Filesとか）
            tagger_args = f'-d "{dic_path}"'
            self.tagger = MeCab.Tagger(tagger_args)
            logger.info(f"MeCabトークナイザーの初期化に成功しました: {tagger_args}")
        except RuntimeError as e:
            logger.error(
                f"MeCabの初期化に失敗しました。MeCabと辞書（unidic-liteなど）がインストールされているか確認してください。エラー: {e}"
            )
            logger.warning("フォールバック: シンプルな空白区切りトークナイザーを使用します。")
            self.tagger = None

    def tokenize(self, text: str) -> List[str]:
        """
        テキストをトークンに分割
        
        名詞・動詞・形容詞・副詞だけ抽出して、原形に正規化する。
        「動いた」→「動く」みたいに。
        助詞とか助動詞は検索ノイズになるので除外。
        """
        if not self.tagger:
            # MeCabが使えない場合はスペースで分割（フォールバック）
            return text.split() if text else []

        if not text or not isinstance(text, str):
            return []

        node = self.tagger.parseToNode(text)
        tokens = []
        
        while node:
            # BOS/EOSノードはスキップ
            if node.surface == "":
                node = node.next
                continue
                
            features = node.feature.split(',')
            pos = features[0] if len(features) > 0 else ""
            
            # 原形があればそれを使う、なければ表層形
            base_form = features[6] if len(features) > 6 and features[6] != '*' else node.surface
            
            # 検索に有用な品詞だけ抽出
            if pos.startswith(('名詞', '動詞', '形容詞', '副詞')):
                tokens.append(base_form)
                
            node = node.next
        
        return tokens

# シングルトンインスタンス
tokenizer = TokenizerService()
