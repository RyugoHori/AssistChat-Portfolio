# システムアーキテクチャ

## システム構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Search UI  │  │ Filter Panel│  │    Detail Panel         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                         Port: 3000                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ /api/search │  │ /api/docs   │  │  /api/search/metadata   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                         Port: 8001                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAG Core Library                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   HybridSearcher                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │   FAISS     │  │    BM25     │  │   Re-ranker     │   │   │
│  │  │  (Dense)    │  │  (Sparse)   │  │ (Cross-Encoder) │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │              ↘         ↓         ↙                       │   │
│  │              ┌─────────────────────┐                     │   │
│  │              │   RRF Fusion        │                     │   │
│  │              └─────────────────────┘                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Index Files (data/indices/)                  │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │ maintenance.faiss│  │ maintenance.bm25│                       │
│  │ (Vector Index)   │  │ (Keyword Index) │                       │
│  └─────────────────┘  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## コンポーネント詳細

### Frontend (apps/assist-chat)

| ディレクトリ | 役割 |
|-------------|------|
| `app/` | Next.js App Router ページ |
| `components/features/` | 機能別コンポーネント（検索、フィルター、詳細） |
| `components/ui/` | shadcn/ui ベースの汎用UIコンポーネント |
| `hooks/` | カスタムフック（useSearch, useDocumentDetail） |
| `contexts/` | React Context（検索状態管理） |

### Backend (services/rag-api)

| ファイル | 役割 |
|---------|------|
| `main.py` | FastAPIアプリケーション、エンドポイント定義 |
| `api/models.py` | Pydanticモデル（リクエスト/レスポンス検証） |

### RAG Core (packages/rag-core)

| モジュール | 役割 |
|-----------|------|
| `search.py` | HybridSearcher（検索のオーケストレーション） |
| `dense_index.py` | FAISSインデックス管理 |
| `sparse_index.py` | BM25インデックス管理 |
| `embeddings.py` | テキスト埋め込み生成 |
| `reranker.py` | Cross-Encoderによる再順位付け |
| `tokenization.py` | MeCabによる日本語トークナイズ |

---

## 検索フロー

```
1. ユーザーがクエリを入力
        │
        ▼
2. Frontend → Backend API (/api/search)
        │
        ▼
3. クエリの前処理
   - MeCabでトークナイズ
   - Sentence-Transformerで埋め込み生成
        │
        ├─────────────────┬
        ▼                 ▼                 
4. 　意味検索    　  キーワード検索   　 　　  
    (FAISS)             (BM25)              
    Top-K取得           Top-K取得            
        │                 │                 
        └────────┬────────┘                
                 ▼                          
5. RRF (Reciprocal Rank Fusion)             
   2つの結果をランクベースで統合           　  
                 │                          
                 ▼                          
6. Post-filtering                           
   メタデータによる絞り込み                  
   (工場、ライン、設備、年度)                 
                 │                          
                 ▼                         
7. Re-ranking (Cross-Encoder)               
   クエリと各結果のペアをスコアリング          
                 │                          
                 ▼                          
8. 最終結果を返却
```

### RRFアルゴリズム

```python
Score = Σ(1 / (k + rank))  # k=60
```

2つの検索結果をランクベースで統合。スコアの正規化が不要でシンプル。

---

## API エンドポイント

| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/search` | 検索実行 |
| GET | `/api/search/metadata` | フィルターメタデータ取得 |
| GET | `/api/docs/{doc_id}` | ドキュメント詳細取得 |
| POST | `/api/feedback` | フィードバック送信 |

### リクエスト例: 検索

```json
POST /api/search
{
  "query": "コンベアが停止する",
  "filters": {
    "productionLines": ["A1000 生産ラインA"],
    "categories": ["機械"]
  },
  "k": 5
}
```

### レスポンス例

```json
{
  "results": [
    {
      "doc_id": "DOC-001",
      "title": "ベルトコンベア停止",
      "snippet": "モーター過負荷により停止...",
      "score": 0.85,
      "confidence": 85,
      "date": "2024-03-15",
      "line": "A1000 生産ラインA",
      "category": "機械"
    }
  ],
  "total": 1,
  "processingTime": 120
}
```

---

## データフロー

### インデックス構築時

```
CSV (保全記録)
    │
    ▼ preprocess.py
Chunks (JSONLファイル)
    │
    ├─────────────────┬
    ▼                 ▼                 
FAISS Index       BM25 Index           
(ベクトル)         (転置インデックス)     
    │                 │                 
    └────────┬────────┘                 
             ▼                          
    data/indices/ に保存                
```

### 検索時

```
User Query
    │
    ▼
HybridSearcher.search()
    │
    ├─ dense_searcher.search()  → FAISS検索
    │
    ├─ sparse_searcher.search() → BM25検索
    │
    ├─ _reciprocal_rank_fusion() → 結果統合
    │
    ├─ _apply_filters() → フィルタリング
    │
    └─ reranker.rerank() → 再順位付け
    │
    ▼
Search Results (JSON)
```

---

## パフォーマンス

### 実測値

| 処理 | 所要時間 |
|------|----------|
| FAISS検索（500件） | ~20ms |
| BM25検索（500件） | ~30ms |
| Re-ranking（10件） | ~100ms |
| **合計** | **~150ms** |

### スケーラビリティ

| 項目 | 現状 | 上限目安 |
|------|------|----------|
| ドキュメント数 | 約1万件 | 10万件 |
| 同時接続数 | ~15人 | 30人程度 |
| インデックスサイズ | ~600MB | ~1GB |

---

## Docker構成

```yaml
services:
  rag-api:      # FastAPI Backend (Port 8001)
  assist-chat:  # Next.js Frontend (Port 3000)
```

### ボリュームマウント

| ホスト | コンテナ | 用途 |
|--------|----------|------|
| `./data` | `/app/data` | インデックス、デモデータ |
| `./packages` | `/packages` | rag-coreパッケージ |
