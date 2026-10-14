# Setup delle piattaforme

Per installazione, permessi file, rete, costi e procedura Discord completa leggi il
[README](../README.md#discord-configurazione-passo-per-passo-anche-su-più-server).
Credenziali e sessioni vanno inserite dall'operatore, mai nei transcript di un agente.
La raccolta richiede consenso e una allowlist esplicita; scoprire un canale non autorizza a leggerlo.

## Discord

Usa soltanto un bot ufficiale. Developer Portal → Bot → **Message Content Intent**.
Invita con scope `bot` e `applications.commands`; concedi View Channel, Read Message History
e Send Messages nei canali necessari, non Administrator. Per ogni server crea un workspace
con ID server e ruoli; senza mapping o con ruoli vuoti `/ask` e `/digest` negano accesso.
`GNOSIS_DISCORD_ALLOWED_ROLE_IDS` è deprecato, non è un fallback di autorizzazione.

Le fonti devono essere canali testuali assegnati al workspace giusto in `sources.toml` o dashboard:

```toml
[[discord]]
channel_id = "YOUR_CHANNEL_ID"
name = "homelab"
workspace = "Server A"
topics = ["Linux", "backup"]
```

Il nome workspace deve coincidere con quello dell'ID server configurato. Per più server,
ripeti con nomi e ID distinti. Il bot risponde in privato e limita `/ask` ai canali leggibili
dal membro nel server corrente; thread/forum non fanno parte di questo percorso.

### Digest automatici

Crea il webhook da Impostazioni canale → Integrazioni e salvalo nel **workspace**, non in una
lista di URL globali. Scegli un canale il cui pubblico sia autorizzato a tutte le fonti del
workspace. Il digest automatico non applica filtri per destinatario e i ruoli dei comandi
non controllano chi legge il canale webhook. Senza webhook non pubblica. Se ci sono workspace,
non viene pubblicato un digest globale misto. La dashboard maschera i webhook; campo vuoto
conserva il valore, API `digest_webhook: ""` lo revoca.

## Telegram

1. Ottieni `api_id` e `api_hash` su <https://my.telegram.org>.
2. Imposta `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` in `.env` o dashboard.
3. Ricrea web/worker per ricaricare le credenziali: `docker compose up -d --force-recreate web worker`.
4. Ferma il worker e crea la sessione una sola volta:

   ```bash
   docker compose stop worker
   docker compose run --rm worker gnosis telegram-login
   docker compose up -d worker
   ```

5. Scegli soltanto chat accessibili e autorizzate nella pagina Telegram, poi riavvia il worker.

Sessione in `telegram-data`: proteggerla come una password; la raccolta usa il tuo account,
non aggira la visibilità dei gruppi. Non leggere o copiare la sessione con un agente senza
consenso specifico. Il codice può richiedere telefono, codice login e 2FA: li inserisce l'utente.

### Bot interattivo (`/ask`, `/digest`)

È uno strumento dell'**operatore globale**, non dei membri dei vari server Discord.

1. Crea un bot tramite [@BotFather](https://t.me/BotFather), salva `TELEGRAM_BOT_TOKEN`.
2. Configura `GNOSIS_TELEGRAM_ALLOWED_USERS` con ID numerici di operatori che possono vedere
   tutte le fonti. Senza allowlist il bot non parte.
3. Sono richiesti gli stessi `TELEGRAM_API_ID` e `TELEGRAM_API_HASH`. La sessione bot è separata
   da quella personale. Ricrea worker dopo aver salvato i valori.
4. Usa i comandi in conversazione privata. I gruppi sono ignorati anche per utenti autorizzati.

`GNOSIS_DIGEST_TELEGRAM_CHAT_ID` è una destinazione globale soltanto in installazioni senza
workspace. Configurare push significa inviare contenuti alla chat: approva esplicitamente
la destinazione e il suo pubblico. Non usare un gruppo ampio come destinazione admin.

## Reddit

Crea un'app OAuth approvata per l'uso che intendi fare. Imposta `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET` e `REDDIT_USER_AGENT`, configura subreddit autorizzati, ricrea worker.
Accesso, quote, prezzi e termini possono cambiare: verifica i requisiti attuali su Reddit;
nessuna promessa di accesso gratuito o bypass delle limitazioni.

## Applicare modifiche

- Credenziali in `.env`: `docker compose up -d --force-recreate web worker` (non solo restart).
- Canali/chat/subreddit nell'allowlist: `docker compose restart worker`.
- Mapping e ruoli workspace: dal DB al comando successivo, senza restart.

Vedi [operazioni](operations.md) per status, backup e gestione cancellazioni.
