CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_migrations (
    name text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sources (
    id bigserial PRIMARY KEY,
    platform text NOT NULL CHECK (platform IN ('telegram', 'discord', 'reddit')),
    external_id text NOT NULL,
    name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    topics text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (platform, external_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id bigserial PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    author text NOT NULL DEFAULT '',
    sent_at timestamptz NOT NULL,
    text text NOT NULL,
    url text NOT NULL DEFAULT '',
    thread_id text,
    content_hash text NOT NULL,
    relevance real,
    tags text[] NOT NULL DEFAULT '{}',
    kind text,
    metadata jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'ignored', 'failed')),
    processing_error text,
    processed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);
CREATE INDEX IF NOT EXISTS messages_status_idx ON messages (status, sent_at);
CREATE INDEX IF NOT EXISTS messages_sent_at_idx ON messages (sent_at DESC);
CREATE TABLE IF NOT EXISTS chunks (
    id bigserial PRIMARY KEY,
    message_id bigint NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    position integer NOT NULL,
    text text NOT NULL,
    embedding vector(1536) NOT NULL,
    search_document tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
    UNIQUE (message_id, position)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_search_idx ON chunks USING gin (search_document);

CREATE TABLE IF NOT EXISTS digests (
    id bigserial PRIMARY KEY,
    period_start timestamptz NOT NULL,
    period_end timestamptz NOT NULL,
    markdown text NOT NULL,
    source_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (period_start, period_end)
);
