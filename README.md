<p align="center">
  <img src="docs/assets/in-development.svg" alt="in development..." width="420">
</p>

<p align="center">
  <img src="docs/assets/banner.svg" alt="Gnosis" width="100%">
</p>

<p align="center">
  <a href="https://github.com/PrimeBuild-pc/Gnosis/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=git&amp;logoColor=white"></a>
  <a href="https://github.com/PrimeBuild-pc/Gnosis/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=github"></a>
  <a href="https://github.com/PrimeBuild-pc/Gnosis/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/PrimeBuild-pc/Gnosis?style=plastic&amp;logo=github"></a>
</p>

<p align="center">
  <a href="https://github.com/PrimeBuild-pc/Gnosis/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/PrimeBuild-pc/Gnosis/ci.yml?branch=main&amp;style=plastic&amp;logo=githubactions&amp;label=CI"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2ea44f?style=plastic"></a>
  <img src="https://img.shields.io/badge/self--hosted-no%20cloud%2C%20no%20tracking-2dd4a7?style=plastic" alt="Self-hosted">
  <img src="https://img.shields.io/badge/privacy-first-2dd4a7?style=plastic" alt="Privacy-first">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=plastic&amp;logo=python&amp;logoColor=white" alt="Python 3.11 or newer">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?style=plastic&amp;logo=fastapi&amp;logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=plastic&amp;logo=postgresql&amp;logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=plastic&amp;logo=docker&amp;logoColor=white" alt="Docker Compose">
</p>

<p align="center"><i>A private, source-grounded knowledge base for Telegram, Discord, and Reddit. Collect authorized community content, filter noise, generate weekly digests, and ask questions with citations back to the original messages.</i></p>

---

## Overview

Gnosis turns selected online communities into a searchable personal knowledge base. It collects content through official platform APIs, enriches and embeds useful messages, and stores everything in PostgreSQL with pgvector.

Answers are generated only from retrieved content and include links to the original platform messages whenever available.

### Key features

- Official connectors for **Telegram**, **Discord**, and **Reddit**
- Explicit source allowlist
- Idempotent ingestion and message update handling
- Relevance filtering, tagging, chunking, and embeddings
- Hybrid PostgreSQL full-text and pgvector retrieval
- Source-grounded RAG answers with validated citations
- Weekly cited digests
- Private web interface protected with HTTP Basic authentication
- Reproducible deployment with Docker Compose

## Architecture

<div align="center">

```text
Telegram ─┐
Discord  ─┼─> Async worker ─> Filter & embed ─> PostgreSQL + pgvector
Reddit   ─┘                                      │
                                                   ├─> Hybrid RAG search
                                                   ├─> Weekly digest
                                                   └─> FastAPI web interface
```

</div>

| Component | Technology | Purpose |
|---|---|---|
| Collectors | Telethon, discord.py, asyncpraw | Authorized platform ingestion |
| Processing | Python, OpenAI API | Filtering, classification, chunking, embeddings |
| Storage | PostgreSQL 16, pgvector | Messages, metadata, full-text index, vectors |
| Application | FastAPI, vanilla HTML/CSS/JS | Private chat, sources, and digest archive |
| Operations | Docker Compose | Database, worker, and web services |

## 🚀 Quick start

Three commands on any Linux machine — a VPS, a cloud VM, a home server, or a laptop.

```bash
git clone https://github.com/PrimeBuild-pc/Gnosis.git
cd Gnosis
./install.sh
```

That is the whole install. `install.sh` installs Docker and the Compose plugin if they are missing (Debian/Ubuntu), asks for an admin password and a free chat provider, pulls the prebuilt image (amd64 and arm64), initialises the database, and starts the stack. Re-run it any time to reconfigure — it never overwrites values you do not touch.

### Requirements

- A Linux machine with `git`. Everything else the installer handles.
- One free chat API key — OpenRouter, Groq, or NVIDIA NIM all have a free tier. Embeddings run locally, so they need no key and cost nothing.
- Platform credentials only for the platforms you actually want. None are required to start.

### Then configure it from the dashboard

Open <http://127.0.0.1:8080> and sign in with the admin user you just chose.

