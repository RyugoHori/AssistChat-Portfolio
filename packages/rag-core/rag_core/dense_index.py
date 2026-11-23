"""PostgreSQL + pgvector によるベクトル検索。"""

import json
import logging
import math
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import settings

logger = logging.getLogger(__name__)


class PgvectorIndexManager:
    """pgvector ベクトル検索。マイグレーションで作ったテーブルを前提にする。"""

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        if db_config is None:
            db_config = settings.get("database", {})

        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self.metadata: List[Dict[str, Any]] = []

        self._connect()
        self._ensure_extension()
        self._ensure_table()
        self._load_metadata()

    def _connect(self):
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=self.db_config.get("host", "localhost"),
                    port=self.db_config.get("port", 5432),
                    dbname=self.db_config.get("name", "assistchat"),
                    user=self.db_config.get("user", "postgres"),
                    password=self.db_config.get("password", "postgres"),
                )
                self.conn.autocommit = False
                self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                logger.info(
                    "pgvector connected: %s:%s/%s",
                    self.db_config.get("host"),
                    self.db_config.get("port"),
                    self.db_config.get("name"),
                )
                return
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning("db connect retry %d/%d: %s", attempt + 1, max_retries, e)
                    time.sleep(retry_delay)
                else:
                    logger.error("db connect failed: %s", e)
                    raise
            except Exception as e:
                logger.error("unexpected db error: %s", e)
                raise

    def _ensure_extension(self):
        """pgvector 拡張がインストールされているか確認する。DDL はマイグレーション管理。"""
        try:
            self.cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            result = self.cursor.fetchone()
            if result is None:
                exists = False
            elif isinstance(result, dict):
                exists = result.get("exists", False)
            else:
                exists = result[0] if len(result) > 0 else False

            if not exists:
                raise RuntimeError(
                    "pgvector 拡張が有効化されていません。" " `python database/run_migrations.py` を実行してください。"
                )

            logger.debug("pgvector extension present")

        except Exception as e:
            logger.error("pgvector check failed: %s", e)
            raise

    def _ensure_table(self):
        """documents テーブルの存在確認。DDL はマイグレーションで管理する。"""
        try:
            self.cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'documents'
                )
                """
            )
            result = self.cursor.fetchone()
            if result is None:
                exists = False
            elif isinstance(result, dict):
                exists = result.get("exists", False)
            else:
                exists = result[0] if len(result) > 0 else False

            if not exists:
                raise RuntimeError(
                    "documents テーブルが存在しません。" " `python database/run_migrations.py` を実行してください。"
                )

            logger.debug("documents table present")

        except psycopg2.Error as e:
            logger.error("table check failed: %s", e)
            raise

    def _load_metadata(self):
        """HybridSearcher が参照する self.metadata を埋める。"""
        try:
            self.cursor.execute("SELECT metadata FROM documents ORDER BY id")
            rows = self.cursor.fetchall()
            self.metadata = [dict(row["metadata"]) for row in rows]
            # 読み取りだけでもトランザクションが開いたままになり、索引の作り直しの TRUNCATE を待たせるので閉じる。
            # rollback にしないのは、同じ接続で実行した SET（評価用の enable_indexscan など）を取り消さないため。
            self.conn.commit()
            logger.info("metadata loaded: %d docs", len(self.metadata))
        except Exception as e:
            self.conn.rollback()
            logger.warning("metadata load failed (table may be empty): %s", e)
            self.metadata = []

    def _clean_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """JSONB が扱えない NaN / Infinity を None に再帰置換する。"""
        cleaned: Dict[str, Any] = {}
        for key, value in meta.items():
            if isinstance(value, (float, int)):
                cleaned[key] = None if math.isnan(value) or math.isinf(value) else value
            elif isinstance(value, dict):
                cleaned[key] = self._clean_metadata(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    None if isinstance(v, (float, int)) and (math.isnan(v) or math.isinf(v)) else v for v in value
                ]
            else:
                cleaned[key] = value
        return cleaned

    def build(self, embeddings: np.ndarray, texts: List[str], metadata: List[Dict[str, Any]]):
        """TRUNCATEして入れ直し、HNSWの索引を作る。"""
        if not isinstance(embeddings, np.ndarray) or embeddings.ndim != 2:
            raise ValueError("embeddings must be a 2D numpy array.")
        if len(embeddings) != len(texts) or len(embeddings) != len(metadata):
            raise ValueError(
                f"Length mismatch: embeddings({len(embeddings)}), " f"texts({len(texts)}), metadata({len(metadata)})"
            )
        if embeddings.shape[1] != 768:
            raise ValueError(f"Expected embedding dimension 768, got {embeddings.shape[1]}")

        logger.info("inserting %d vectors into pgvector", len(embeddings))

        if settings["embedding"].get("normalize_embeddings", True):
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            embeddings = embeddings / norms
            logger.debug("embeddings normalized")

        batch_data = []
        for i, (emb, text, meta) in enumerate(zip(embeddings, texts, metadata)):
            chunk_id = meta.get("chunk_id", f"chunk_{i}")
            cleaned_meta = self._clean_metadata(meta)
            batch_data.append((chunk_id, text, emb.tolist(), json.dumps(cleaned_meta, ensure_ascii=False)))

        try:
            logger.info("truncating documents table")
            self.cursor.execute("TRUNCATE TABLE documents RESTART IDENTITY CASCADE")
            self.conn.commit()

            logger.info("batch insert start")
            psycopg2.extras.execute_batch(
                self.cursor,
                """
                INSERT INTO documents (chunk_id, text, embedding, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                batch_data,
                page_size=100,
            )
            self.conn.commit()
            logger.info("insert done: %d rows", len(batch_data))

            logger.info("creating HNSW index")
            self.cursor.execute("DROP INDEX IF EXISTS documents_embedding_idx")
            # 2000件規模では IVFFLAT の lists=100・probes=1 だと近い記録を取りこぼす。
            # HNSW は既定のパラメータで足りるので、値は指定しない。
            self.cursor.execute(
                """
                CREATE INDEX documents_embedding_idx
                ON documents USING hnsw (embedding vector_cosine_ops)
                """
            )
            self.conn.commit()

            # VACUUM は autocommit でないと動かないので一時的に切り替える。
            old_autocommit = self.conn.autocommit
            self.conn.autocommit = True
            try:
                self.cursor.execute("VACUUM ANALYZE documents")
                logger.info("HNSW index ready")
            finally:
                self.conn.autocommit = old_autocommit

            self._load_metadata()

        except Exception as e:
            self.conn.rollback()
            logger.error("insert failed: %s", e)
            raise

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        chunk_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """ベクトル検索。pgvector のコサイン距離 (0-2) を (2-d)/2 で [0,1] に写像する。

        chunk_ids を渡すと、その中だけを比べる。
        """
        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        if settings["embedding"].get("normalize_embeddings", True):
            norm = np.linalg.norm(query_vector)
            if norm > 0:
                query_vector = query_vector / norm

        query_list = query_vector[0].tolist()

        where = ""
        params: List[Any] = [query_list]
        if chunk_ids is not None:
            where = "WHERE chunk_id = ANY(%s)"
            params.append(list(chunk_ids))
        params += [query_list, top_k]

        try:
            if chunk_ids is not None:
                # 絞り込むときは近似の索引（HNSW）を使わず、対象の記録を全部比べる。
                # 索引をたどると、条件に合わない記録で候補を使い切って件数が足りなくなることがある。
                self.cursor.execute("SET LOCAL enable_indexscan = off")
            self.cursor.execute(
                f"""
                SELECT
                    text,
                    metadata,
                    (2.0 - (embedding <=> %s::vector)) / 2.0 AS score
                FROM documents
                {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            rows = self.cursor.fetchall()
            self.conn.commit()  # _load_metadata と同じ理由で閉じる

            results = []
            for row in rows:
                score = max(0.0, min(1.0, float(row["score"])))
                item = dict(row["metadata"])
                item["text"] = row["text"]
                results.append((item, score))
            return results

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning("db connection lost, reconnecting: %s", e)
            self._connect()
            return self.search(query_vector, top_k, chunk_ids)
        except Exception as e:
            self.conn.rollback()
            logger.error("pgvector search failed: %s", e)
            return []

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("pgvector connection closed")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
