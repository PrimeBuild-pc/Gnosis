# Configurazione delle piattaforme

## Telegram

1. Creare `api_id` e `api_hash` su <https://my.telegram.org>.
2. Inserirli in `.env`.
3. Inserire in `config/sources.toml` gli ID numerici delle chat autorizzate.
4. Eseguire `docker compose run --rm worker gnosis telegram-login` e completare il login.

La sessione è salvata nel volume `telegram-data`. Non copiarla né versionarla: equivale a una credenziale di accesso.

## Discord

1. Creare un'applicazione e un bot nel Discord Developer Portal.
2. Abilitare il privileged intent **Message Content**.
3. Invitare il bot esclusivamente nei server che lo autorizzano, con permessi di lettura e cronologia sui canali scelti.
4. Inserire token e channel ID in `.env` e `config/sources.toml`.

Gnosis non accetta token utente e non implementa self-bot.

## Reddit

1. Creare un'applicazione API personale Reddit.
2. Inserire client ID, secret e uno user-agent identificabile in `.env`.
3. Configurare soltanto subreddit esplicitamente selezionati.

L'installazione deve rispettare rate limit, Developer Terms e obblighi di cancellazione applicabili. Prima di un uso non personale verificare nuovamente i termini correnti delle piattaforme.
