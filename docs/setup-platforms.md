# Configurazione delle piattaforme

## Telegram

1. Creare `api_id` e `api_hash` su <https://my.telegram.org>.
2. Inserirli in `.env`.
3. Inserire in `config/sources.toml` gli ID numerici delle chat autorizzate.
4. Eseguire `docker compose run --rm worker gnosis telegram-login` e completare il login.

La sessione è salvata nel volume `telegram-data`. Non copiarla né versionarla: equivale a una credenziale di accesso.

### Bot interattivo (`/ask`, `/digest`)

Facoltativo, oltre al collector: permette di interrogare Gnosis direttamente da Telegram invece che dalla web UI.

1. Creare un bot con [@BotFather](https://t.me/BotFather) (`/newbot`) e copiare il token in `TELEGRAM_BOT_TOKEN`.
2. Recuperare il proprio ID utente numerico da un bot come [@userinfobot](https://t.me/userinfobot) e inserirlo in `GNOSIS_TELEGRAM_ALLOWED_USERS` (uno o più ID separati da virgola).
3. Il bot resta comunque un'app registrata con `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` (stessi valori del collector), ma usa una sessione separata: nessun conflitto con il login dell'account personale.
4. `GNOSIS_TELEGRAM_ALLOWED_USERS` è obbligatorio se `TELEGRAM_BOT_TOKEN` è impostato: senza whitelist il worker si rifiuta di avviare il bot.

Comandi disponibili: `/ask <domanda>` risponde con citazioni `[Mn]` e link alle fonti; `/digest` restituisce l'ultimo digest salvato.

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
