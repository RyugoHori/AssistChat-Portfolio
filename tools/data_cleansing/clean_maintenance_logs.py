"""
保全記録データクレンジングパイプライン

本番の保全記録（手書きOCR・表記揺れ・略語混在）を検索用コーパスに整える。

パイプライン:
    load → normalize_unicode → normalize_dates → canonicalize_equipment
         → correct_ocr_errors → filter_quality → deduplicate → save

使い方:
    python clean_maintenance_logs.py \\
        --input dirty_sample.csv \\
        --output cleaned_sample.csv \\
        --dictionary equipment_dictionary.yaml \\
        --report cleansing_report.json

設計上の注意:
    - 除外レコードは `excluded.csv` に保存し、現場フィードバックに活用できる
    - 辞書は単一の Source of Truth（YAML）に寄せてコードからハードコーディングを排除
    - パイプライン各段階は単体テスト可能な pure function として分離
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

logger = logging.getLogger("cleansing")



@dataclass
class CleansingReport:
    """クレンジング結果のサマリー"""

    input_count: int = 0
    output_count: int = 0
    excluded_reasons: Dict[str, int] = field(default_factory=dict)
    corrections: Dict[str, int] = field(default_factory=dict)

    def add_exclusion(self, reason: str) -> None:
        self.excluded_reasons[reason] = self.excluded_reasons.get(reason, 0) + 1

    def add_correction(self, kind: str) -> None:
        self.corrections[kind] = self.corrections.get(kind, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        total_excluded = sum(self.excluded_reasons.values())
        rate = total_excluded / self.input_count if self.input_count else 0.0
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "excluded_count": total_excluded,
            "exclusion_rate": round(rate, 4),
            "excluded_reasons": self.excluded_reasons,
            "corrections": self.corrections,
        }

    def pretty_print(self) -> None:
        total = sum(self.excluded_reasons.values())
        rate = total / self.input_count * 100 if self.input_count else 0.0
        print("\n" + "=" * 68)
        print(" データクレンジングレポート")
        print("=" * 68)
        print(
            f"入力: {self.input_count} 件 → 出力: {self.output_count} 件"
            f"（{total} 件除外 / 除外率 {rate:.1f}%）"
        )
        if self.excluded_reasons:
            print("\n除外理由の内訳:")
            for reason, count in sorted(self.excluded_reasons.items(), key=lambda x: -x[1]):
                sub_rate = count / self.input_count * 100 if self.input_count else 0.0
                print(f"  {reason:<28}: {count:>3} 件 ({sub_rate:>4.1f}%)")
        if self.corrections:
            print("\n表記揺れ補正:")
            for kind, count in sorted(self.corrections.items(), key=lambda x: -x[1]):
                print(f"  {kind:<28}: {count:>3} 件")
        print("=" * 68 + "\n")



def normalize_unicode(text: str) -> str:
    """
    全角英数・カタカナを半角へ NFKC 正規化

    「ＮＣ旋盤」「ｎｃ旋盤」→「NC旋盤」
    """
    if not isinstance(text, str):
        return text
    return unicodedata.normalize("NFKC", text).strip()


_WAREKI_ERAS = {
    "令和": 2018,
    "R": 2018,
    "平成": 1988,
    "H": 1988,
    "昭和": 1925,
    "S": 1925,
}


def parse_flexible_date(raw: Any) -> Optional[str]:
    """
    多様な日付フォーマットを ISO 8601 (YYYY-MM-DD) に統一

    サポート形式:
        - 2024-01-05 / 2024/01/05 / 2024.01.05
        - 令和6年1月5日 / R6.1.5
        - 2024/1/5（0埋めなし）
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    s = normalize_unicode(s)

    # 和暦パターン: 「令和6年1月5日」「R6.1.5」
    wareki_match = re.match(
        r"(令和|平成|昭和|R|H|S)(\d{1,2})[年./](\d{1,2})[月./](\d{1,2})日?",
        s,
    )
    if wareki_match:
        era, y, m, d = wareki_match.groups()
        base = _WAREKI_ERAS.get(era)
        if base is None:
            return None
        year = base + int(y)
        try:
            return f"{year:04d}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            return None

    # 西暦パターン: 2024/1/5, 2024-01-05, 2024.01.05
    seireki_match = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if seireki_match:
        y, m, d = seireki_match.groups()
        try:
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            return None

    return None


