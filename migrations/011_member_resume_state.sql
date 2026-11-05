-- Where each member's last undated /gnosis resume ended: the next one covers only
-- what is new since then.
CREATE TABLE IF NOT EXISTS member_resume_state (
    guild_id text NOT NULL,
    user_id text NOT NULL,
    last_end timestamptz NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);
