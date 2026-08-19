# Configurazione delle piattaforme

Il percorso rapido è in due passi, e non richiede di modificare file a mano:

1. `./install.sh` alla radice del repo installa Docker se manca, chiede password admin e provider chat, e avvia lo stack.
2. Il resto si fa dalla dashboard: **Impostazioni** mostra una checklist di cosa manca, le credenziali divise per sezione e un pulsante `i` accanto a ogni campo che spiega a cosa serve. **Sorgenti** è dove si scelgono canali e chat, da una tendina di quelli che il bot vede davvero.

Questa pagina resta il riferimento dettagliato: cosa significa ogni credenziale, quali permessi servono sulla piattaforma e quali sono i limiti di ciascun connettore.

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

## Workspace: tenere separati piu' server

Un workspace raggruppa le sorgenti di uno stesso server. Serve perche' senza, una domanda pesca da tutte le fonti configurate e la risposta mescola server diversi.

1. In **Impostazioni → Workspace**, crea un workspace e assegnagli l'ID del server Discord (tasto destro sul nome del server → Copia ID server, con la modalita' sviluppatore attiva).
2. Nel tab **Sorgenti**, scegliendo un canale dalla tendina il workspace viene compilato da solo con il nome del server.
3. Da quel momento `/ask` dentro quel server risponde usando solo i suoi canali, e applica i ruoli autorizzati di quel workspace.

Ruoli autorizzati e webhook del digest sono impostazioni **del workspace**, non globali: due server hanno ruoli diversi e destinazioni diverse. Le variabili `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` e `GNOSIS_DIGEST_DISCORD_WEBHOOK` restano come ripiego per chi non usa i workspace, e accettano un solo webhook.

## Discord

1. Creare un'applicazione e un bot nel Discord Developer Portal.
2. Abilitare il privileged intent **Message Content**.
3. Nell'URL di invito, includere sia lo scope `bot` sia lo scope **`applications.commands`** (necessario perché i comandi slash `/ask` e `/digest` compaiano — senza questo scope il bot legge i messaggi ma non offre comandi).
4. Invitare il bot esclusivamente nei server che lo autorizzano, con permessi di lettura e cronologia sui canali scelti.
5. Inserire il token dalla dashboard (**Impostazioni → Discord**) e scegliere i canali dal tab **Sorgenti**: la tendina si popola da sola appena il worker riparte con il token impostato.

Gnosis non accetta token utente e non implementa self-bot.

### Bot interattivo (`/ask`, `/digest`)

A differenza di Telegram, su Discord non serve un bot separato: lo stesso bot usato per la raccolta risponde anche ai comandi, appena `DISCORD_BOT_TOKEN` è impostato.

1. Attivare la modalità sviluppatore in Discord (Impostazioni utente → Avanzate) per poter copiare gli ID.
2. Tasto destro sul ruolo da autorizzare (nel server, in Impostazioni ruoli) → **Copia ID**.
3. Inserire uno o più ID in `GNOSIS_DISCORD_ALLOWED_ROLE_IDS`, separati da virgola.

Senza `GNOSIS_DISCORD_ALLOWED_ROLE_IDS` i comandi restano visibili ma rispondono "non configurato": la raccolta messaggi continua a funzionare comunque, non viene bloccata. I comandi possono impiegare fino a un'ora per comparire su Discord la prima volta (propagazione della sincronizzazione globale); dopo il primo avvio è immediata.

Comandi disponibili: `/ask <domanda>` risponde con citazioni `[Mn]` e link alle fonti; `/digest` restituisce l'ultimo digest salvato.

### Digest pubblicato automaticamente

Facoltativo: oltre a poterlo chiedere on-demand, il digest settimanale generato dal worker può essere pubblicato da solo.

- **Telegram**: imposta `GNOSIS_DIGEST_TELEGRAM_CHAT_ID` con l'ID della chat/canale di destinazione (usa `TELEGRAM_BOT_TOKEN`, nessuna configurazione aggiuntiva).
- **Discord**: crea un webhook nel canale di destinazione (Impostazioni canale → Integrazioni → Webhook → Nuovo webhook, copia l'URL) e incollalo in `GNOSIS_DIGEST_DISCORD_WEBHOOK`.

Le due destinazioni sono indipendenti fra loro e da `GNOSIS_DISCORD_ALLOWED_ROLE_IDS`/`GNOSIS_TELEGRAM_ALLOWED_USERS`.

## Reddit

1. Creare un'applicazione API personale Reddit.
2. Inserire client ID, secret e uno user-agent identificabile in `.env`.
3. Configurare soltanto subreddit esplicitamente selezionati.

L'installazione deve rispettare rate limit, Developer Terms e obblighi di cancellazione applicabili. Prima di un uso non personale verificare nuovamente i termini correnti delle piattaforme.
