"""
ポートフォリオ用のデモデータ生成スクリプト
実際の保全記録っぽいダミーデータを作る
工場 → ライン → 設備の階層構造をちゃんと守る
"""

import pandas as pd
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

# ログ設定（デバッグ用）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== マスターデータ ====================

# 工場とラインの対応関係
FACTORY_LINE_MAP = {
    "第1工場": ["A1000 生産ラインA", "A2000 生産ラインB"],
    "第2工場": ["B1000 組立ラインC", "B2000 組立ラインD"],
    "第3工場": ["C1000 検査ラインE"]
}

# ラインごとのカテゴリ（機械/電気）
# 本来はラインごとに設備が違うけど、ここではカテゴリで簡略化してる
# もっと厳密にするなら、ライン → カテゴリ → 設備1 のマッピングが必要
LINE_CATEGORY_MAP = {
    "A1000 生産ラインA": ["機械", "電気"],
    "A2000 生産ラインB": ["機械", "電気"],
    "B1000 組立ラインC": ["機械", "電気"], # 組立はロボット多いかも
    "B2000 組立ラインD": ["機械", "電気"],
    "C1000 検査ラインE": ["電気", "機械"], # 検査はセンサー多め
}

# 設備の階層構造：カテゴリ → 設備1 → 設備2
EQUIPMENT_TREE = {
    "機械": {
        "加工設備": ["NC旋盤", "マシニングセンタ", "平面研削盤", "油圧プレス機"],
        "搬送設備": ["ベルトコンベア", "ローラーコンベア", "多関節ロボット", "無人搬送車(AGV)", "オーバーヘッドホイスト"],
        "ユーティリティ": ["スクリューコンプレッサー", "冷却塔(クーリングタワー)", "貫流ボイラー", "集塵機"],
        "組立設備": ["ナットランナー", "圧入機", "カシメ機", "自動塗布装置"]
    },
    "電気": {
        "制御盤": ["主制御盤", "動力盤", "操作盤", "リモートI/O盤"],
        "センサー": ["光電センサー", "近接スイッチ", "圧力トランスミッタ", "熱電対", "画像処理カメラ", "流量計"],
        "駆動制御": ["サーボアンプ", "インバータ", "ステッピングドライバ", "ソフトスタータ"],
        "通信機器": ["PLC CPUユニット", "イーサネットユニット", "無線LANアダプタ", "タッチパネル(HMI)"]
    }
}

WORK_TYPES = ["修理票", "重大故障", "作業票", "連絡票"]
WORK_TYPE_WEIGHTS = [0.5, 0.1, 0.3, 0.1]

# テンプレート（現象・原因・処置の文章を自動生成するため）
# {part}は部品名、{value}は数値、{code}はエラーコードみたいな感じ
SYMPTOM_TEMPLATES = [
    "稼働中に{part}付近から「ガガガ」という異音が発生した。",
    "起動ボタンを押下したが、{part}が応答せず、エラーコードE-{code}が表示された。",
    "製品の{feature}寸法が規格値({spec}±0.05)を外れ、{value}mmとなっている。",
    "{part}の過負荷アラーム(OL)が頻発し、装置がチョコ停する。",
    "{part}の振動値が管理基準({spec}mm/s)を超え、{value}mm/sを記録した。",
    "{part}の継ぎ目から作動油が漏れ、床面に油溜まりができている。",
    "供給エア圧力が{value}MPaまで低下し、シリンダー動作が不安定になった。",
    "上位システムとの通信エラーが発生し、生産実績データが送信できない。",
    "タッチパネルの画面がフリーズし、操作を受け付けない。",
    "シリンダーの動作速度が低下し、サイクルタイムが基準より{value}秒遅延している。",
    "搬送ベルトがスリップしており、ワークの搬送位置ズレが発生。",
    "ヒーター温度が設定値{spec}℃まで上昇せず、{value}℃で頭打ちになる。",
    "安全扉を閉じたがインターロックが解除されず、起動できない。",
    "原点復帰動作を行ったが、{part}軸が完了位置手前で停止する。",
    "{part}のサーマルトリップが作動し、主電源が遮断された。"
]

CAUSE_TEMPLATES = [
    "{part}内部のベアリング（型式:{model}）が摩耗し、回転振れが生じていた。",
    "センサー位置が振動によりズレており、検出距離が限界を超えていた。",
    "可動部のケーブルベア内で{part}用ケーブルが断線していた。",
    "電磁開閉器の接点が溶着しており、遮断不能となっていた。",
    "PLCプログラムのタイマー設定ミスにより、待機時間が不足していた。",
    "吸気フィルターが切粉と油分で完全に目詰まりしていた。",
    "Oリング（{model}）の経年劣化による硬化・亀裂。",
    "Vベルトの張力が規定値{spec}Nに対し{value}Nまで低下していた。",
    "自動給油装置の配管詰まりにより、{part}への給油が行われていなかった。",
    "スライド摺動面に切粉が噛み込み、動作抵抗が増大していた。",
    "カップリングの樹脂パーツが疲労破壊していた。",
    "インバータ設定パラメータの誤変更。",
    "アース不良によりノイズが信号線に重畳し、誤検知を引き起こした。"
]

