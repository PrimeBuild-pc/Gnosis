# Operazioni

Prerequisiti e permessi: [README](../README.md). Tutti i comandi vanno eseguiti nella directory
Gnosis. API e CLI sono strumenti dell'operatore globale, non di tenant isolati.

## Stato e reload

```bash
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail=100 worker web
```

`/health` conferma solo che il web risponde. Controlla la pagina Stato per i connettori.
I log possono contenere dettagli privati/errori dei provider: sanitizzali prima di condividerli.

- Credenziali/endpoint/modello cambiati: `docker compose up -d --force-recreate web worker`.
  `restart` non ricarica l'env_file Docker. Le chiavi chat salvate dalla dashboard si applicano
  subito al solo processo web; il worker va comunque ricreato.
- Allowlist sorgenti cambiata: `docker compose restart worker`. La ricerca esclude subito una
  sorgente disabilitata, ma il collector mantiene la configurazione fino al restart.
- Ruoli e mapping workspace: applicati dal DB al comando successivo, senza restart.

## Selfcheck (scrive fixture temporanee)

```bash
docker compose run --rm web gnosis selfcheck
```

Solo su un database autorizzato: applica migration e crea fixture univoche, verifica query e
isolamento Discord, poi rimuove le proprie fixture. Non disabilita le sorgenti esistenti.
Non è un check read-only; un kill improvviso può lasciare fixture `__selfcheck__` da rimuovere
manualmente dopo verifica. Non utilizzare per autorizzare automaticamente un deploy.

## Backup

Conserva database, `.env`, configurazione e sessioni Telegram insieme. Le sessioni equivalgono
a credenziali e il dump include messaggi, ruoli e webhook. Usa cifratura e una copia fuori host.
Su Linux:

```bash
umask 077
mkdir -p backups
chmod 700 backups
docker compose stop worker web
docker compose exec -T db pg_dump -U gnosis -Fc gnosis > backups/gnosis.dump
cp .env backups/env.backup
cp config/sources.toml backups/sources.toml
docker compose run --rm --no-deps --entrypoint tar worker -C /data -cf - telegram > backups/telegram.tar
docker compose up -d
```

Se un comando fallisce, verifica il backup prima di considerarlo valido; riavvia i servizi
quando sicuro. Il DB continua a funzionare, ma non ci sono writer applicativi durante la copia.
Cifra il backup con il tuo strumento abituale; non versionare `backups/` né caricarlo su issue.

### Restore (distruttivo: autorizzazione e backup obbligatori)

Ripristina solo backup fidati, compatibili con la versione del codice. Avvia solo `db`, mantieni
web/worker fermi. Su una nuova installazione prepara prima `.env`, config e permessi secondo README.

```bash
docker compose stop worker web
docker compose up -d db
docker compose exec -T db pg_restore -U gnosis -d gnosis --clean --if-exists --exit-on-error < backups/gnosis.dump
cp backups/env.backup .env
cp backups/sources.toml config/sources.toml
docker compose run --rm --no-deps --entrypoint tar worker -C /data -xf - < backups/telegram.tar
sudo chgrp 10001 .env config config/sources.toml
chmod 660 .env config/sources.toml
chmod 2770 config
docker compose up -d --force-recreate
```

La password PostgreSQL nel volume di destinazione deve corrispondere a quella ripristinata
in `.env`; ripristinare il file non cambia l'utente PostgreSQL. Non proseguire se il restore
fallisce. Verifica accesso, Stato e un campione di fonti prima di riattivare i webhook.

## Retention e cancellazione

Impostazioni → Conservazione dati: giorni massimi dei messaggi (default: nessuna scadenza).
Il worker elimina messaggi e chunk ogni ora. CLI una tantum:

```bash
docker compose run --rm worker gnosis prune --before 2025-01-01
```

`prune`/retention non eliminano i digest già salvati. Anche una cancellazione ricevuta dalla
piattaforma non riscrive i digest storici: possono conservare informazioni derivate. `/digest`
Discord verifica ancora le citazioni; l'admin resta autorizzato all'archivio globale.
La funzione **wipe** cancella tutta la memoria raccolta, non è limitata al workspace selezionato.
Il worker può raccogliere nuovamente messaggi al prossimo backfill: per un'erasure duratura,
ferma/disabilita le sorgenti e gestisci anche backup/digest. Reddit non garantisce eventi di
cancellazione retroattiva; applica i termini correnti e gestisci richieste di rimozione.

## Aggiornamento / rollback

Dopo backup e verifica che il checkout non contenga modifiche locali da preservare:

```bash
docker compose stop worker web
git pull --ff-only
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d --force-recreate
```

Verifica `/health`, Stato e configurazione workspace. I volumi restano: **mai `down -v`** per
aggiornare. Il rollback di codice può richiedere anche un restore del DB compatibile: le
migration non hanno downgrade automatico. Non ruotare solo POSTGRES_PASSWORD su un volume
esistente; vedi README per la procedura PostgreSQL.
