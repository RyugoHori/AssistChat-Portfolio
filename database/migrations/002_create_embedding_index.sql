-- ベクトル検索用の HNSW 索引（コサイン距離）。
-- 索引を作る処理は、データを入れ直したあとに同じ名前・同じ方式で作り直す。
-- 理由は ARCHITECTURE に書いている。

CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops);

COMMENT ON INDEX documents_embedding_idx IS 'ベクトル検索用の HNSW 索引（コサイン距離）';