def build_equipment_normalizer(
    dictionary: Dict[str, Any],
) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    設備名辞書を「alias → canonical」のマップに変換

    長い alias から優先的に置換できるよう長さ順に並べる。
    """
    alias_to_canonical: Dict[str, str] = {}
    for entry in dictionary.get("equipment", []):
        canonical = entry["canonical"]
        alias_to_canonical[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_to_canonical[alias.lower()] = canonical

    # 長い alias から先にマッチさせる（部分一致の誤置換を防ぐ）
    sorted_aliases = sorted(alias_to_canonical.keys(), key=len, reverse=True)
    rules = [(a, alias_to_canonical[a]) for a in sorted_aliases]
    ocr_corrections = dictionary.get("ocr_corrections", [])
    return dict(rules), ocr_corrections


def canonicalize_equipment(
    text: str,
    alias_to_canonical: Dict[str, str],
) -> Tuple[str, int]:
    """
    テキスト中の設備名別名を正準名に置換

    Returns:
        (正準化後のテキスト, 置換回数)
    """
    if not isinstance(text, str) or not text:
        return text, 0

    replaced = 0
    # 長い alias から順に置換
    for alias, canonical in sorted(alias_to_canonical.items(), key=lambda x: -len(x[0])):
        if alias == canonical.lower():
            continue  # 自身への置換はスキップ
        # 大文字小文字を無視した単純置換（単語境界は日本語では曖昧なため使わない）
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        new_text, n = pattern.subn(canonical, text)
        if n > 0:
            replaced += n
            text = new_text
    return text, replaced


def correct_ocr_errors(text: str) -> Tuple[str, int]:
    """
    OCR 由来の典型的な誤認識を軽量に補正

    文脈条件（前後文字）を考慮する単純な実装。
    積極的な補正は誤補正リスクが高いため、明らかなカタカナ語内の漢字誤認だけを対象にする。
    """
    if not isinstance(text, str):
        return text, 0

    corrections = 0

    # 漢字「力/口/工/才/二/夕/卜」がカタカナ語の中に混入しているケースを補正
    # カタカナの前後にある場合のみ置換する
    substitutions = [
        ("力", "カ"),
        ("口", "ロ"),
        ("工", "エ"),
        ("才", "オ"),
        ("二", "ニ"),
        ("夕", "タ"),
        ("卜", "ト"),
    ]
    for src, dst in substitutions:
        pattern = re.compile(f"(?<=[ァ-ヶー]){re.escape(src)}|{re.escape(src)}(?=[ァ-ヶー])")
        new_text, n = pattern.subn(dst, text)
        if n > 0:
            corrections += n
            text = new_text

    return text, corrections


def passes_quality_check(
    row: Dict[str, Any],
    min_text_length: int = 20,
) -> Tuple[bool, str]:
    """
    品質フィルタ

    - 症状 + 対処 が min_text_length 文字未満 → 除外
    - 文字エントロピー（ユニーク文字数 / 総文字数）が低い → 除外（連続文字の攻撃）
    - 必須カラム欠損 → 除外
    """
    required = ("equipment1", "equipment2", "equipment3", "line", "location")
    for col in required:
        if not row.get(col) or str(row[col]).strip() == "":
            return False, "必須カラム欠損"

    symptom = str(row.get("symptom") or "").strip()
    action = str(row.get("action_taken") or "").strip()
    combined = symptom + action

    if len(combined) < min_text_length:
        return False, "品質不足（文字数不足）"

    # ユニーク率が 0.3 未満 → 同じ文字の繰り返しとみなす（「あああ」「OKOK」等）
    unique_ratio = len(set(combined)) / len(combined)
    if unique_ratio < 0.3:
        return False, "品質不足（エントロピー低）"

    return True, ""


def is_japanese_content(text: str, min_ja_ratio: float = 0.3) -> bool:
    """
    テキストに日本語（ひらがな/カタカナ/漢字）が一定割合含まれるかを判定

    `langdetect` を使わない軽量実装。誤字・略語を含む保全記録でも安定動作する。
    """
    if not isinstance(text, str) or not text:
        return False
    ja_chars = re.findall(r"[ぁ-んァ-ヶ一-龥]", text)
    total = len(text.replace(" ", "").replace("　", ""))
    if total == 0:
        return False
    return len(ja_chars) / total >= min_ja_ratio


def compute_record_hash(row: Dict[str, Any]) -> str:
    """完全一致重複検出用ハッシュ（日付・設備・症状・対処）"""
    key = "|".join([
        str(row.get("date", "")),
        str(row.get("equipment3", "")),
        str(row.get("symptom", "")),
        str(row.get("action_taken", "")),
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def compute_shingle_set(text: str, shingle_size: int = 3) -> set:
    """
    近似重複検出用のシングル集合（簡易 MinHash 代替）

    本番では datasketch.MinHash を使うが、ポートフォリオでは
    依存を増やさないため純 Python の Jaccard 類似度で近似する。
    """
    text = re.sub(r"\s+", "", text)
    if len(text) < shingle_size:
        return {text}
    return {text[i : i + shingle_size] for i in range(len(text) - shingle_size + 1)}


def jaccard_similarity(a: set, b: set) -> float:
    """Jaccard 類似度"""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0



class MaintenanceLogCleanser:
    """保全記録クレンジングパイプライン"""

    def __init__(
        self,
        dictionary_path: Path,
        min_text_length: int = 20,
        near_duplicate_threshold: float = 0.85,
    ):
        with open(dictionary_path, "r", encoding="utf-8") as f:
            dictionary = yaml.safe_load(f)

        self.alias_to_canonical, _ = build_equipment_normalizer(dictionary)
        self.min_text_length = min_text_length
        self.near_duplicate_threshold = near_duplicate_threshold
        self.report = CleansingReport()

    def run(
        self,
        input_path: Path,
        output_path: Path,
        excluded_path: Optional[Path] = None,
    ) -> CleansingReport:
        """パイプラインを実行して結果を保存"""
        df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
        self.report.input_count = len(df)
        logger.info("入力 %d 件を読み込みました: %s", len(df), input_path)

        records = df.to_dict(orient="records")
        cleaned: List[Dict[str, Any]] = []
        excluded: List[Dict[str, Any]] = []
        seen_hashes: set = set()
        shingle_index: List[Tuple[set, str]] = []  # (shingles, doc_id)

        for row in records:
            doc_id = row.get("doc_id", "?")

            # 1. Unicode 正規化（全フィールド）
            for key, value in list(row.items()):
                if isinstance(value, str):
                    row[key] = normalize_unicode(value)

            # 2. 日付統一
            original_date = row.get("date", "")
            parsed_date = parse_flexible_date(original_date)
            if original_date and parsed_date is None:
                self.report.add_exclusion("日付パース不可")
                excluded.append({**row, "_exclude_reason": "日付パース不可"})
                logger.debug("除外[日付]: %s raw=%r", doc_id, original_date)
                continue
            row["date"] = parsed_date or ""

            # 3. 設備名正準化
            for col in ("equipment1", "equipment2", "equipment3", "symptom", "action_taken"):
                text = row.get(col, "")
                if text:
                    new_text, n = canonicalize_equipment(text, self.alias_to_canonical)
                    if n > 0:
                        self.report.add_correction("設備名正準化")
                    row[col] = new_text

            # 4. OCR 誤認識補正
            for col in ("symptom", "action_taken"):
                text = row.get(col, "")
                if text:
                    new_text, n = correct_ocr_errors(text)
                    if n > 0:
                        self.report.add_correction("OCR エラー補正")
                    row[col] = new_text

            # 5. 品質フィルタ
            ok, reason = passes_quality_check(row, self.min_text_length)
            if not ok:
                self.report.add_exclusion(reason)
                excluded.append({**row, "_exclude_reason": reason})
                logger.debug("除外[品質]: %s reason=%s", doc_id, reason)
                continue

            # 6. 日本語判定
            combined_text = f"{row.get('symptom', '')} {row.get('action_taken', '')}"
            if not is_japanese_content(combined_text):
                self.report.add_exclusion("言語判定失敗")
                excluded.append({**row, "_exclude_reason": "言語判定失敗"})
                logger.debug("除外[言語]: %s", doc_id)
                continue

            # 7. 重複排除（完全一致）
            record_hash = compute_record_hash(row)
            if record_hash in seen_hashes:
                self.report.add_exclusion("重複（完全一致）")
                excluded.append({**row, "_exclude_reason": "重複（完全一致）"})
                logger.debug("除外[完全重複]: %s", doc_id)
                continue
            seen_hashes.add(record_hash)

            # 8. 重複排除（近似）
            shingles = compute_shingle_set(combined_text)
            is_near_duplicate = any(
                jaccard_similarity(shingles, existing) >= self.near_duplicate_threshold
                for existing, _ in shingle_index
            )
            if is_near_duplicate:
                self.report.add_exclusion("重複（近似）")
                excluded.append({**row, "_exclude_reason": "重複（近似）"})
                logger.debug("除外[近似重複]: %s", doc_id)
                continue
            shingle_index.append((shingles, doc_id))

            cleaned.append(row)

        self.report.output_count = len(cleaned)

        # 保存
        pd.DataFrame(cleaned).to_csv(output_path, index=False, encoding="utf-8")
        logger.info("出力 %d 件を保存しました: %s", len(cleaned), output_path)

        if excluded_path is not None and excluded:
            pd.DataFrame(excluded).to_csv(excluded_path, index=False, encoding="utf-8")
            logger.info("除外 %d 件を保存しました: %s", len(excluded), excluded_path)

        return self.report



def main():
    parser = argparse.ArgumentParser(description="保全記録データクレンジング")
    parser.add_argument("--input", type=Path, required=True, help="入力 CSV")
    parser.add_argument("--output", type=Path, required=True, help="出力 CSV（クレンジング済み）")
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path(__file__).parent / "equipment_dictionary.yaml",
        help="設備名正準化辞書 (YAML)",
    )
    parser.add_argument(
        "--excluded",
        type=Path,
        default=None,
        help="除外レコードの出力先 CSV（指定しない場合は保存しない）",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="レポート JSON の出力先",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=20,
        help="品質フィルタの最小文字数（症状+対処）",
    )
    parser.add_argument(
        "--near-dup-threshold",
        type=float,
        default=0.85,
        help="近似重複の Jaccard 閾値",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG ログを出力",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    cleanser = MaintenanceLogCleanser(
        dictionary_path=args.dictionary,
        min_text_length=args.min_length,
        near_duplicate_threshold=args.near_dup_threshold,
    )
    report = cleanser.run(
        input_path=args.input,
        output_path=args.output,
        excluded_path=args.excluded,
    )
    report.pretty_print()

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("レポートを保存しました: %s", args.report)


if __name__ == "__main__":
    main()
