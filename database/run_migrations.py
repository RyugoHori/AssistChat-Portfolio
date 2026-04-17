"""DB マイグレーション実行スクリプト（冪等・履歴管理付き）。

使い方:
    python database/run_migrations.py
"""

import logging
import sys
from pathlib import Path
from typing import List, Set

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.config import settings


def get_connection():
    db_config = settings["database"]
    logger.debug("db connect: %s:%s/%s", db_config["host"], db_config["port"], db_config["name"])
    try:
        return psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["name"],
            user=db_config["user"],
            password=db_config["password"],
        )
    except psycopg2.OperationalError as e:
        logger.error("db connect failed: %s", e)
        logger.error("環境変数（DB_HOST など）を確認してください")
        raise


def get_migration_files(migrations_dir: Path) -> List[Path]:
    """*.sql を 001_, 002_, ... の順にソートして返す。"""
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        logger.warning("no migration files in: %s", migrations_dir)
    return migration_files


def get_applied_migrations(cursor) -> Set[str]:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
        """
    )
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def apply_migration(cursor, migration_file: Path, version: str) -> None:
    """SQL 実行 → schema_migrations へ履歴追記。失敗時はロールバック。"""
    logger.info("applying: %s", version)

    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        cursor.execute(sql)
        cursor.execute(
            """
            INSERT INTO schema_migrations (version, description)
            VALUES (%s, %s)
            """,
            (version, f"Applied {migration_file.name}"),
        )
        logger.info("applied: %s", version)
    except Exception as e:
        logger.error("migration failed: %s (%s)", version, e)
        raise


def run_migrations() -> int:
    logger.info("migrations start")

    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = get_migration_files(migrations_dir)
    if not migration_files:
        logger.info("no migrations to apply")
        return 0

    logger.info("found %d migration files", len(migration_files))

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    applied_count = 0
    try:
        applied = get_applied_migrations(cursor)
        conn.commit()

        if applied:
            logger.info("already applied: %d", len(applied))

        for migration_file in migration_files:
            version = migration_file.stem
            if version in applied:
                logger.info("skip (already applied): %s", version)
                continue
            apply_migration(cursor, migration_file, version)
            conn.commit()
            applied_count += 1

        if applied_count > 0:
            logger.info("applied %d new migrations", applied_count)
        else:
            logger.info("all migrations up to date")

        return applied_count

    except Exception as e:
        logger.error("migration aborted: %s", e)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    try:
        run_migrations()
        sys.exit(0)
    except Exception as e:
        logger.error("fatal: %s", e)
        sys.exit(1)
