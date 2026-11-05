-- Administrators may run Gnosis only as a digest publisher: when false, the member
-- /gnosis commands (except deleting one's own key) are refused on that server.
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS member_commands_enabled boolean NOT NULL DEFAULT true;
