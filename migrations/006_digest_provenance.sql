-- Check every input message against current permissions before sharing a stored digest.
-- Legacy digests have no provable input set: Discord commands must refuse them.
ALTER TABLE digests ADD COLUMN IF NOT EXISTS message_ids bigint[] NOT NULL DEFAULT '{}';
