-- ============================================================================
-- AssistChat: 初期スキーマ定義
-- ============================================================================
-- 作成日: 2025-02-08
-- Phase: 2 → 3 移行
-- 説明: RAG検索システムの基本スキーマ
--       - documents テーブル: ベクトル検索用ドキュメントストレージ
--       - pgvector 拡張の有効化
--       - 基本インデックスの作成
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
--   metadata: 検索フィルター用のメタデータ（JSONB形式）
--             - doc_id, title, category, line, equipment など
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
-- インデックス作成
-- 
-- 1. metadata用 GINインデックス
--    - JSONBフィールドの高速検索用
--    - フィルター機能で使用（工場、ライン、設備カテゴリなど）
-- 
-- 2. chunk_id用 B-Treeインデックス
--    - UNIQUE制約による一意性保証
--    - chunk_id検索の高速化
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS documents_metadata_idx 
    ON documents USING GIN (metadata);

CREATE INDEX IF NOT EXISTS documents_chunk_id_idx 
    ON documents (chunk_id);

-- ----------------------------------------------------------------------------
-- テーブル・カラムコメント
-- PostgreSQLのメタデータとして保存（ドキュメント化）
-- ----------------------------------------------------------------------------
COMMENT ON TABLE documents IS 'RAG 検索用ドキュメントストレージ（本文・埋め込み・メタデータ）';
COMMENT ON COLUMN documents.id IS '自動採番の主キー';
COMMENT ON COLUMN documents.chunk_id IS 'アプリケーション側で生成するチャンク識別子';
COMMENT ON COLUMN documents.text IS 'ドキュメント本文（検索対象）';
COMMENT ON COLUMN documents.embedding IS 'Sentence-BERT埋め込みベクトル（768次元、正規化済み）';
COMMENT ON COLUMN documents.metadata IS '検索フィルター用メタデータ（JSONB）。doc_id, title, category, lineなどを含む';
COMMENT ON COLUMN documents.created_at IS 'レコード作成日時';