- **Settings** opens on a configuration checklist: what is ready, what is still missing, which field to fill, and a link straight to the page that issues each credential. Chat keys apply immediately, with no restart.
- **Sources** is where you add the channels, chats, and subreddits to follow. Nothing is collected until you list it there.

The service binds to `127.0.0.1` and never opens a port to the internet. On a remote server, reach the dashboard through an SSH tunnel from your own computer:

```bash
ssh -L 8080:127.0.0.1:8080 user@your-server
```

Then open <http://127.0.0.1:8080> locally. No firewall rule, no domain, no certificate.

If you enable Telegram, one interactive login is needed after the install to create the session:

```bash
docker compose run --rm worker gnosis telegram-login
```

<details>
<summary>Manual install, step by step</summary>

```bash
git clone https://github.com/PrimeBuild-pc/Gnosis.git
cd Gnosis
cp .env.example .env
cp config/sources.example.toml config/sources.toml
docker compose pull   # or: docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d
```

`.env` and `config/sources.toml` are both excluded from Git. Everything in them can also be set from the dashboard afterwards.

</details>

## Configuration

| Variable | Required | Description |
|---|---:|---|
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `GNOSIS_EMBEDDING_PROVIDER` | No | `local` (default, free, runs in-container via fastembed) or `openai` |
| `GNOSIS_EMBEDDING_MODEL` / `GNOSIS_EMBEDDING_DIMENSIONS` | No | Local embedding model and vector size (default: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384) |
| `GNOSIS_CHAT_API_KEY` / `GNOSIS_CHAT_BASE_URL` | Yes | OpenAI-compatible chat provider (classification, RAG, digest). Point it at a free tier — OpenRouter, NVIDIA NIM, Groq — or OpenAI. Falls back to `OPENAI_API_KEY`/`OPENAI_BASE_URL` if unset |
| `OPENAI_CHAT_MODEL` | Yes | Chat model name (set it to match whichever provider is used for chat) |
| `OPENAI_API_KEY` | Only if `GNOSIS_EMBEDDING_PROVIDER=openai` or as chat fallback | OpenAI key, needed only when opting into OpenAI for embeddings or chat |
| `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` | No | Fallback role allowlist. Prefer per-workspace roles, set from the dashboard |
| `GNOSIS_DIGEST_DISCORD_WEBHOOK` | No | Fallback digest webhook, a single URL. Prefer the per-workspace one |
| `GNOSIS_BOTS` | No | Other Prime Build bots as `id=url`, comma separated, so the dashboard can link them |
| `GNOSIS_USERNAME` | Yes | Private web interface username |
| `GNOSIS_PASSWORD` | Yes | Private web interface password |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | If enabled | Telegram client credentials |
| `TELEGRAM_BOT_TOKEN` | No | BotFather token for the interactive `/ask` and `/digest` Telegram bot |
| `GNOSIS_TELEGRAM_ALLOWED_USERS` | If bot enabled | Comma-separated Telegram user IDs authorized to use the bot |
| `GNOSIS_DIGEST_TELEGRAM_CHAT_ID` | No | Telegram chat to auto-publish the weekly digest to |
| `DISCORD_BOT_TOKEN` | If enabled | Official Discord bot token (also powers the `/ask` and `/digest` slash commands) |
| `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` | No | Comma-separated Discord role IDs authorized to use the bot's slash commands |
| `GNOSIS_DIGEST_DISCORD_WEBHOOK` | No | Discord channel webhook URL to auto-publish the weekly digest to |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | If enabled | Reddit OAuth credentials |

See [`.env.example`](.env.example) for every available setting and [`config/sources.example.toml`](config/sources.example.toml) for the source allowlist format.

