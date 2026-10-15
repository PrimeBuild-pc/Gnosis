# Operations

Prerequisites and permissions: [README](../README.md). Run all commands from the Gnosis directory.
The API and CLI are tools for the global operator, not isolated tenants.

## Status and reload

```bash
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail=100 worker web
```

`/health` only confirms that the web service responds. Check the Status page for connectors.
Logs may contain private details/provider errors: sanitize them before sharing.

- Credentials/endpoint/model changed: `docker compose up -d --force-recreate web worker`.
  `restart` does not reload Docker's env_file. Chat keys saved in the dashboard apply immediately
  to the web process only; the worker must still be recreated.
- Source allowlist changed: `docker compose restart worker`. Search immediately excludes a
  disabled source, but the collector keeps its configuration until restart.
- Workspace roles and mappings: applied from the DB on the next command, without restart.

### Languages and archived content

The dashboard and interactive bots support `en`, `it`, `es`, `ru`, and `zh`, with English as
fallback. Browser language negotiation and a saved explicit preference select the dashboard
language; the request locale also controls RAG answers. Source messages are not translated.
The operator CLI and installer remain English-only.

Archived digests remain in the language used when generated, not the viewer's current language.
Existing Italian digests are retained unchanged. New scheduled digests are generated in English;
changing the UI/bot locale does not regenerate or translate the archive.

## Selfcheck (writes temporary fixtures)

```bash
docker compose run --rm web gnosis selfcheck
```

Only on an authorized database: it applies migrations and creates unique fixtures, checks
queries and Discord isolation, then removes its fixtures. It does not disable existing sources.
It is not read-only; an abrupt kill may leave `__selfcheck__` fixtures to remove manually after
inspection. Do not use it to automatically authorize a deployment.

## Backup

Keep the database, `.env`, configuration, and Telegram sessions together. Sessions are equivalent
to credentials, and the dump includes messages, roles, and webhooks. Use encryption and an off-host
copy. On Linux:

```bash
umask 077
mkdir -p backups
chmod 700 backups
docker compose stop worker web
docker compose exec -T db pg_dump -U gnosis -Fc gnosis > backups/gnosis.dump
cp .env backups/env.backup
cp config/sources.toml backups/sources.toml
docker compose run --rm --no-deps --entrypoint tar worker -C /data -cf - telegram > backups/telegram.tar
docker compose up -d
```

If any command fails, verify the backup before treating it as valid; restart services when safe.
The DB keeps running, but there are no application writers during the copy.
Encrypt the backup with your usual tool; do not commit `backups/` or upload it to issues.

### Restore (destructive: authorization and backup required)

Restore only trusted backups compatible with the code version. Start only `db`, keeping
web/worker stopped. For a new installation, first prepare `.env`, config, and permissions per README.

```bash
docker compose stop worker web
docker compose up -d db
docker compose exec -T db pg_restore -U gnosis -d gnosis --clean --if-exists --exit-on-error < backups/gnosis.dump
cp backups/env.backup .env
cp backups/sources.toml config/sources.toml
docker compose run --rm --no-deps --entrypoint tar worker -C /data -xf - < backups/telegram.tar
sudo chgrp 10001 .env config config/sources.toml
chmod 660 .env config/sources.toml
chmod 2770 config
docker compose up -d --force-recreate
```

The PostgreSQL password in the destination volume must match the one restored in `.env`;
restoring the file does not change the PostgreSQL user. Do not proceed if the restore fails.
Verify access, Status, and a sample of sources before re-enabling webhooks.

## Retention and deletion

Settings → Data retention: maximum message age in days (default: no expiration).
The worker deletes messages and chunks hourly. One-off CLI:

```bash
docker compose run --rm worker gnosis prune --before 2025-01-01
```

`prune`/retention do not delete saved digests. A deletion received from the platform also does
not rewrite historical digests: they may retain derived information. Discord `/digest` still
checks citations; the admin remains authorized for the global archive.
The **wipe** function deletes all collected memory; it is not limited to the selected workspace.
The worker may collect messages again on the next backfill: for lasting erasure, stop/disable
sources and handle backups/digests too. Reddit does not guarantee retroactive deletion events;
follow current terms and handle removal requests.

## Update / rollback

After backing up and checking that the checkout has no local changes to preserve:

```bash
docker compose stop worker web
git pull --ff-only
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d --force-recreate
```

Verify `/health`, Status, and workspace configuration. Volumes remain: **never use `down -v`**
to update. A code rollback may also require a compatible DB restore: migrations have no automatic
downgrade. Do not rotate only POSTGRES_PASSWORD on an existing volume; see README for the
PostgreSQL procedure.
