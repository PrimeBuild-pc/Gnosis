# Gnosis: coding-agent procedures

- Homelab installation or control: read `README.md` (limits, Discord, agents). Before backup,
  restore, retention, updates, or selfcheck commands, read `docs/operations.md`.
- Scope: one globally trusted operator, not a multi-tenant SaaS. The web selector is not an ACL.
  Discord commands must require a workspace, verifiable guild, fail-closed roles, filters before
  ranking, channel permissions, and ephemeral replies without mentions.
- Work only in the requested checkout; check `git status` and preserve others' changes.
  Test offline with fake DB/providers/Discord. Verification commands are in README; selfcheck
  writes fixtures and migrations and requires an explicitly authorized database.
- Agree on host, servers/workspaces, and actions before installing, contacting platforms,
  downloading models, publishing digests, or changing permissions. Wipe/prune/restore/volumes
  require specific consent and a verified backup. No implicit deployments or commits.
- Users enter secrets/login/2FA. Do not read real `.env` files, sessions, or backups, or print
  credentials/headers/webhooks. Use `.env.example` and temporary fixtures for checks.
- Control after consent: `gnosis` CLI/Docker Compose, authenticated admin API `/docs`, or browser
  with an authorized session. No new global token, MCP, or Docker socket in the container.
  The admin API and Telegram bot have global visibility: trusted agents/operators only.
- Keep platform I/O asynchronous in `collectors/`, immutable configuration in `config.py`,
  and persistence in `db.py` with numbered SQL migrations in `migrations/`.
  Update the schema through the CLI, not during web startup.
- Check callers and regression tests for every scope/config change. Report results and anything
  left unverified; coding-agent subscriptions do not include chat-model API credit.
- UI and interactive bots support en/it/es/ru/zh with English fallback; browser negotiation and
  saved preference select the UI locale, and request locale controls RAG. Preserve archived
  digests in their generation language (including existing Italian); new scheduled digests use
  English. Operator CLI and installer output remain English-only.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
