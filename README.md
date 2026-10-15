<p align="center">
  <img src="docs/assets/in-development.svg" alt="In development" width="420">
</p>

<p align="center">
  <img src="docs/assets/banner.svg" alt="Gnosis — private knowledge base for communities" width="100%">
</p>

<p align="center">
  <a href="https://github.com/PrimeBuild-pc/Gnosis/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=git&amp;logoColor=white"></a>
  <a href="https://github.com/PrimeBuild-pc/Gnosis/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=github"></a>
  <a href="https://github.com/PrimeBuild-pc/Gnosis/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=github"></a>
</p>

<p align="center">
  <a href="https://github.com/PrimeBuild-pc/Gnosis/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/PrimeBuild-pc/Gnosis/ci.yml?branch=main&amp;style=plastic&amp;logo=githubactions&amp;label=CI"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2ea44f?style=plastic"></a>
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-your%20infrastructure-2dd4a7?style=plastic">
  <img alt="Privacy-first" src="https://img.shields.io/badge/privacy-first-2dd4a7?style=plastic">
</p>

<p align="center">
  <img alt="Python 3.11 or later" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=plastic&amp;logo=python&amp;logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?style=plastic&amp;logo=fastapi&amp;logoColor=white">
  <img alt="PostgreSQL 16" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=plastic&amp;logo=postgresql&amp;logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker-Compose-2496ED?style=plastic&amp;logo=docker&amp;logoColor=white">
</p>

<p align="center"><i>Collect authorized content, search your sources, and get answers with citations to the original messages.</i></p>

---

# Gnosis

A private knowledge base for authorized Discord, Telegram, and Reddit content: collection,
PostgreSQL/pgvector hybrid search, answers with citations, digests, and a multilingual dashboard.
Python 3.11+, FastAPI, vanilla JavaScript, Docker Compose. In development, MIT license.

## Before you start: limits and costs

- **One trusted operator**, with one HTTP Basic admin account. The dashboard and API administer
  the entire installation: the workspace selector is a filter, **not** an authorization boundary
  between web users. This is not a public multi-tenant SaaS. For administrators who must not see
  each other's data, use separate installations, databases, credentials, and volumes.
- The same Discord bot can serve multiple servers. Commands require a workspace explicitly
  mapped to the server ID and its roles; missing mappings or empty roles deny access.
  `/ask` uses only messages from the server, workspace, and channels the member can read.
  Replies are private (ephemeral), without automatic mentions. `/digest` checks all stored
  input messages against current permissions, not just citations; digests predating
  migration 006 are not shown by Discord until regenerated.
- The dashboard, graph, and authorized Telegram bot can access **all** sources.
  Telegram replies only in private conversations: authorize trusted operators only.
- Self-hosting does not mean offline: Discord/Telegram/Reddit require network access and APIs.
  If you use remote chat or embeddings, processed content is sent to the provider. Default
  embeddings are local; the build downloads the model from third parties and needs network
  access, disk space, and RAM.
- **ChatGPT/Codex/Claude/Pi and coding-agent subscriptions are not OpenAI API credit.**
  Remote providers need API credentials and separate billing. Free tiers may change, impose
  quotas, or lack your chosen model. You can use an already available OpenAI-compatible local
  chat model: buying an OpenAI key is not required.
- Valid citations do not guarantee the model interpreted the source correctly.
  Check originals before making decisions. Do not collect content without consent.

## Languages

The dashboard and interactive Discord/Telegram bots support English (`en`), Italian (`it`),
Spanish (`es`), Russian (`ru`), and Chinese (`zh`), with **English as the default**. The dashboard
negotiates the browser language on first use and saves an explicit language choice. The request
locale controls RAG answer generation; changing the interface language does not translate source
messages. Bots use the supported language from the interaction/user locale, falling back to English.

Archived digests are not dynamically translated: they remain in their original generation language.
Existing Italian digests are retained unchanged; newly scheduled digests are generated in English.
Operator-facing CLI commands and the guided installer are English-only.

## Recommended homelab installation (Linux + Docker)

### 1. Prepare the machine

