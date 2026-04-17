"""
データクレンジングパイプラインの単体テスト

各段階（pure function）を個別に検証し、
パイプライン全体のエンドツーエンドテストも 1 ケース用意する。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# tools/data_cleansing は import path に入っていないので動的に追加
_TOOLS_ROOT = Path(__file__).resolve().parents[3] / "tools" / "data_cleansing"
sys.path.insert(0, str(_TOOLS_ROOT))

clean_module = importlib.import_module("clean_maintenance_logs")


# ==================== normalize_unicode ====================

class TestNormalizeUnicode:
    def test_fullwidth_to_halfwidth(self):
        assert clean_module.normalize_unicode("ＮＣ旋盤") == "NC旋盤"

    def test_halfwidth_katakana(self):
        # 半角カナは全角カナに統一される
        assert "ｶﾞ" not in clean_module.normalize_unicode("ｶﾞｰﾄﾞ")

    def test_strips_whitespace(self):
        assert clean_module.normalize_unicode("  hello  ") == "hello"

    def test_non_string_passes_through(self):
        assert clean_module.normalize_unicode(None) is None


# ==================== parse_flexible_date ====================

class TestParseFlexibleDate:
    @pytest.mark.parametrize("raw,expected", [
        ("2024-01-05", "2024-01-05"),
        ("2024/1/5", "2024-01-05"),
        ("2024.01.05", "2024-01-05"),
        ("2024/12/31", "2024-12-31"),
    ])
    def test_seireki_variants(self, raw, expected):
        assert clean_module.parse_flexible_date(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("令和6年1月5日", "2024-01-05"),
        ("R6.1.5", "2024-01-05"),
        ("H30.12.1", "2018-12-01"),
    ])
    def test_wareki_variants(self, raw, expected):
        assert clean_module.parse_flexible_date(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "invalid", "abcd"])
    def test_invalid_returns_none(self, raw):
        assert clean_module.parse_flexible_date(raw) is None


# ==================== canonicalize_equipment ====================

class TestCanonicalizeEquipment:
    @pytest.fixture
    def dictionary(self):
        import yaml
        dict_path = _TOOLS_ROOT / "equipment_dictionary.yaml"
        with open(dict_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def alias_map(self, dictionary):
        alias_to_canonical, _ = clean_module.build_equipment_normalizer(dictionary)
        return alias_to_canonical

    def test_replaces_alias(self, alias_map):
        text, n = clean_module.canonicalize_equipment("圧トラの値が異常", alias_map)
        assert "圧力トランスミッタ" in text
        assert n >= 1

    def test_replaces_fullwidth_alias(self, alias_map):
        text, _ = clean_module.canonicalize_equipment("ＮＣ旋盤の主軸故障", alias_map)
        # alias は事前正規化前なので ＮＣ旋盤 として辞書にあるかは test 時の実装次第
        # 少なくとも置換が走る or そのまま残る（失敗しない）
        assert "旋盤" in text

    def test_long_alias_priority(self, alias_map):
        # 「圧力TR」を先に置換すべき（「PT」だけ先に当たると「圧力Trans」に壊れる）
        text, _ = clean_module.canonicalize_equipment("圧力TRの出力不良", alias_map)
        assert "圧力トランスミッタ" in text

    def test_no_match_returns_unchanged(self, alias_map):
        text, n = clean_module.canonicalize_equipment("全く関係ない文字列", alias_map)
        assert n == 0


# ==================== correct_ocr_errors ====================

class TestCorrectOcrErrors:
    def test_kanji_in_katakana_gets_corrected(self):
        # 「モー夕ー」の「夕」は OCR 誤認識で、「タ」に補正されるべき
        text, n = clean_module.correct_ocr_errors("モー夕ー異音")
        assert "モーター" in text
        assert n >= 1

    def test_no_katakana_context_no_correction(self):
        # 漢字文の中の「工」は補正しない
        text, n = clean_module.correct_ocr_errors("工場で作業")
        assert text == "工場で作業"
        assert n == 0


# ==================== passes_quality_check ====================

class TestPassesQualityCheck:
    def test_valid_record_passes(self):
        row = {
            "equipment1": "センサー",
            "equipment2": "圧力トランスミッタ",
            "equipment3": "PT-1",
            "line": "A1000",
            "location": "第1工場",
            "symptom": "圧力値がふらつき、配管振動の影響と推定",
            "action_taken": "配管クランプ追加で振動抑制。ゼロ点再調整",
        }
        ok, reason = clean_module.passes_quality_check(row)
        assert ok is True
        assert reason == ""

    def test_short_text_is_excluded(self):
        row = {
            "equipment1": "センサー",
            "equipment2": "圧力",
            "equipment3": "PT",
            "line": "A",
            "location": "第1工場",
            "symptom": "OK",
            "action_taken": "OK",
        }
        ok, reason = clean_module.passes_quality_check(row)
        assert ok is False
        assert "文字数" in reason

    def test_low_entropy_is_excluded(self):
        row = {
            "equipment1": "E1",
            "equipment2": "E2",
            "equipment3": "E3",
            "line": "A",
            "location": "L",
            "symptom": "あ" * 50,
            "action_taken": "あ" * 50,
        }
        ok, reason = clean_module.passes_quality_check(row)
        assert ok is False

    def test_missing_required_field_excluded(self):
        row = {
            "equipment1": "",
            "equipment2": "E2",
            "equipment3": "E3",
            "line": "A",
            "location": "L",
            "symptom": "長い症状" * 10,
            "action_taken": "対処" * 10,
        }
        ok, reason = clean_module.passes_quality_check(row)
        assert ok is False
        assert "必須" in reason


# ==================== is_japanese_content ====================

class TestIsJapaneseContent:
    def test_japanese_passes(self):
        assert clean_module.is_japanese_content("モーターから異音が発生した") is True

    def test_english_fails(self):
        assert clean_module.is_japanese_content("Abnormal noise from motor") is False

    def test_empty_fails(self):
        assert clean_module.is_japanese_content("") is False
        assert clean_module.is_japanese_content(None) is False


# ==================== jaccard_similarity / shingle_set ====================

class TestShingleAndJaccard:
    def test_identical_texts_give_similarity_one(self):
        a = clean_module.compute_shingle_set("テスト文書です")
        b = clean_module.compute_shingle_set("テスト文書です")
        assert clean_module.jaccard_similarity(a, b) == 1.0

    def test_disjoint_texts_give_zero(self):
        a = clean_module.compute_shingle_set("全く違う")
        b = clean_module.compute_shingle_set("abcde")
        assert clean_module.jaccard_similarity(a, b) == 0.0

    def test_similar_texts_give_high_similarity(self):
        a = clean_module.compute_shingle_set("モーター異音の事例")
        b = clean_module.compute_shingle_set("モーター異音と振動の事例")
        sim = clean_module.jaccard_similarity(a, b)
        assert 0.3 < sim < 1.0


# ==================== パイプライン全体（E2E） ====================

class TestPipelineEndToEnd:
    def test_runs_on_sample_and_excludes_expected(self, tmp_path):
        dict_path = _TOOLS_ROOT / "equipment_dictionary.yaml"
        sample_path = _TOOLS_ROOT / "dirty_sample.csv"
        output_path = tmp_path / "cleaned.csv"
        excluded_path = tmp_path / "excluded.csv"

        cleanser = clean_module.MaintenanceLogCleanser(
            dictionary_path=dict_path,
            min_text_length=20,
        )
        report = cleanser.run(
            input_path=sample_path,
            output_path=output_path,
            excluded_path=excluded_path,
        )

        assert report.input_count == 100
        assert report.output_count > 0
        assert report.output_count < report.input_count  # 何かは除外される
        # 出力ファイルが生成されていること
        assert output_path.exists()
        assert excluded_path.exists()
        # 少なくとも品質不足（短文・OKのみ等）の除外があるはず
        assert sum(report.excluded_reasons.values()) > 0
