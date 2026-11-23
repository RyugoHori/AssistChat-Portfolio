"""
tools/generate_demo_data.py のテスト
乱数で生成する項目は300件で確かめる
"""

from __future__ import annotations

import copy
import csv
import importlib
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

_TOOLS_ROOT = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(_TOOLS_ROOT))

gen = importlib.import_module("generate_demo_data")

MODES_YAML = _TOOLS_ROOT / "failure_modes.yaml"


def _generate(seed: int = 42) -> list:
    data = gen.load_modes(MODES_YAML)
    return gen.generate_records(data, 300, seed, date(2021, 1, 1), date(2025, 12, 31))


def test_same_seed_gives_same_records():
    assert _generate() == _generate()


def test_every_equipment2_has_two_or_more_modes():
    data = gen.load_modes(MODES_YAML)
    counts = Counter(eq2 for mode in data["modes"] for eq2 in mode["equipment2"])
    assert [eq2 for eq2 in gen.all_equipment2() if counts[eq2] < 2] == []


def test_recurrence_picks_from_unit_history(monkeypatch):
    """必ず再発させたとき、同じ個体の2件目以降がすべて、その個体で過去に起きたモードになる。"""
    # 確率0.4のままだと、偶然同じモードを選んだ分でも通ってしまい、再発の処理が壊れていても気づけない
    monkeypatch.setattr(gen, "RECUR_PROB", 1.0)
    histories: dict = {}
    checked = 0
    for record in _generate():
        history = histories.setdefault((record["line"], record["equipment3"]), [])
        if history:
            assert record["mode_id"] in history, record["doc_id"]
            checked += 1
        history.append(record["mode_id"])
    assert checked > 0


def test_csv_columns(tmp_path):
    output = tmp_path / "demo_logs.csv"
    gen.write_csv(_generate(), output)
    with open(output, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))
    assert header == [
        "doc_id",
        "source_number",
        "work_type",
        "date",
        "location",
        "line",
        "category",
        "equipment1",
        "equipment2",
        "equipment3",
        "equipment_full",
        "work_duration_minutes",
        "downtime_minutes",
        "symptom",
        "root_cause",
        "action_taken",
        "prevention",
        "text",
        "cause_category",
    ]


def test_style_does_not_leave_long_vowel_after_letter():
    """「インバーター」が略称の置換で「INVー」になるような崩れがないかを、全部の組み合わせで見る。"""
    data = gen.load_modes(MODES_YAML)
    broken = []
    for mode in data["modes"]:
        for eq2 in mode["equipment2"]:
            for template in mode["symptoms"] + [mode["cause"], mode["action"]]:
                text = gen.fill(template, eq2, mode.get("error_code", ""), "1")
                for style in data["writer_styles"]:
                    styled = gen.apply_style(text, style)
                    if re.search(r"[A-Za-zＡ-Ｚａ-ｚ]ー", styled):
                        broken.append((mode["id"], style["name"], styled))
    assert broken == []


def test_validate_modes_rejects_broken_yaml():
    """故障モード辞書を壊したときに、検査で止まることを確かめる。"""
    data = gen.load_modes(MODES_YAML)

    def first_with(d: dict, key: str) -> dict:
        return next(mode for mode in d["modes"] if mode.get(key))

    def second_with(d: dict, key: str) -> dict:
        return [mode for mode in d["modes"] if mode.get(key)][1]

    cases = [
        (lambda d: d["modes"][0].update(equipment2=["存在しない設備"]), "EQUIPMENT_TREEにない設備名"),
        (lambda d: d["modes"][0].update(cause_category="存在しない分類"), "原因分類の一覧にない"),
        (lambda d: first_with(d, "error_code").pop("error_code"), "error_codeがない"),
        (lambda d: first_with(d, "values").pop("values"), "valuesがない"),
        (
            lambda d: d.update(modes=[m for m in d["modes"] if "ローラーコンベア" not in m["equipment2"]]),
            "故障モードが2つ未満",
        ),
        (lambda d: d["modes"][1].update(id=d["modes"][0]["id"]), "idが重複"),
        (
            lambda d: second_with(d, "error_code").update(error_code=first_with(d, "error_code")["error_code"]),
            "error_codeが重複",
        ),
    ]
    for break_data, message in cases:
        broken = copy.deepcopy(data)
        break_data(broken)
        with pytest.raises(ValueError, match=message):
            gen.validate_modes(broken)