ACTION_TEMPLATES = [
    "{part}（{model}）を予備品と交換し、芯出し調整を実施。",
    "センサー取付ブラケットを増し締めし、検出位置を再調整。",
    "断線箇所を特定し、屈曲に強いロボットケーブルへ張り替え実施。",
    "接点不良のリレーを新品に交換し、I/Oチェックを実施。",
    "ラダープログラムを修正し、インターロック条件を見直した。",
    "フィルターを洗浄液で清掃し、エアブロー乾燥後に再装着。",
    "Oリング全数を新品交換し、リークテストを実施して漏れなきことを確認。",
    "テンションメーターを用いて張力を規定値{spec}Nに調整。",
    "配管を分解清掃し、ディストリビューターを交換。給油動作を確認。",
    "摺動面をオイルストーンで修正し、カジリを除去。",
    "カップリングを交換し、モーターと負荷側の軸心を調整。",
    "パラメータP-{code}を初期値に戻し、正常動作を確認。",
    "シールド線のアース処理をやり直し、フェライトコアを追加。"
]

PARTS_DB = {
    "機械": ["ボールねじ", "リニアガイド", "タイミングベルト", "油圧ポンプ", "ソレノイドバルブ", "チャック爪", "主軸ベアリング", "減速機"],
    "電気": ["光電管", "リミットスイッチ", "エンコーダ", "SSR", "マグネットスイッチ", "ヒューズ", "DC24V電源", "サーボモーター"]
}

MODELS = ["6204ZZ", "6005DDU", "MY2N-D2", "G3NA-210B", "E3Z-T61", "CV-X100", "FX5U-32MT", "GT2710", "CR-700"]

# ==================== データ生成のヘルパー関数 ====================

def generate_date(start_year=2021, end_year=2025) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 5, 30)
    delta = end - start
    random_days = random.randrange(delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")

def format_template(template, category):
    part = random.choice(PARTS_DB[category])
    model = random.choice(MODELS)
    value = random.randint(10, 200)
    spec = random.randint(value, value + 50)
    code = random.randint(100, 999)
    feature = random.choice(["外径", "全長", "内径", "厚み"])
    
    return template.format(
        part=part, model=model, value=value, spec=spec, code=code, feature=feature
    )

def generate_record(index: int) -> Dict:
    # 1. 階層構造をランダムに選ぶ
    location = random.choice(list(FACTORY_LINE_MAP.keys()))
    line = random.choice(FACTORY_LINE_MAP[location])
    
    # ラインからカテゴリを選ぶ（簡略版）
    category = random.choice(LINE_CATEGORY_MAP[line])
    
    # 設備の階層を選ぶ
    eq1_list = list(EQUIPMENT_TREE[category].keys())
    equipment1 = random.choice(eq1_list)
    equipment2 = random.choice(EQUIPMENT_TREE[category][equipment1])
    equipment3 = f"{equipment2} #{random.randint(1, 4)}" # 例：操作盤 #2
    
    work_type = random.choices(WORK_TYPES, weights=WORK_TYPE_WEIGHTS)[0]
    
    # 2. テンプレートから文章を生成
    symptom = format_template(random.choice(SYMPTOM_TEMPLATES), category)
    cause = format_template(random.choice(CAUSE_TEMPLATES), category)
    action = format_template(random.choice(ACTION_TEMPLATES), category)
    
    # 3. その他の詳細情報
    prevention = random.choice(["", "定期点検項目への追加。", "保全カレンダーへの登録。", "オペレーターへの清掃指導。", "予備品の在庫発注点見直し。"])
    
    full_text = f"""【現象】
{symptom}

【原因】
{cause}

【処置】
{action}

【備考】
{prevention if prevention else '特になし。'}"""

    # 作業時間とダウンタイム
    work_time = random.randint(30, 300)
    downtime = 0
    if work_type == "重大故障":
        downtime = work_time + random.randint(0, 120)
    elif work_type == "修理票":
        downtime = random.randint(0, 60)

    return {
        "doc_id": f"doc_{index:06d}",
        "source_number": f"Rpt-{index:04d}",
        "work_type": work_type,
        "date": generate_date(),
        "location": location,
        "line": line,
        "category": category,
        "equipment1": equipment1,
        "equipment2": equipment2,
        "equipment3": equipment3,
        "equipment_full": f"{equipment1} > {equipment2} > {equipment3}",
        "work_duration_minutes": work_time,
        "downtime_minutes": downtime,
        "symptom": symptom,
        "root_cause": cause,
        "action_taken": action,
        "prevention": prevention,
        "text": full_text
    }

def generate_demo_data(count: int = 500, output_path: str = "data/demo/demo_logs.csv"):
    logger.info(f"Generating {count} realistic demo records...")
    
    records = [generate_record(i) for i in range(count)]
    df = pd.DataFrame(records)
    
    logger.info("Data Distribution:")
    logger.info(df['location'].value_counts())
    logger.info(df['work_type'].value_counts())
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8')
    logger.info(f"Saved to {path}")

if __name__ == "__main__":
    generate_demo_data()