Embeddings default to a local multilingual model (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, via [fastembed](https://github.com/qdrant/fastembed)) — no API key, no cost, and it runs fine on a small ARM instance. Switching to OpenAI embeddings requires matching `GNOSIS_EMBEDDING_DIMENSIONS` to the chosen model and re-applying `migrations/002_local_embeddings.sql` (or a custom one) for the new vector size.

## Commands

```bash
gnosis db-init
gnosis telegram-login
gnosis worker
gnosis web
gnosis digest
gnosis prune --before 2025-01-01
gnosis selfcheck
```

`selfcheck` runs the real queries against the configured database — workspaces, sources, scoped and unscoped search, digests, stats — on temporary rows it cleans up afterwards, and exits non-zero if anything fails. The API tests use a fake database, so they cannot tell whether a query is actually valid for PostgreSQL; this closes that gap.

Connectors backfill the latest 200 accessible items, then continue through real-time events or polling. Repeated ingestion is safe and does not duplicate platform messages.

## 💬 Telegram bot

If `TELEGRAM_BOT_TOKEN` and `GNOSIS_TELEGRAM_ALLOWED_USERS` are set, the worker also runs a private Telegram bot (via BotFather) alongside the web UI:

- `/ask <question>` — source-grounded answer with `[Mn]` citations and links, same engine as the web chat.
- `/digest` — the latest saved weekly digest.

Only the whitelisted Telegram user IDs can use it; see [platform setup](docs/setup-platforms.md#bot-interattivo-ask-digest).

## 🎮 Discord bot

Unlike Telegram, ingestion and commands share the same Discord bot — as soon as `DISCORD_BOT_TOKEN` is set, `/ask` and `/digest` slash commands are registered alongside the existing collector:

- `/ask <domanda>` — same source-grounded answer engine as the web chat and the Telegram bot.
- `/digest` — the latest saved weekly digest.

Only members with a role listed in `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` can use them; without it the commands reply "not configured" but ingestion keeps working. The bot's invite URL needs the `applications.commands` OAuth scope, not just `bot`, or the slash commands won't appear — see [platform setup](docs/setup-platforms.md#bot-interattivo-ask-digest-1).

The weekly digest can also be pushed automatically (instead of only on-demand) to a Telegram chat and/or a Discord channel webhook — see `GNOSIS_DIGEST_TELEGRAM_CHAT_ID` / `GNOSIS_DIGEST_DISCORD_WEBHOOK` above.

## 🛠️ Admin dashboard

The dashboard is an application shell, not a page of tabs: **platforms down the left rail, the server picker across the top**. Whatever you open, you are looking at it through the server selected up there.

```
┌──────────────┬──────────────────────────────────────┐
│ 🧠 Gnosis    │  Context: [ Prime Build ▾ ]      🌐  │
│ 🚪 Doorman   ├──────────────────────────────────────┤
│ 🔐 D-View    │                                      │
│ ──────────── │   Discord                            │
│ ◎ Overview   │   ├ Credentials                      │
│ 💬 Chat      │   ├ Server settings · Prime Build    │
│ 📰 Digests   │   └ Channels read                    │
│ 🕸 Graph     │                                      │
│ ──────────── │                                      │
│ 🎮 Discord ● │                                      │
│ ✈ Telegram ○ │                                      │
│ 👽 Reddit  ○ │                                      │
└──────────────┴──────────────────────────────────────┘
```

- **Platforms** each get their own page: credentials, the settings that belong to the selected server (authorized roles, digest webhook), and the channels being read. The dot next to each one says whether it is configured and collecting.
- **Sources** are picked from a dropdown of channels the bot can actually see; the worker publishes that list, so 19-digit IDs never have to be copied by hand. Each page states plainly that these are the channels Gnosis *reads*, while `/ask` works in any channel where the bot is present.
- **Every field carries an `i` button** explaining what it does, where the value comes from, and what breaks without it.
- **Overview** opens on a setup checklist plus what has been collected so far, counted for the selected server.
- **Language**: English and Italian, guessed from the browser and switchable from the header. All strings live in `static/i18n.js`; the API returns data, never prose.
- **Bots**: the other Prime Build bots appear in the rail, greyed out until reachable. Set `GNOSIS_BOTS=doorman=http://host:3000,dview=http://host:3001` and they turn into links. The dashboard shows the install command rather than running it — installing from a browser would mean handing the container the Docker socket, which is full control of the host.

The frontend is dependency-free vanilla JS in four files: `i18n.js` (strings), `ui.js` (DOM helpers), `modules.js` (Gnosis pages), `shell.js` (rail, routing, server picker). Only `modules.js` knows anything about Gnosis, which is what makes the shell reusable.

## 🗂️ Workspaces

A workspace groups sources so a question can be answered from one server without dragging in the others. Without it, every answer and every digest mixes all configured sources together.

- Pick the context from the selector in the header. Chat, digests, sources and stats all follow it; **All sources** stays available as an explicit choice.
- Give a workspace the Discord server ID and `/ask` inside that server scopes itself automatically, using that workspace's authorized roles.
- Each workspace has its own weekly digest and its own webhook, so two servers never share a destination.
- In `config/sources.toml`, a source joins a workspace with `workspace = "Name"`. Sources without one stay reachable from the global context only.

## 🕸️ Knowledge graph

Every message that passes the relevance filter also goes through a lightweight entity/relationship extraction pass (one extra LLM call). Results land in three tables (`entities`, `entity_mentions`, `entity_relations`) queryable via `GET /api/entities` and `GET /api/entities/{id}`, and browsable from the dashboard's Grafo tab.

Known limitations, by design for this iteration:
- Entity deduplication matches on normalized name (`strip().casefold()`) + type — near-duplicates with different surface forms ("Claude" vs "Claude AI") stay separate nodes. An embedding-based resolution pass is the natural upgrade path if this becomes a problem in practice.
- The graph doesn't feed into RAG answers yet — it's deliberately kept separate from `/ask` so it can't affect the citation-integrity guarantees already in place there.

## 🔒 Platform access and privacy

- **Discord:** only an official bot authorized by the server administrators is supported. User tokens and self-bots are explicitly unsupported.
- **Telegram:** the client is limited to chats explicitly listed in `sources.toml` and accessible by the authenticated account.
- **Reddit:** access uses official OAuth APIs and must follow current rate limits and developer terms.
- **Web access:** the service binds to `127.0.0.1` by default. Use a private network or an HTTPS reverse proxy for remote access.
- **Secrets:** never commit `.env`, `sources.toml`, Telegram session files, or database backups.

Read the complete [platform setup guide](docs/setup-platforms.md) before enabling collectors.

## 🖥️ Running on a server, VPS, or cloud VM

The install is the same everywhere. What changes is only how you reach the dashboard and how you keep it running.

### Sizing

Gnosis runs on a small instance. It has been deployed and tested on an Oracle Cloud Always Free Ampere VM with **1 OCPU and 6 GB of RAM**, which is a quarter of what that free tier allows. Local embeddings are the heaviest part, and they fit comfortably.

The published image is multi-arch, so `x86_64` and `arm64` (Ampere, Graviton, Raspberry Pi 5) all pull the same tag with no rebuild.

### Reaching the dashboard

Pick one. The first needs no configuration at all and is the recommended default.

**SSH tunnel** — nothing is exposed, nothing to configure:

```bash
ssh -L 8080:127.0.0.1:8080 user@your-server
```

**Private network** — [Tailscale](https://tailscale.com) or WireGuard if you want it reachable from a phone without opening ports.

**Public domain with HTTPS** — only if you actually need it. Point a domain at the server, open 443, and put a TLS reverse proxy in front:

```nginx
server {
    listen 443 ssl;
    server_name gnosis.your-domain.com;
    location / { proxy_pass http://127.0.0.1:8080; }
}
```

Never publish port 8080 directly: HTTP Basic authentication over plain HTTP sends the password in the clear.

### Surviving reboots

Every service declares `restart: unless-stopped`, so the stack comes back on its own. Make sure the Docker daemon itself starts at boot:

```bash
sudo systemctl enable docker
```

## Development

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

The CI workflow runs linting, tests, and a Docker image build on every push and pull request.

## Documentation

- [Product brief](docs/product-brief.md)
- [Dashboard shell](docs/dashboard-shell.md) — how the shell is built and what to share with the other bots
- [Platform setup](docs/setup-platforms.md)
- [Operations, backup, and retention](docs/operations.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)

---

## 📄 License

MIT © PrimeBuild — see [LICENSE](LICENSE) for details.

<sub>Built for private, evidence-backed community research.</sub>
