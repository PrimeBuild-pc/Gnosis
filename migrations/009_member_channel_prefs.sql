-- A member's own channel choice for /gnosis resume. It only narrows what the member
-- may read and the administrator has not excluded; it can never widen it.
CREATE TABLE IF NOT EXISTS member_channel_prefs (
    guild_id text NOT NULL,
    user_id text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('only', 'exclude')),
    channel_ids text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (guild_id, user_id)
);
