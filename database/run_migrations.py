"""
データベースマイグレーション実行スクリプト

DDL をアプリケーションコードから分離し、本番運用レベルの DB 管理を実現する。

特徴:
- 冪等性: 何度実行しても安全（適用済みはスキップ）
- 履歴管理: schema_migrations テーブルで管理
- エラーハンドリング: 失敗時のロールバック

使い方:
    python database/run_migrations.py
    
    # 初回実行時: 全マイグレーション適用
    # 2回目以降: 新規マイグレーションのみ適用
"""

import psycopg2
import sys
import logging
from pathlib import Path
from typing import Set, List

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "packages" / "rag-core"))

from rag_core.config import settings


def get_connection():
    """
    データベース接続を取得
    
    config.py の設定を使用。
    環境変数（DB_HOST, DB_PORT等）から自動取得。
    
    Returns:
        psycopg2.connection: DB接続オブジェクト
    
    Raises:
        psycopg2.OperationalError: 接続失敗時
    """
    db_config = settings["database"]
    
    logger.debug(f"DB接続試行: {db_config['host']}:{db_config['port']}/{db_config['name']}")
    
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["name"],
            user=db_config["user"],
            password=db_config["password"]
        )
        logger.debug("DB接続成功")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"DB接続失敗: {e}")
        logger.error("環境変数（DB_HOST, DB_PORT等）を確認してください")
        raise


def get_migration_files(migrations_dir: Path) -> List[Path]:
    """
    マイグレーションファイルを取得
    
    *.sql ファイルを名前順（数字順）でソート。
    001_xxx.sql, 002_xxx.sql, ... の順で実行される。
    
    Args:
        migrations_dir: マイグレーションディレクトリ
    
    Returns:
        マイグレーションファイルのリスト（ソート済み）
    """
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        logger.warning(f"マイグレーションファイルが見つかりません: {migrations_dir}")
    else:
        logger.debug(f"マイグレーションファイル発見: {len(migration_files)}件")
        for f in migration_files:
            logger.debug(f"  - {f.name}")
    
    return migration_files


def get_applied_migrations(cursor) -> Set[str]:
    """
    適用済みマイグレーション一覧を取得
    
    schema_migrationsテーブルから取得。
    テーブルが存在しない場合は作成。
    
    Args:
        cursor: DBカーソル
    
    Returns:
        適用済みバージョン番号のSet
    """
    # schema_migrationsテーブル作成（冪等性）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)
    
    cursor.execute("""
        COMMENT ON TABLE schema_migrations IS 'マイグレーション実行履歴';
        COMMENT ON COLUMN schema_migrations.version IS 'マイグレーションファイル名（拡張子なし）';
        COMMENT ON COLUMN schema_migrations.applied_at IS '適用日時';
    """)
    
    # 適用済み一覧取得
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
    applied = {row[0] for row in cursor.fetchall()}
    
    return applied


def apply_migration(cursor, migration_file: Path, version: str) -> None:
    """
    マイグレーションを適用
    
    SQL実行 → 履歴記録 の順で実行。
    エラー時は自動的にロールバック（autocommit=False）。
    
    Args:
        cursor: DBカーソル
        migration_file: マイグレーションファイル
        version: バージョン番号
    
    Raises:
        Exception: SQL実行エラー時
    """
    logger.info(f"📝 実行中: {version}")
    
    # SQLファイル読み込み
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    try:
        # SQL実行
        cursor.execute(sql)
        
        # 履歴記録
        cursor.execute(
            """
            INSERT INTO schema_migrations (version, description) 
            VALUES (%s, %s)
            """,
            (version, f"Applied {migration_file.name}")
        )
        
        logger.info(f"✅ 完了: {version}")
        
    except Exception as e:
        logger.error(f"❌ エラー: {version}")
        logger.error(f"   {e}")
        raise


def run_migrations() -> int:
    """
    マイグレーション実行（メイン処理）
    
    Returns:
        適用したマイグレーション件数
    
    Raises:
        Exception: DB接続エラー、SQL実行エラー等
    """
    logger.info("=" * 80)
    logger.info("マイグレーション実行開始")
    logger.info("=" * 80)
    
    # マイグレーションファイル取得
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = get_migration_files(migrations_dir)
    
    if not migration_files:
        logger.info("適用するマイグレーションがありません")
        return 0
    
    logger.info(f"マイグレーションファイル: {len(migration_files)}件")
    
    # DB接続
    conn = get_connection()
    conn.autocommit = False  # トランザクション有効化
    cursor = conn.cursor()
    
    applied_count = 0
    
    try:
        # 適用済みマイグレーション取得
        applied = get_applied_migrations(cursor)
        conn.commit()
        
        if applied:
            logger.info(f"適用済み: {len(applied)}件")
            for v in sorted(applied):
                logger.debug(f"  - {v}")
        
        # マイグレーション実行
        for migration_file in migration_files:
            version = migration_file.stem  # ファイル名（拡張子なし）
            
            if version in applied:
                logger.info(f"⏭️  スキップ: {version} (適用済み)")
                continue
            
            # マイグレーション適用
            apply_migration(cursor, migration_file, version)
            conn.commit()
            applied_count += 1
        
        # 結果サマリー
        logger.info("=" * 80)
        if applied_count > 0:
            logger.info(f"✅ {applied_count}件の新しいマイグレーションを適用しました")
        else:
            logger.info("✅ すべてのマイグレーションが適用済みです")
        logger.info("=" * 80)
        
        return applied_count
        
    except Exception as e:
        logger.error(f"マイグレーション失敗: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()
        logger.debug("DB接続をクローズしました")


if __name__ == "__main__":
    try:
        run_migrations()
        sys.exit(0)
    except Exception as e:
        logger.error(f"致命的エラー: {e}")
        sys.exit(1)
