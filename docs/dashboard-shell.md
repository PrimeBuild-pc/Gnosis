# Architettura della dashboard

Gnosis serve una dashboard FastAPI con HTML/CSS/JavaScript vanilla, senza framework
frontend o build dedicata. `src/gnosis/static/index.html` carica i quattro script in
ordine; `tests/frontend.cjs` verifica anche che non vengano distribuiti bundle obsoleti.

| File in `src/gnosis/static/` | Responsabilità |
|---|---|
| `index.html` | Struttura iniziale, landmark, caricamento CSS e script |
| `i18n.js` | Stringhe e selezione lingua italiano/inglese |
| `ui.js` | Helper DOM, campi, messaggi e validazione dei link |
| `modules.js` | Pagine chat, digest, piattaforme, stato e impostazioni |
| `shell.js` | Sidebar, routing per hash, workspace e collegamenti agli altri bot |
| `style.css` | Token di colore, layout, componenti e stati accessibili |

Il registro `GNOSIS_MODULES` definisce le pagine e i gruppi `bot`, `platforms`,
`system`. Il DOM viene costruito con `createElement` e `textContent`: contenuti delle
piattaforme e output del modello sono dati non fidati, non HTML da eseguire.

## Contratto backend

- `GET /api/bots`: applicazione corrente e bot configurati con `GNOSIS_BOTS`.
  Il backend verifica la raggiungibilità; il browser apre il collegamento indicato.
- `GET /api/workspaces`: workspace per il selettore di contesto.
- `GET /api/setup`: stato della configurazione, con testi di aiuto gestiti da `i18n.js`.

API, dashboard e asset richiedono l'autenticazione admin; `/health` è pubblico.
L'amministratore è un operatore fidato globale: il selettore workspace è un filtro,
non una separazione di privilegi. Anche il grafo resta globale.

## Collegamenti a Doorman e D-View

Le due applicazioni sono Next.js con login Discord OAuth, non moduli di Gnosis.
`GNOSIS_BOTS` permette di collegare installazioni già esistenti; non condivide sessioni,
credenziali o permessi. Passare a un altro bot apre una nuova scheda.

La dashboard mostra istruzioni per installare un bot assente, ma non esegue comandi
sull'host e non monta il socket Docker. L'installazione e le operazioni autorizzate
restano descritte nel [README](../README.md) e nella [guida operativa](operations.md).
