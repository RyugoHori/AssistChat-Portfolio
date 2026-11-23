"""語彙素で返すトークナイザーのテスト。"""

from rag_core.tokenization import tokenizer


def test_lemma_not_reading_and_english_note_removed():
    """同じ読みの別の語を区別し、外来語の英語の注記を外す。"""
    tokens = tokenizer.tokenize("異音")
    assert "異音" in tokens
    assert "イオン" not in tokens
    assert tokenizer.tokenize("モーター") == ["モーター"]
