"""
デモデータの生成。
故障モード辞書（failure_modes.yaml）から、症状・原因・処置がそろった保全記録を作る。
工場 → ライン → 設備の階層は守る。
"""

import argparse
import csv
import logging
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)

TOOLS_DIR = Path(__file__).resolve().parent

# 工場とラインの対応関係
FACTORY_LINE_MAP = {
    "第1工場": ["A1000 生産ラインA", "A2000 生産ラインB"],
    "第2工場": ["B1000 組立ラインC", "B2000 組立ラインD"],
    "第3工場": ["C1000 検査ラインE"],
}

# ラインごとのカテゴリ（機械/電気）。どのラインにも両方の設備があるものとして簡略化してる
LINE_CATEGORY_MAP = {
    "A1000 生産ラインA": ["機械", "電気"],
    "A2000 生産ラインB": ["機械", "電気"],
    "B1000 組立ラインC": ["機械", "電気"],
    "B2000 組立ラインD": ["機械", "電気"],
    "C1000 検査ラインE": ["電気", "機械"],
}

# 設備の階層構造：カテゴリ → 設備1 → 設備2（一般的なガラス加工工場を想定した架空の構成）
EQUIPMENT_TREE = {
    "機械": {
        "切断設備": ["切断機", "折割機"],
        "加工設備": ["孔あけ機", "面取り機", "洗浄機"],
        "印刷設備": ["スクリーン印刷機", "乾燥炉"],
        "強化設備": ["加熱炉", "曲げ成形機", "風冷装置"],
        "搬送設備": ["ローラーコンベア", "ベルトコンベア", "移載ロボット", "吸着リフター"],
        "ユーティリティ": ["エアコンプレッサー", "冷却水ポンプ", "真空ポンプ", "集塵機"],
    },
    "電気": {
        "制御盤": ["主制御盤", "動力盤", "リモートI/O盤"],
        "センサー": ["光電センサー", "近接スイッチ", "熱電対", "放射温度計", "検査カメラ"],
        "駆動制御": ["インバータ", "サーボアンプ"],
        "通信機器": ["PLC CPUユニット", "タッチパネル(HMI)"],
    },
}

WORK_TYPES = ["修理票", "重大故障", "作業票", "連絡票"]
WORK_TYPE_WEIGHTS = [0.5, 0.1, 0.3, 0.1]

PREVENTIONS = [
    "",
    "定期点検項目への追加。",
    "保全カレンダーへの登録。",
    "オペレーターへの清掃指導。",
    "予備品の在庫発注点見直し。",
]

