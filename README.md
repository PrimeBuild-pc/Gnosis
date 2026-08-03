<h1 align="center">🧠 Gnosis</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
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

### Requirements

- Docker with Compose
- An OpenAI API key
- Credentials for each enabled platform
- At least one authorized source

### 1. Clone and configure

```bash
git clone https://github.com/PrimeBuild-pc/Gnosis.git
cd Gnosis
cp .env.example .env
cp config/sources.example.toml config/sources.toml
```

Edit `.env` and `config/sources.toml` with your credentials and allowlisted source IDs. Both files are excluded from Git.

### 2. Build and initialize the database

```bash
docker compose build
docker compose run --rm web gnosis db-init
```

### 3. Create the Telegram session

Skip this step if Telegram is not enabled.

```bash
docker compose run --rm worker gnosis telegram-login
```

The generated session is stored in a private Docker volume and must be treated as a credential.

### 4. Start Gnosis

```bash
docker compose up -d
```

Open <http://127.0.0.1:8080> and sign in with `GNOSIS_USERNAME` and `GNOSIS_PASSWORD`.

## Configuration

| Variable | Required | Description |
|---|---:|---|
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `OPENAI_API_KEY` | Yes | API key used for classification, embeddings, and answers |
| `OPENAI_CHAT_MODEL` | Yes | Chat model name |
| `OPENAI_EMBEDDING_MODEL` | Yes | Embedding model; output must contain 1,536 dimensions |
| `GNOSIS_USERNAME` | Yes | Private web interface username |
| `GNOSIS_PASSWORD` | Yes | Private web interface password |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | If enabled | Telegram client credentials |
| `DISCORD_BOT_TOKEN` | If enabled | Official Discord bot token |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | If enabled | Reddit OAuth credentials |

See [`.env.example`](.env.example) for every available setting and [`config/sources.example.toml`](config/sources.example.toml) for the source allowlist format.

The default embedding model is `text-embedding-3-small`, which matches the database schema's 1,536 dimensions.

## Commands

```bash
gnosis db-init
gnosis telegram-login
gnosis worker
gnosis web
gnosis digest
gnosis prune --before 2025-01-01
```

Connectors backfill the latest 200 accessible items, then continue through real-time events or polling. Repeated ingestion is safe and does not duplicate platform messages.

## 🔒 Platform access and privacy

- **Discord:** only an official bot authorized by the server administrators is supported. User tokens and self-bots are explicitly unsupported.
- **Telegram:** the client is limited to chats explicitly listed in `sources.toml` and accessible by the authenticated account.
- **Reddit:** access uses official OAuth APIs and must follow current rate limits and developer terms.
- **Web access:** the service binds to `127.0.0.1` by default. Use a private network or an HTTPS reverse proxy for remote access.
- **Secrets:** never commit `.env`, `sources.toml`, Telegram session files, or database backups.

Read the complete [platform setup guide](docs/setup-platforms.md) before enabling collectors.

## 🖥️ Running on Oracle Cloud (Always Free)

Gnosis fits comfortably on an ARM Ampere instance (4 OCPU, 24 GB RAM — always free).

### Prerequisites

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER  # log out and back in
```

### Deploy

```bash
git clone https://github.com/PrimeBuild-pc/Gnosis.git
cd Gnosis

# Create config files (edit with your values)
cp .env.example .env
cp config/sources.example.toml config/sources.toml

# Build and start
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d
```

### Security

Bind to localhost and use nginx as a TLS reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name gnosis.your-domain.com;
    location / { proxy_pass http://127.0.0.1:8080; }
}
```

### Auto-start on boot

```bash
# Docker Compose auto-restarts with restart: unless-stopped
# Ensure Docker daemon starts on boot
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
- [Platform setup](docs/setup-platforms.md)
- [Operations, backup, and retention](docs/operations.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)

---

## 📄 License

MIT © PrimeBuild — see [LICENSE](LICENSE) for details.

<sub>Built for private, evidence-backed community research.</sub>