Install Git, [Docker Engine](https://docs.docker.com/engine/install/), and the
[Docker Compose](https://docs.docker.com/compose/install/) plugin **>= 2.30** (a current version is recommended).
On Windows/macOS, use Docker Desktop and a Linux/WSL shell for the commands below.
You do not need a domain or open router ports.

```bash
docker version
docker compose version
git clone https://github.com/PrimeBuild-pc/Gnosis.git
cd Gnosis
```

Allow a few GB of free space and RAM for PostgreSQL and the embedding model; local chat-model
requirements are separate. No particular cloud tier is guaranteed to be free or sufficient.
The app uses CPU for embeddings and does not require a GPU for the default model.

Docker group membership is effectively root access: add only trusted users. The installer
does not install Docker, change host groups, or execute scripts downloaded from the network.

### 2. Choose guided or manual installation

**Guided**, after reading `install.sh`:

```bash
./install.sh
```

It asks for admin credentials and chat configuration, generates a database password for new
installations, creates an empty allowlist, and builds the local checkout. It may request `sudo`
solely to assign the files' group to the container group. It does not enable platforms or download
chat models. The build downloads dependencies and the embedding model. Unchanged credentials are
preserved; do not use it to automatically rotate the password of an existing database.

**Manual**, equivalent steps:

```bash
umask 077
cp .env.example .env
printf '# Add only authorized sources.\n' > config/sources.toml
```

Open `.env` in a local editor. Set:

```dotenv
POSTGRES_PASSWORD=YOUR_RANDOM_ALPHANUMERIC_DATABASE_PASSWORD
DATABASE_URL=postgresql://gnosis:YOUR_RANDOM_ALPHANUMERIC_DATABASE_PASSWORD@db:5432/gnosis
GNOSIS_USERNAME=admin
GNOSIS_PASSWORD=YOUR_UNIQUE_LONG_ADMIN_PASSWORD
```

Generate passwords in your password manager. Repeat the same database password in both fields;
use alphanumeric characters to avoid URL encoding. **Do not share or paste the file into an agent
chat.** `.env` is excluded from Git and uses Compose dotenv syntax. For manual editing, prefer
alphanumeric credentials; special characters require correct quoting and escaping (a literal `$`
becomes `$$` inside double quotes). The installer and dashboard automatically serialize quotes
and backslashes too. Multiline values are not supported. `change-me` or an empty admin password
prevents startup.

Configure chat in one of two ways:

```dotenv
# OpenAI API (separate billing)
OPENAI_API_KEY=YOUR_API_KEY
OPENAI_CHAT_MODEL=gpt-4o-mini
```

or:

```dotenv
# Remote OpenAI-compatible endpoint or your own already configured local server
GNOSIS_CHAT_API_KEY=local
GNOSIS_CHAT_BASE_URL=http://YOUR_MODEL_SERVICE:11434/v1
OPENAI_CHAT_MODEL=YOUR_INSTALLED_MODEL_NAME
```

`local` is just a nonempty value for servers that do not require a key: it does not bypass
remote-provider authentication. Inside a container, `127.0.0.1` is the container itself:
use a service name on the same private Docker network. Docker Desktop supports
`host.docker.internal`; on Linux, the `host-gateway` mapping and model-server connectivity
must be configured explicitly. Do not expose an unauthenticated model server to the Internet
to solve this problem. Models must be installed by the operator, not automatically downloaded
by the agent.

You can leave chat unconfigured to open the dashboard; the worker waits for a nonempty key
and will report an error while it is missing. Keep embeddings local (`local`, dimensions `384`).
Changing provider/model/dimensions with existing data requires a migration and reindexing:
`db-init` does not reapply migrations that have already run.

### 3. Protect files and start

The container uses UID/GID **10001**, not root. On a dedicated Linux host, check that group
10001 contains no other host users; share write access only with this group:

```bash
sudo chgrp 10001 .env config config/sources.toml
chmod 660 .env config/sources.toml
chmod 2770 config
docker compose config --quiet
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d
```

Keep the host file owner: these permissions allow the operator's editor and dashboard to
write without `chmod 666`/`777`. Desktop bind mounts have different semantics: verify dashboard
writes and do not grant everyone access as a workaround.

The local build runs the checkout's changes: pulling the registry's `latest` tag might
retrieve an older version. The embedding model is included in the image; we have not performed
downloads/deployment to verify this guide.

### 4. Open and verify

```bash
docker compose ps
curl --fail http://127.0.0.1:8080/health
```

Open <http://127.0.0.1:8080> and sign in with the admin credentials. `/health` is public and only
indicates that the web service responds, not that Discord/chat are ready. The **Status** page
shows the worker, pipeline, and source activity. API, assets, and `/docs` documentation require
authentication.

If the machine is remote, run this from your computer:

```bash
ssh -N -L 8080:127.0.0.1:8080 USER@HOMELAB_HOST
```

Open the same local URL. Compose publishes only on loopback; PostgreSQL exposes no host ports.
HTTP Basic does not encrypt traffic: for access outside the tunnel, use HTTPS with a proxy and
firewall. Do not publish port 8080 directly. The proxy must preserve the correct Host and scheme
for same-origin checks; accept forwarded headers only from trusted proxies. There is no built-in
brute-force protection: do not treat this dashboard as a public service.

## Discord: step-by-step setup, including multiple servers

1. Obtain consent from server administrators and content owners.
2. Open <https://discord.com/developers/applications>, **New Application**, then **Bot**.
   Copy/reset the bot token and enter it in `DISCORD_BOT_TOKEN` on the dashboard's Discord
   page (or in `.env`). It is a credential: user tokens/self-bots are not supported.
3. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent**. This
   implementation does not require Presence or Server Members Intent. If Discord requires
   intent approval for your bot, complete that process before starting it.
4. In **OAuth2 → URL Generator**, select `bot` and `applications.commands`. Minimum permissions
   in authorized channels: **View Channels**, **Read Message History**, **Send Messages**
   for replies. Do not grant **Administrator**, server/role management, or member kicks.
   Open the link, choose the server, and approve. Repeat for each authorized server.
5. After saving credentials, recreate the processes (a simple `restart` does not reread `.env`):

   ```bash
   docker compose up -d --force-recreate web worker
   ```

6. Enable Discord **User Settings → Advanced → Developer Mode**. Copy the **server** ID and
   authorized **role** IDs (not user IDs or role names).
7. In dashboard **Settings → Workspaces**, create a uniquely named workspace with the server
   ID. Select it at the top; on the **Discord** page, save comma-separated role IDs.
   A workspace without roles denies all commands. The old global variable
   `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` is deprecated and no longer grants access.
8. On **Discord → Sources**, select only the channels to read from the dropdown.
   Use exactly the workspace name you created, even if it differs from the server name
   suggested by the dropdown. Discovered channels are not automatically authorized for collection.
   Specify concrete topics (for example `Linux, backup, homelab`) for the relevance filter.
9. After allowlist changes:

   ```bash
   docker compose restart worker
   ```

10. Test `/ask` with a member who has the role, then without the role. Test in the second server:
    no source from the first server should appear. An unmapped server denies access even if
    the bot has been invited. Discord DM commands cannot access the knowledge base.

Global command synchronization may take time. The collector reads the latest 200 accessible
messages at startup, then live events/edits/deletions. Sources must be text channels:
threads/forums are not included in the `/ask` authorization flow. Permissions are read from
the event-updated Discord cache, not a REST request for each command. Historical messages
without a verifiable `guild_id` are excluded from commands.

### Digests and restricted channels

Automatic digests are **per workspace**, not per member. A webhook publishes the entire digest
to its destination: `/ask` roles do not protect a webhook. Choose a destination channel whose
audience is authorized for **all** sources in the workspace; otherwise leave the webhook empty.
Do not mix servers within workspaces. An admin can deliberately configure cross-platform sources:
this does not give Discord members permission to read them. Digests for Discord workspaces
include only messages with a verifiable guild matching the mapping.

Create the webhook in **Channel Settings → Integrations → Webhooks**, and save it in the workspace.
The dashboard shows only a masked indicator; an empty field preserves the value. To revoke it,
the owner can send `digest_webhook: ""` to the authenticated API or revoke it in Discord.
Workspaces without a destination do not use the global webhook. When workspaces exist, the worker
does not create or publish a global digest; manual global generation stays archived without a push.
Configuring the wrong destination remains the operator's responsibility.

## Telegram and Reddit (optional)

See [platform setup](docs/setup-platforms.md). Telegram requires `TELEGRAM_API_ID`,
`TELEGRAM_API_HASH`, an interactive login, and the session in the `telegram-data` volume:

```bash
docker compose stop worker
docker compose run --rm worker gnosis telegram-login
docker compose up -d worker
```

The separate Telegram bot requires a BotFather token and `GNOSIS_TELEGRAM_ALLOWED_USERS`;
it is only for operators authorized to access the entire database and replies only in private.
Reddit requires OAuth credentials and compliance with current terms/rate limits. No platform
is required to open the dashboard. `config/sources.example.toml` is documentation only:
do not copy demonstration sources into a real installation without authorization.

## Installation and control with an AI agent

You can ask a coding agent to read `AGENTS.md` and this guide and prepare installation,
nonsensitive configuration, checks, or later control through the **existing CLI**, authenticated
**`/docs` API**, or browser. No new MCP, universal token, or Docker socket access from the
container is needed. Agent harness/SSH/browser permissions remain necessary and separate from
both Discord permissions and chat-provider billing.

Recommended procedure:

1. Define the host, repository, workspaces/servers, and allowed actions. The agent proposes
   commands with their effects, costs/downloads, and rollback; it obtains your consent before running them.
2. Enter passwords, tokens, login/2FA, and Discord invitations yourself. Do not let `.env`,
   Authorization headers, webhooks, sessions, or backups appear in logs/transcripts. Use an
   already authenticated browser session or a credentials channel approved by your harness,
   not credentials in the prompt.
3. After consent, the agent may install/recreate only the agreed stack, check `/health`, read
   Status, and test sources with synthetic data. It can configure workspaces and the allowlist
   through the same APIs as the dashboard.
4. For later control, grant limited access to the same host and specify an action list:
   for example checks, restarts, backups, updates. Every scope expansion, digest publication,
   model download, permission change, private-data read, or destructive operation (`wipe`,
   `prune`, restore, workspace/volume deletion) requires specific consent.

The admin API grants global privileges: there are no read-only or workspace-scoped agent tokens.
Do not grant it to an untrusted agent. You can revoke the session/harness/SSH access and rotate
the admin password; platform credentials must be revoked separately. This guide enables a
workflow; it does not claim the agent has already installed or checked your system.

## Backups, updates, and troubleshooting

See [operations](docs/operations.md) for full backup, restore, and retention procedures.
Before updating, save the database, `.env`, `config/sources.toml`, and Telegram sessions in a
protected backup. Volumes persist across restarts; **`docker compose down -v` deletes data**.

```bash
# After backup; stop writers during migrations/updates
 docker compose stop worker web
 git pull --ff-only
 docker compose build
 docker compose run --rm web gnosis db-init
 docker compose up -d --force-recreate
```

**Existing installations:** add `POSTGRES_PASSWORD` with the **current** PostgreSQL password
and keep `DATABASE_URL` consistent. The variable does not change users in an already initialized
volume. If the password is still `gnosis`, rotate it with `\password gnosis` in a
`docker compose exec db psql -U gnosis` session, then update both fields and recreate web/worker;
back up first. Configure workspace mappings and roles: the old global Discord fallback is removed.

| Symptom | Check / solution |
|---|---|
| Docker/Compose unavailable | Install the plugin >= 2.30, check the daemon and permissions; do not chmod the socket |
| `permission denied` saving config | Check the host owner, GID 10001, and permissions of the three paths above; avoid 666/777 |
| Worker errors without a key | Set a real API key or dummy `local` + local endpoint, then recreate containers |
| Chat model not found / 429 | Check model name, endpoint, provider quotas and billing; agent subscription ≠ API |
| Channels not visible / empty messages | Bot token, invitation, View Channel/History, Message Content Intent, and Status page |
| `/ask` denies access | Server ID, workspace, nonempty roles, and member role; no global fallback |
| Sources not collected after saving | Restart worker; selecting a workspace alone does not enable a channel |
| No results | Processed messages, topics/filter, enabled sources, and correct workspace |
| Digest unavailable | No messages in the previous week or citations not currently accessible |
| Database authentication failed | Existing user's password and DATABASE_URL must match; do not delete the volume |
| Local model URL unreachable | Container loopback is not the host; check private networking/model service |

## Development and offline checks

```bash
python -m venv .venv
. .venv/bin/activate  # PowerShell: .venv\Scripts\Activate.ps1
pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
node tests/frontend.cjs
bash tests/install-selfcheck.sh
bash -n install.sh
```

The frontend has no dependencies/build tools. Tests mock the DB, providers, and Discord:
no Discord calls, model downloads, or deployments. On an authorized test database,
`gnosis selfcheck` applies migrations, creates uniquely prefixed fixtures, and removes them;
it does not change the real allowlist. This is an SQL check, not a fully read-only check:
ask permission before running it. Large-archive performance and live-platform behavior must
be verified in your environment.

Further references: [dashboard architecture](docs/dashboard-shell.md),
[example configuration](.env.example), [license](LICENSE).
