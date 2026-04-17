"""
PostgreSQL + pgvector によるベクトル検索

データ永続化・トランザクション管理のためPostgreSQLを使用。

設計方針:
- FAISSIndexManager と同じインターフェースを維持
- メタデータは self.metadata 属性として提供（HybridSearcher の互換性）
- スコアは 0-1 の範囲に正規化（FAISS と同じ）
"""

import psycopg2
import psycopg2.extras
import numpy as np
import json
import logging
import time
from typing import List, Dict, Any, Tuple, Optional
from .config import settings

logger = logging.getLogger(__name__)


class PgvectorIndexManager:
    """
    PostgreSQL + pgvector によるベクトル検索
    
    FAISSIndexManager の代替実装。
    インターフェースを維持することで、既存コードへの影響を最小化。
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        """
        Args:
            db_config: DB接続設定（省略時は settings["database"] を使用）
        """
        if db_config is None:
            db_config = settings.get("database", {})
        
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self.metadata: List[Dict[str, Any]] = []  # HybridSearcher の互換性のため
        
        # DB接続・初期化
        self._connect()
        self._ensure_extension()
        self._ensure_table()
        
        # メタデータをロード（HybridSearcher が期待する形式）
        self._load_metadata()

    def _connect(self):
        """DB接続を確立（リトライロジック付き）"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=self.db_config.get("host", "localhost"),
                    port=self.db_config.get("port", 5432),
                    dbname=self.db_config.get("name", "assistchat"),
                    user=self.db_config.get("user", "postgres"),
                    password=self.db_config.get("password", "postgres")
                )
                self.conn.autocommit = False  # トランザクション管理を明示
                self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                logger.info(f"PostgreSQL接続成功: {self.db_config.get('host')}:{self.db_config.get('port')}/{self.db_config.get('name')}")
                return
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"接続失敗（{attempt+1}/{max_retries}）、{retry_delay}秒後にリトライ: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"PostgreSQL接続失敗。Docker Composeが起動しているか確認してください: {e}")
                    raise
            except Exception as e:
                logger.error(f"予期しないエラー: {e}")
                raise

    def _ensure_extension(self):
        """
        pgvector拡張確認
        
        マイグレーションで管理されているため、ここでは存在確認のみ。
        """
        try:
            # 拡張存在確認
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """)
            
            result = self.cursor.fetchone()
            if result is None:
                exists = False
            elif isinstance(result, dict):
                # RealDictCursor を使用している場合、辞書で返る
                exists = result.get('exists', False)
            else:
                # 通常のカーソルの場合、タプルで返る
                exists = result[0] if len(result) > 0 else False
            
            if not exists:
                error_msg = (
                    "\n" + "=" * 80 + "\n"
                    "❌ エラー: pgvector拡張が有効化されていません\n"
                    "\n"
                    "以下のコマンドでマイグレーションを実行してください:\n"
                    "  python database/run_migrations.py\n"
                    "\n"
                    "=" * 80
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.debug("pgvector拡張を確認")
            
        except Exception as e:
            logger.error(f"pgvector拡張の確認失敗: {e}")
            raise

    def _ensure_table(self):
        """
        テーブル存在確認
        
        マイグレーション管理により、DDLは独立したファイルで管理されています。
        ここでは存在確認のみ行い、テーブルが存在しない場合は
        マイグレーション実行を促します。
        """
        try:
            # テーブル存在確認
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                      AND table_name = 'documents'
                )
            """)
            
            result = self.cursor.fetchone()
            if result is None:
                exists = False
            elif isinstance(result, dict):
                # RealDictCursor を使用している場合、辞書で返る
                exists = result.get('exists', False)
            else:
                # 通常のカーソルの場合、タプルで返る
                exists = result[0] if len(result) > 0 else False
            
            if not exists:
                error_msg = (
                    "\n" + "=" * 80 + "\n"
                    "❌ エラー: documentsテーブルが存在しません\n"
                    "\n"
                    "マイグレーション管理により、DDLは独立したファイルで管理されています。\n"
                    "以下のコマンドでマイグレーションを実行してください:\n"
                    "\n"
                    "  python database/run_migrations.py\n"
                    "\n"
                    "=" * 80
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.debug("テーブル存在確認完了")
            
        except psycopg2.Error as e:
            logger.error(f"テーブル確認失敗: {e}")
            raise
        
        # マイグレーション管理に移行
        # DDLは database/migrations/ に配置
        # 実行: python database/run_migrations.py

    def _load_metadata(self):
        """
        全メタデータをロード
        
        HybridSearcher の互換性のため、self.metadata として公開。
        search.py が期待する形式: List[Dict[str, Any]]
        """
        try:
            self.cursor.execute("SELECT metadata FROM documents ORDER BY id")
            rows = self.cursor.fetchall()
            self.metadata = [dict(row['metadata']) for row in rows]
            logger.info(f"メタデータロード完了: {len(self.metadata)}件")
        except Exception as e:
            logger.warning(f"メタデータロード失敗（テーブルが空の可能性）: {e}")
            self.metadata = []

    def _clean_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        メタデータから NaN を除去
        
        PostgreSQL の JSONB は NaN をサポートしないため、
        NaN を None に変換する。
        
        Args:
            meta: 元のメタデータ
        
        Returns:
            クリーンなメタデータ
        """
        import math
        
        cleaned = {}
        for key, value in meta.items():
            # NaN チェック（float/int のみ）
            if isinstance(value, (float, int)):
                if math.isnan(value) or math.isinf(value):
                    cleaned[key] = None
                else:
                    cleaned[key] = value
            elif isinstance(value, dict):
                # ネストされた辞書も再帰的に処理
                cleaned[key] = self._clean_metadata(value)
            elif isinstance(value, list):
                # リスト内の NaN も処理
                cleaned[key] = [
                    None if isinstance(v, (float, int)) and (math.isnan(v) or math.isinf(v)) else v
                    for v in value
                ]
            else:
                cleaned[key] = value
        
        return cleaned

    def build(self, embeddings: np.ndarray, texts: List[str], metadata: List[Dict[str, Any]]):
        """
        インデックス構築（PostgreSQLにベクトルを挿入）
        
        バッチINSERTで高速化。
        IVFFLATインデックスはデータ挿入後に作成。
        
        Args:
            embeddings: ベクトル配列 (n, 768)
            texts: テキストのリスト
            metadata: メタデータのリスト（chunk_id, doc_id, text等を含む）
        
        Raises:
            ValueError: 入力データの形式が不正な場合
        """
        # 入力検証
        if not isinstance(embeddings, np.ndarray) or embeddings.ndim != 2:
            raise ValueError("embeddings must be a 2D numpy array.")
        
        if len(embeddings) != len(texts) or len(embeddings) != len(metadata):
            raise ValueError(
                f"Length mismatch: embeddings({len(embeddings)}), "
                f"texts({len(texts)}), metadata({len(metadata)})"
            )
        
        dimension = embeddings.shape[1]
        if dimension != 768:
            raise ValueError(f"Expected embedding dimension 768, got {dimension}")
        
        logger.info(f"PostgreSQLにベクトルを挿入中: {len(embeddings)}件")
        
        # 正規化（コサイン類似度用）
        # FAISSと同じロジック
        if settings["embedding"].get("normalize_embeddings", True):
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            # ゼロ除算回避
            norms = np.where(norms == 0, 1, norms)
            embeddings = embeddings / norms
            logger.debug("埋め込みベクトルを正規化")
        
        # バッチデータ準備
        batch_data = []
        for i, (emb, text, meta) in enumerate(zip(embeddings, texts, metadata)):
            # chunk_id を取得（なければ自動生成）
            chunk_id = meta.get('chunk_id', f'chunk_{i}')
            
            # NaN を None に変換（PostgreSQL JSONB 対応）
            cleaned_meta = self._clean_metadata(meta)
            
            batch_data.append((
                chunk_id,
                text,
                emb.tolist(),  # NumPy配列をリストに変換
                json.dumps(cleaned_meta, ensure_ascii=False)
            ))
        
        try:
            # 既存データをクリア（TRUNCATE は DELETE より高速）
            logger.info("既存データをクリア中...")
            self.cursor.execute("TRUNCATE TABLE documents RESTART IDENTITY CASCADE")
            self.conn.commit()
            logger.debug("既存データをクリア完了")
            
            # バッチINSERT（execute_batch で高速化）
            logger.info("バッチINSERT実行中...")
            psycopg2.extras.execute_batch(
                self.cursor,
                """
                INSERT INTO documents (chunk_id, text, embedding, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                batch_data,
                page_size=100  # 100件ずつコミット
            )
            
            self.conn.commit()
            logger.info(f"✅ ベクトル挿入完了: {len(batch_data)}件")
            
            # IVFFLAT インデックス作成（データ挿入後）
            logger.info("IVFFLAT インデックスを作成中...")
            
            # 既存インデックスを削除
            self.cursor.execute("DROP INDEX IF EXISTS documents_embedding_idx")
            
            # 新しいインデックスを作成
            # lists = 100: 1万件に最適（データ件数の平方根が目安）
            self.cursor.execute("""
                CREATE INDEX documents_embedding_idx 
                ON documents USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            
            self.conn.commit()
            
            # 統計情報を更新（検索パフォーマンス向上）
            # VACUUM は autocommit モードで実行する必要がある
            old_autocommit = self.conn.autocommit
            self.conn.autocommit = True
            try:
                self.cursor.execute("VACUUM ANALYZE documents")
                logger.info("✅ IVFFLAT インデックス作成完了")
            finally:
                self.conn.autocommit = old_autocommit
            
            # メタデータ再ロード
            self._load_metadata()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"ベクトル挿入失敗: {e}")
            raise

    def search(self, query_vector: np.ndarray, top_k: int) -> List[Tuple[Dict[str, Any], float]]:
        """
        ベクトル検索
        
        Args:
            query_vector: クエリベクトル (768,) or (1, 768)
            top_k: 取得件数
        
        Returns:
            [(metadata, score), ...] のリスト
            score は 0-1 の範囲（1 = 最も類似、0 = 全く異なる）
        
        Note:
            pgvector のコサイン距離（0-2）を FAISS のコサイン類似度（0-1）に変換
            変換式: score = (2.0 - distance) / 2.0
        """
        # 1次元ベクトルを2次元に変換
        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)
        
        # 正規化（FAISSと同じロジック）
        if settings["embedding"].get("normalize_embeddings", True):
            norm = np.linalg.norm(query_vector)
            if norm > 0:
                query_vector = query_vector / norm
        
        query_list = query_vector[0].tolist()
        
        try:
            # pgvector 検索
            # <=> はコサイン距離演算子（0 = 同一、2 = 正反対）
            # (2.0 - distance) / 2.0 で 0-1 の範囲に正規化
            self.cursor.execute("""
                SELECT 
                    text,
                    metadata,
                    (2.0 - (embedding <=> %s::vector)) / 2.0 AS score
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_list, query_list, top_k))
            
            rows = self.cursor.fetchall()
            
            # FAISSと同じ形式で返す（textを含む）
            results = []
            for row in rows:
                # スコアが範囲外になることはないはずだが、念のためクリップ
                score = max(0.0, min(1.0, float(row['score'])))
                # metadataにtextを追加
                item = dict(row['metadata'])
                item['text'] = row['text']
                results.append((item, score))
            
            return results
            
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # 接続切れの場合、再接続を試みる
            logger.warning(f"DB接続エラー、再接続を試みます: {e}")
            self._connect()
            # 再試行
            return self.search(query_vector, top_k)
        except Exception as e:
            logger.error(f"検索失敗: {e}")
            return []

    def close(self):
        """DB接続をクローズ"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("PostgreSQL接続をクローズ")

    def __del__(self):
        """デストラクタ（念のため）"""
        try:
            self.close()
        except Exception:
            pass  # デストラクタでは例外を抑制
