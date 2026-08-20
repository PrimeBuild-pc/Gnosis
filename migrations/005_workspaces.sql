-- Un workspace e' un gruppo di sorgenti interrogabile in isolamento: un server Discord, un
-- gruppo di chat Telegram, una raccolta di subreddit. Serve perche' senza appartenenza ogni
-- risposta mescola tutte le fonti configurate.
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

-- Nullable di proposito: le sorgenti gia' configurate restano senza workspace e continuano a
-- funzionare esattamente come prima, finche' non le si assegna.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS workspace_id bigint
    REFERENCES workspaces(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS sources_workspace_idx ON sources (workspace_id);

-- Un digest per workspace per periodo, invece di uno solo globale.
ALTER TABLE digests ADD COLUMN IF NOT EXISTS workspace_id bigint
    REFERENCES workspaces(id) ON DELETE CASCADE;
ALTER TABLE digests DROP CONSTRAINT IF EXISTS digests_period_start_period_end_key;
-- NULL non e' distinto in un UNIQUE normale: senza NULLS NOT DISTINCT il digest globale
-- (workspace_id NULL) verrebbe duplicato a ogni giro invece di essere aggiornato.
CREATE UNIQUE INDEX IF NOT EXISTS digests_workspace_period_idx
    ON digests (workspace_id, period_start, period_end) NULLS NOT DISTINCT;

-- Cache dei canali/chat che il bot vede: alimenta le tendine della dashboard, cosi' non serve
-- copiare a mano ID a 19 cifre. La riempie il worker, che e' l'unico ad avere le sessioni.
CREATE TABLE IF NOT EXISTS available_sources (
    platform text NOT NULL CHECK (platform IN ('telegram', 'discord', 'reddit')),
    external_id text NOT NULL,
    name text NOT NULL,
    workspace_external_id text NOT NULL DEFAULT '',
    workspace_name text NOT NULL DEFAULT '',
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (platform, external_id)
);
