-- A workspace groups sources for scoped queries: a Discord server, a group of Telegram
-- chats, or a collection of subreddits. Without membership, answers mix all configured sources.
CREATE TABLE IF NOT EXISTS workspaces (
    id bigserial PRIMARY KEY,
    name text NOT NULL UNIQUE,
    platform text CHECK (platform IS NULL OR platform IN ('telegram', 'discord', 'reddit')),
    external_id text,
    allowed_role_ids text[] NOT NULL DEFAULT '{}',
    digest_webhook text NOT NULL DEFAULT '',
    digest_telegram_chat_id text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS workspaces_platform_external_idx
    ON workspaces (platform, external_id) WHERE external_id IS NOT NULL;

-- Deliberately nullable: existing sources keep working without a workspace until assigned.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS workspace_id bigint
    REFERENCES workspaces(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS sources_workspace_idx ON sources (workspace_id);

-- One digest per workspace and period, rather than only one global digest.
ALTER TABLE digests ADD COLUMN IF NOT EXISTS workspace_id bigint
    REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE digests DROP CONSTRAINT IF EXISTS digests_period_start_period_end_key;
-- A normal UNIQUE treats NULL values as distinct: without NULLS NOT DISTINCT the global
-- digest (workspace_id NULL) would be duplicated on every run instead of updated.
CREATE UNIQUE INDEX IF NOT EXISTS digests_workspace_period_idx
    ON digests (workspace_id, period_start, period_end) NULLS NOT DISTINCT;

-- Cache visible channels/chats for dashboard dropdowns, avoiding manual 19-digit IDs.
-- The worker populates it because only the worker has the platform sessions.
CREATE TABLE IF NOT EXISTS available_sources (
    platform text NOT NULL CHECK (platform IN ('telegram', 'discord', 'reddit')),
    external_id text NOT NULL,
    name text NOT NULL,
    workspace_external_id text NOT NULL DEFAULT '',
    workspace_name text NOT NULL DEFAULT '',
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (platform, external_id)
);
