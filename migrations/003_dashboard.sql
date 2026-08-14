ALTER TABLE messages ADD COLUMN IF NOT EXISTS author_id text;
CREATE INDEX IF NOT EXISTS messages_author_idx ON messages (source_id, author_id);

CREATE TABLE IF NOT EXISTS worker_status (
    component text PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('ok', 'error')),
    detail text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings (
    key text PRIMARY KEY,
    value text
);

CREATE TABLE IF NOT EXISTS ignored_authors (
    platform text NOT NULL CHECK (platform IN ('telegram', 'discord', 'reddit')),
    author_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (platform, author_id)
);

CREATE TABLE IF NOT EXISTS api_usage (
    id bigserial PRIMARY KEY,
    kind text NOT NULL,
    model text NOT NULL,
    prompt_tokens integer NOT NULL DEFAULT 0,
    completion_tokens integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS api_usage_created_idx ON api_usage (created_at DESC);
