DROP INDEX IF EXISTS chunks_embedding_idx;
ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
