"""索引の文と検索の質問で共有する正規化。"""

import re

_ABBREVIATIONS = {
    "CV": "コンベア",
    "MTR": "モーター",
    "PMP": "ポンプ",
    "CYL": "シリンダー",
    "BRG": "ベアリング",
    "INV": "インバータ",
}

_FULLWIDTH_TABLE = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
)


def normalize_text(text: str) -> str:
    """索引とクエリの両方にかける正規化。片方だけにかけると表記揺れで一致しなくなるため、共通化する。"""
    text = text.translate(_FULLWIDTH_TABLE)

    for abbr, full in _ABBREVIATIONS.items():
        # \b は日本語も単語の一部とみなすので、「CVが停止」の CV が展開されない。
        # 英数字以外を区切りと見て、CVTEST のような別の英数字の並びは巻き込まない。
        text = re.sub(
            r"(?<![A-Za-z0-9])" + abbr + r"(?![A-Za-z0-9])",
            full,
            text,
        )

    text = re.sub(r"\s+", " ", text).strip()
    return text
