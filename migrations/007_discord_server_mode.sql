-- Discord "server mode": read every channel the bot can see (minus exclusions), post
-- digests to a channel at a chosen frequency, and give members private summary channels.
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS read_all_channels boolean NOT NULL DEFAULT true;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS excluded_channel_ids text[] NOT NULL DEFAULT '{}';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS digest_channel_id text NOT NULL DEFAULT '';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS digest_frequency text NOT NULL DEFAULT 'weekly'
    CHECK (digest_frequency IN ('off', 'daily', 'weekly'));
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS digest_locale text NOT NULL DEFAULT 'en';

-- Channels discovered by "read all" rather than listed in sources.toml. Startup only
-- disables configured sources, so these survive restarts; exclusions disable them.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS auto boolean NOT NULL DEFAULT false;

-- One private /gnosis channel per member and server. Never collected.
CREATE TABLE IF NOT EXISTS private_channels (
    guild_id text NOT NULL,
    user_id text NOT NULL,
    channel_id text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, user_id)
);

-- Members' own OpenAI-compatible credentials for /gnosis resume. The key is encrypted
-- (Fernet); base URL and model are not secret.
CREATE TABLE IF NOT EXISTS user_llm_keys (
    discord_user_id text PRIMARY KEY,
    api_key_encrypted text NOT NULL,
    base_url text NOT NULL DEFAULT '',
    model text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);