# API・画面・前処理が列名で参照しているので、既存の列は残して cause_category を末尾に足す
COLUMNS = [
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

# 同じ個体で同じ故障が繰り返し起きるのが保全記録の特徴。デモデータでも再発を残す。
# 評価Bは、過去の同じ設備・同じ原因の記録を正解にする。
RECUR_PROB = 0.4

# 個体ごとの故障しやすさを決めるパレート分布の形の値。一部の号機に故障が偏るのを再現する
PARETO_SHAPE = 2.0

# 設備種別だけ書く人と、号機まで書く人がいる。号機付きの名前でも同じ記録として引けるかを評価に含めるため
EQ3_PROB = 0.3

# 原因分類は人が選んで入力する項目なので、選び間違いや「とりあえずその他」が混ざる。
# 評価Bの正解は原因分類から自動で付けるため、正解にも誤りが含まれる状態を再現する（目視確認で割合を見る）
TYPO_PROB = 0.05
OTHER_CATEGORY = "その他"

# 英数字と記号（U+0021〜U+007E）を全角にする表。空白は半角のまま
FULLWIDTH_TABLE = {code: code + 0xFEE0 for code in range(0x21, 0x7F)}


def all_equipment2() -> List[str]:
    return [eq2 for eq1_map in EQUIPMENT_TREE.values() for eq2_list in eq1_map.values() for eq2 in eq2_list]


def validate_modes(data: Dict[str, Any]) -> None:
    """故障モード辞書が生成のルールに合っているかを確かめ、合わなければ止める。YAMLを手で直したときの確認用。"""
    known_eq2 = all_equipment2()
    mode_counts: Counter = Counter()
    ids: List[str] = []
    codes: List[str] = []
    for mode in data["modes"]:
        mode_id = mode["id"]
        for eq2 in mode["equipment2"]:
            if eq2 not in known_eq2:
                raise ValueError(f"{mode_id}: EQUIPMENT_TREEにない設備名です: {eq2}")
            mode_counts[eq2] += 1
        if mode["cause_category"] not in data["cause_categories"]:
            raise ValueError(f"{mode_id}: 原因分類の一覧にない分類です: {mode['cause_category']}")
        texts = mode["symptoms"] + [mode["cause"], mode["action"]]
        if any("{code}" in t for t in texts) and not mode.get("error_code"):
            raise ValueError(f"{mode_id}: 文に{{code}}があるのにerror_codeがない")
        if any("{value}" in t for t in texts) and "value" not in (mode.get("values") or {}):
            raise ValueError(f"{mode_id}: 文に{{value}}があるのにvaluesがない")
        if mode_id in ids:
            raise ValueError(f"モードのidが重複しています: {mode_id}")
        ids.append(mode_id)
        code = mode.get("error_code")
        if code:
            if code in codes:
                raise ValueError(f"{mode_id}: error_codeが重複しています: {code}")
            codes.append(code)
    for eq2 in known_eq2:
        if mode_counts[eq2] < 2:
            raise ValueError(f"故障モードが2つ未満の設備種別があります: {eq2}（{mode_counts[eq2]}個）")


def load_modes(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validate_modes(data)
    return data


def build_units() -> List[Dict[str, str]]:
    """設備の個体の一覧。各ラインで、使えるカテゴリの全設備種別が #1 と #2 の2台ずつあるとみなす。"""
    # 実際はラインごとに台数も種類も違うけど、ここでは2台ずつにそろえて簡略化してる
    units = []
    for location, lines in FACTORY_LINE_MAP.items():
        for line in lines:
            for category in LINE_CATEGORY_MAP[line]:
                for equipment1, eq2_list in EQUIPMENT_TREE[category].items():
                    for equipment2 in eq2_list:
                        for number in (1, 2):
                            units.append(
                                {
                                    "location": location,
                                    "line": line,
                                    "category": category,
                                    "equipment1": equipment1,
                                    "equipment2": equipment2,
                                    "equipment3": f"{equipment2} #{number}",
                                }
                            )
    return units


def _decimals(number: Any) -> int:
    text = str(number)
    return len(text.split(".")[1]) if "." in text else 0


def format_value(spec: Dict[str, Any], rng: random.Random) -> str:
    """values の範囲から値を決める。桁数は範囲の値に合わせる（0.5〜0.7なら0.6、110〜150なら整数）。"""
    digits = max(_decimals(spec["min"]), _decimals(spec["max"]))
    if digits == 0:
        number = str(rng.randint(spec["min"], spec["max"]))
    else:
        number = f"{rng.uniform(spec['min'], spec['max']):.{digits}f}"
    return number + spec["unit"]


def fill(template: str, eq: str, code: str, value: str) -> str:
    return template.replace("{eq}", eq).replace("{code}", code).replace("{value}", value)


def apply_style(text: str, style: Dict[str, Any]) -> str:
    """書き手の癖（長音の省略、略称、全角）を文に反映する。"""
    for old, new in (style.get("replace") or {}).items():
        text = text.replace(old, new)
    if style.get("to_fullwidth"):
        text = text.translate(FULLWIDTH_TABLE)
    return text


def write_texts(
    mode: Dict[str, Any], unit: Dict[str, str], style: Dict[str, Any], rng: random.Random
) -> Tuple[str, str, str]:
    """1件分の症状・原因・処置の文を作る。"""
    # 同じ故障でも書く人によって言い回しや表記が違う。
    # 評価Aで、質問と記録の書き方がずれていても引けるか（言い換え・略称・全角）を測れるようにするため
    if style.get("prefer_short"):
        symptom = min(mode["symptoms"], key=len)
    else:
        symptom = rng.choice(mode["symptoms"])
    eq = unit["equipment3"] if rng.random() < EQ3_PROB else unit["equipment2"]
    code = mode.get("error_code", "")
    # 1件の中で数値が食い違わないよう、値は1回だけ決める
    value = format_value(mode["values"]["value"], rng) if mode.get("values") else ""
    texts = [apply_style(fill(t, eq, code, value), style) for t in (symptom, mode["cause"], mode["action"])]
    return texts[0], texts[1], texts[2]


def pick_cause_category(true_category: str, categories: List[str], rng: random.Random) -> str:
    if rng.random() >= TYPO_PROB:
        return true_category
    if rng.random() < 0.5:
        return rng.choice([c for c in categories if c != true_category])
    return OTHER_CATEGORY


def generate_records(data: Dict[str, Any], count: int, seed: int, start: date, end: date) -> List[Dict[str, Any]]:
    """記録を日付順に作る。各記録はCSVの列に加えて、再発を確かめるための mode_id を持つ（CSVには出さない）。"""
    rng = random.Random(seed)
    modes = {mode["id"]: mode for mode in data["modes"]}
    modes_by_eq2: Dict[str, List[str]] = {}
    for mode in data["modes"]:
        for eq2 in mode["equipment2"]:
            modes_by_eq2.setdefault(eq2, []).append(mode["id"])
    styles = data["writer_styles"]
    style_weights = [style["weight"] for style in styles]

    units = build_units()
    unit_weights = [rng.paretovariate(PARETO_SHAPE) for _ in units]
    # 同じ名前の号機が各ラインにあるので、個体はラインと equipment3 の組で区別する
    histories: Dict[Tuple[str, str], List[str]] = {}

    days = (end - start).days
    dates = sorted(start + timedelta(days=rng.randrange(days + 1)) for _ in range(count))

    records = []
    for index, day in enumerate(dates):
        unit = rng.choices(units, weights=unit_weights)[0]
        history = histories.setdefault((unit["line"], unit["equipment3"]), [])
        # 履歴は同じモードの重複を含むので、何度も起きている故障ほど再発しやすい（慢性的な故障）
        if history and rng.random() < RECUR_PROB:
            mode_id = rng.choice(history)
        else:
            mode_id = rng.choice(modes_by_eq2[unit["equipment2"]])
        history.append(mode_id)
        mode = modes[mode_id]

        style = rng.choices(styles, weights=style_weights)[0]
        symptom, cause, action = write_texts(mode, unit, style, rng)
        work_type = rng.choices(WORK_TYPES, weights=WORK_TYPE_WEIGHTS)[0]
        prevention = rng.choice(PREVENTIONS)

        full_text = f"""【現象】
{symptom}

【原因】
{cause}

【処置】
{action}

【備考】
{prevention if prevention else '特になし。'}"""

        # 作業時間とダウンタイム
        work_time = rng.randint(30, 300)
        downtime = 0
        if work_type == "重大故障":
            downtime = work_time + rng.randint(0, 120)
        elif work_type == "修理票":
            downtime = rng.randint(0, 60)

        records.append(
            {
                "doc_id": f"doc_{index:06d}",
                "source_number": f"Rpt-{index:04d}",
                "work_type": work_type,
                "date": day.isoformat(),
                **unit,
                "equipment_full": f"{unit['equipment1']} > {unit['equipment2']} > {unit['equipment3']}",
                "work_duration_minutes": work_time,
                "downtime_minutes": downtime,
                "symptom": symptom,
                "root_cause": cause,
                "action_taken": action,
                "prevention": prevention,
                "text": full_text,
                "cause_category": pick_cause_category(mode["cause_category"], data["cause_categories"], rng),
                "mode_id": mode_id,
            }
        )
    return records


def count_recurrences(records: List[Dict[str, Any]]) -> int:
    """同じ個体で同じ故障モードが過去にもあった記録の数。"""
    seen = set()
    recurred = 0
    for record in records:
        key = (record["line"], record["equipment3"], record["mode_id"])
        if key in seen:
            recurred += 1
        seen.add(key)
    return recurred


def write_csv(records: List[Dict[str, Any]], path: Path) -> None:
    """Excelで開けるようBOM付きで書く。改行はLFにそろえ、どのOSで生成しても同じ中身にする。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def log_summary(records: List[Dict[str, Any]]) -> None:
    logger.info("records: %d", len(records))
    logger.info("period: %s - %s", records[0]["date"], records[-1]["date"])
    counts = Counter(record["equipment2"] for record in records)
    for eq2 in all_equipment2():
        logger.info("  %s: %d", eq2, counts[eq2])
    recurred = count_recurrences(records)
    logger.info("recurrence rate: %.3f (%d / %d)", recurred / len(records), recurred, len(records))


def main() -> None:
    parser = argparse.ArgumentParser(description="故障モード辞書からデモデータを生成する")
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2021, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--modes", type=Path, default=TOOLS_DIR / "failure_modes.yaml")
    parser.add_argument("--output", type=Path, default=TOOLS_DIR.parent / "data" / "demo" / "demo_logs.csv")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count は1以上にしてください")
    if args.end < args.start:
        parser.error("--end は --start 以降の日付にしてください")

    logging.basicConfig(level=logging.INFO)
    data = load_modes(args.modes)
    records = generate_records(data, args.count, args.seed, args.start, args.end)
    write_csv(records, args.output)
    log_summary(records)
    logger.info("saved: %s", args.output)


if __name__ == "__main__":
    main()
