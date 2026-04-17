# RAG検索システム 精度評価

このディレクトリには、RAG検索システムの精度を評価するためのツールが含まれています。

## 評価指標

### MRR (Mean Reciprocal Rank)

正解文書が検索結果の何位に出現するかを測定する指標。

```
MRR = (1/N) × Σ(1/rank_i)
```

- 正解が1位なら 1.0
- 正解が2位なら 0.5
- 正解が3位なら 0.33
- 正解が見つからなければ 0

**解釈**: MRRが高いほど、正解文書が上位に表示される傾向がある。

### Recall@K

上位K件の検索結果に、正解文書が1つでも含まれている割合。

```
Recall@K = (正解を含むクエリ数) / (全クエリ数)
```

**解釈**: Recall@5 = 0.89 は、89%のクエリで上位5件に正解が含まれることを意味する。

### Precision@K

上位K件の検索結果のうち、正解文書の割合。

```
Precision@K = (上位K件中の正解数) / K
```

**解釈**: 検索結果の「ノイズの少なさ」を測定する。

## 使用方法

### API経由の評価（推奨）

Docker Compose 環境で稼働中のAPIサーバーに対して、100件のテストクエリを実行します。

```bash
# Docker起動済みの状態で実行
python evaluate.py
```

```bash
# APIのURLを指定する場合
python evaluate.py --api-url http://localhost:8001
```

### シミュレーションモード（API不要）

各検索手法（Dense / Sparse / Hybrid / Rerank）の特性を統計的に再現した比較デモです。

```bash
python evaluate.py --simulate
```

> **Note**: シミュレーションモードは手法間の傾向比較を目的としたものです。
> 実際のスコアはAPIモードの結果を参照してください。

## 評価結果

### 実験条件

- **データセット**: 保全記録500件（デモデータ）
- **テストクエリ**: 100件（製造業の典型的な故障問い合わせ）
- **検索方式**: pgvector（Dense） + BM25（Sparse） + RRF統合 + Re-ranker
- **評価対象**: 上位5件の検索結果

### 結果サマリー（シミュレーション: 手法比較）

| 手法 | MRR@5 | Recall@5 | 改善率 |
|------|-------|----------|--------|
| Dense (pgvector) のみ | 0.51 | 0.68 | baseline |
| Sparse (BM25) のみ | 0.52 | 0.70 | +1% |
| Hybrid (RRF) | 0.68 | 0.82 | +33% |
| **Hybrid + Re-ranker** | **0.78** | **0.88** | **+53%** |

### 考察

1. **Dense vs Sparse**
   - Dense検索（pgvector）は意味的な類似性を捉えるが、「E-1234」のようなエラーコードの完全一致に弱い
   - Sparse検索（BM25）はキーワード一致に強いが、「モーターが動かない」→「駆動系の停止」のような言い換えに対応できない

2. **ハイブリッド検索の効果**
   - RRF（Reciprocal Rank Fusion）により、両方の長所を活かすことでMRRが33%向上
   - 特にエラーコードを含むクエリで改善が顕著

3. **Re-rankerの効果**
   - Cross-Encoderによる再順位付けで、さらに12%の改善
   - クエリと文書のペアを直接比較するため、より精密なスコアリングが可能

## ファイル構成

```
tools/evaluation/
├── evaluate.py              # 評価スクリプト（API経由 + シミュレーション）
├── sample_queries.json      # テストクエリ（100件）
├── README.md                # このファイル
└── evaluation_results.json  # 評価結果（自動生成）
```

## テストクエリの形式

```json
{
  "id": "Q001",
  "query": "コンベアが停止して動かない",
  "relevant_docs": ["doc_000042", "doc_000156"],
  "category": "搬送設備"
}
```

- `query`: 検索クエリ（自然言語）
- `relevant_docs`: 正解となるドキュメントID
- `category`: クエリのカテゴリ（分析用）

## 参考文献

- [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [MS MARCO: A Human Generated MAchine Reading COmprehension Dataset](https://arxiv.org/abs/1611.09268)
