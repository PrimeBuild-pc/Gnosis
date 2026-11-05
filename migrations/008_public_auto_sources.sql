-- Channels found by "read all" may be staff-only. Server digests are posted publicly,
-- so they include an auto channel only when @everyone can view it. Private channels stay
-- available to /gnosis resume, which checks each member's own permissions.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS public boolean NOT NULL DEFAULT false;
