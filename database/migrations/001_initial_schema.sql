-- ============================================================================
-- AssistChat: 初期スキーマ定義
-- ============================================================================
-- 説明: RAG検索システムの基本スキーマ
--       - documents テーブル: ベクトル検索用ドキュメントストレージ
--       - pgvector 拡張の有効化
-- ============================================================================

-- ----------------------------------------------------------------------------
-- pgvector拡張を有効化
-- ベクトル型（vector）を使用するために必要
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- documentsテーブル作成
-- 
-- カラム説明:
--   id: 自動採番の主キー
--   chunk_id: ドキュメントチャンクの一意識別子（アプリ側で生成）
--   text: ドキュメントの本文（検索対象テキスト）
--   embedding: 768次元の埋め込みベクトル（Sentence-BERT）
--   metadata: チャンクの情報（JSONB形式）。doc_id と記録の項目（工場・ライン・設備・日付など）
--             絞り込みの候補と詳細の表示に使う
--   created_at: レコード作成日時
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    text TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- テーブル・カラムコメント
-- PostgreSQLのメタデータとして保存（ドキュメント化）
-- ----------------------------------------------------------------------------
COMMENT ON TABLE documents IS 'RAG 検索用ドキュメントストレージ（本文・埋め込み・メタデータ）';
COMMENT ON COLUMN documents.id IS '自動採番の主キー';
COMMENT ON COLUMN documents.chunk_id IS 'アプリケーション側で生成するチャンク識別子';
COMMENT ON COLUMN documents.text IS 'ドキュメント本文（検索対象）';
COMMENT ON COLUMN documents.embedding IS 'Sentence-BERT埋め込みベクトル（768次元、正規化済み）';
COMMENT ON COLUMN documents.metadata IS 'チャンクの情報（JSONB）。doc_id と記録の項目（工場・ライン・設備・日付など）を含む';
COMMENT ON COLUMN documents.created_at IS 'レコード作成日時';
