# Gnosis

Knowledge base personale che raccoglie contenuti autorizzati da Telegram, Discord e Reddit, crea digest settimanali e risponde con citazioni alle fonti originali.

## Requisiti

- Docker con Compose
- credenziali OpenAI
- almeno una sorgente autorizzata
- credenziali delle piattaforme utilizzate

## Avvio

```bash
cp .env.example .env
cp config/sources.example.toml config/sources.toml
# Compilare .env e config/sources.toml
docker compose build
docker compose run --rm web gnosis db-init
```

Per Telegram, creare una volta la sessione persistente:

```bash
docker compose run --rm worker gnosis telegram-login
```

Avviare poi i servizi:

```bash
docker compose up -d
```

L'interfaccia è disponibile su <http://127.0.0.1:8080>. Il browser richiederà `GNOSIS_USERNAME` e `GNOSIS_PASSWORD` alla prima chiamata API.

## Configurazione

Le credenziali vanno soltanto in `.env`, escluso da Git. L'allowlist è in `config/sources.toml`, anch'esso escluso da Git. Il formato completo è mostrato in `config/sources.example.toml`.

Il modello embedding deve produrre vettori da 1536 dimensioni; il valore predefinito `text-embedding-3-small` è compatibile.

## Comandi

```bash
gnosis db-init
gnosis telegram-login
gnosis worker
gnosis web
gnosis digest
gnosis prune --before 2025-01-01
```

I connettori eseguono un backfill iniziale degli ultimi 200 elementi accessibili e poi restano in ascolto o polling. Gli inserimenti sono idempotenti.

## Limiti di accesso

- **Discord:** soltanto bot ufficiale autorizzato nel server; i self-bot non sono supportati.
- **Telegram:** client associato al proprio account e limitato alle chat esplicitamente configurate.
- **Reddit:** OAuth e API ufficiale, rispettando limiti e termini applicabili.

Consultare [docs/setup-platforms.md](docs/setup-platforms.md) prima di configurare i connettori.

## Sviluppo

```bash
python -m venv .venv
. .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
pytest
```

## Operazioni e backup

Vedere [docs/operations.md](docs/operations.md).
