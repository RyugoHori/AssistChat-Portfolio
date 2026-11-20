"""索引とクエリで共有する正規化のテスト。"""

from rag_core.normalize import normalize_text


def test_fullwidth_abbreviation_and_whitespace():
    """全角英数、単語として独立した略語、空白。"""
    assert normalize_text("ＡＬＭ１１０２") == "ALM1102"
    assert normalize_text("CV 停止") == "コンベア 停止"
    assert normalize_text("  a   b  ") == "a b"


def test_abbreviation_next_to_japanese():
    """日本語に続く略語と、辞書に足した INV。"""
    assert normalize_text("CVが停止") == "コンベアが停止"
    assert normalize_text("ベルトCVの異音") == "ベルトコンベアの異音"
    assert normalize_text("INVが停止") == "インバータが停止"
