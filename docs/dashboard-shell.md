# Il guscio della dashboard, e come condividerlo fra i tre bot

Questa nota descrive com'è fatta la dashboard di Gnosis e cosa conviene davvero condividere
con Doorman e D-View. È una nota di progetto, non una guida operativa.

## Com'è fatta

Quattro file in `src/gnosis/static/`, senza dipendenze e senza toolchain:

| File | Responsabilità | Specifico di Gnosis? |
|---|---|---|
| `shell.js` | barra laterale, routing per hash, selettore del server, cambio lingua, elenco bot | no |
| `ui.js` | helper DOM, campi con pulsante informativo, righe di elenco, stato del contesto | no |
| `style.css` | token di colore, griglia dell'applicazione, componenti | no |
| `i18n.js` | tutte le stringhe, inglese e italiano | sì, nei testi |
| `modules.js` | le pagine: chat, digest, piattaforme, stato, impostazioni | sì |

Il guscio non sa cosa sia Gnosis. Legge un registro di moduli:

```js
{id: 'discord', group: 'platforms', icon: '🎮', labelKey: 'section.discord',
 platform: 'discord', render: container => { /* disegna la pagina */ }}
```

e li dispone in tre gruppi (`bot`, `platforms`, `system`). Cambiare `modules.js` cambia
l'intera applicazione: è l'unico punto di contatto.

Il contratto che il backend deve rispettare è ristretto:

- `GET /api/bots` — i bot affiancati, con `installed` e `current`
- `GET /api/workspaces` — i server, per il selettore in alto
- `GET /api/setup` — cosa è pronto e cosa manca, **solo dati**: le spiegazioni stanno in `i18n.js`

## Cosa condividere davvero

Doorman e D-View **non** sono nella stessa situazione di Gnosis, e conviene dirlo prima di
copiare file:

- entrambi sono **Next.js**, non pagine statiche;
- entrambi hanno già il **login Discord OAuth** e pagine `/guilds/[guildId]/…`, cioè hanno
  già il modello "scegli il server, poi vedi le sue cose";
- Gnosis è FastAPI con HTTP Basic, e serve file statici.

Quindi la mossa sbagliata è portare `shell.js` dentro Next.js e riscrivere due interfacce
funzionanti. Si perderebbe l'autenticazione OAuth per guadagnare uniformità estetica.

**Da condividere: `style.css`.** È scritto apposta senza framework e senza `@import`: token
di colore, griglia, `.card`, `.list-row`, `.rail-item`, `.field`. Importarlo in
`apps/web/src/app/globals.css` fa sì che i tre bot sembrino lo stesso prodotto pur restando
tre applicazioni diverse. Le classi sono nomi normali, non moduli CSS, quindi funzionano
identiche in JSX.

**Da replicare, non copiare: la struttura.** Barra laterale a sinistra con i tre bot in
cima, selettore del server in alto, gruppi `bot` / `platforms` / `system`. In Next.js si
esprime con un `layout.tsx` invece che con `shell.js`, ma è la stessa gerarchia.

**Da condividere davvero come codice: `GET /api/bots`.** Sono venti righe per applicazione e
sono ciò che rende il gruppo un gruppo: ogni bot dichiara gli altri due, prova a
raggiungerli, e mostra grigio ciò che non risponde. Il probe va fatto lato server, non dal
browser: da JavaScript il CORS non lascia distinguere "spento" da "raggiungibile ma di
un'altra origine".

## Perché l'installazione non parte dal browser

La pagina di un bot non installato mostra il comando, non lo esegue. Eseguirlo vorrebbe dire
montare il socket Docker nel container della dashboard, cioè dare a un'applicazione esposta
via web il controllo completo della macchina. Per un progetto self-hosted che gira sulla VM
personale di qualcun altro non è uno scambio accettabile di default.

L'alternativa onesta è quella implementata: se il bot è già installato altrove, lo si dichiara
in `GNOSIS_BOTS` e smette di essere grigio.

## Limiti attuali, dichiarati

- Il selettore in alto elenca i **workspace di Gnosis**, non i server Discord in assoluto: un
  server esiste nell'elenco solo dopo che gli è stato assegnato almeno una sorgente o è stato
  creato a mano.
- Passare da un bot all'altro apre una scheda nuova. Un'unica sessione condivisa fra tre
  applicazioni con tre modelli di autenticazione diversi è un problema a sé.
- Il grafo delle entità resta globale, non filtrato per server.
