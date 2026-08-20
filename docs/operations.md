# Operazioni

## Stato

```bash
docker compose ps
docker compose logs -f worker
docker compose logs -f web
curl http://127.0.0.1:8080/health
```

## Controllo di salute

```bash
docker compose run --rm web gnosis selfcheck
```

Esegue le query vere contro il database configurato — workspace, sorgenti, ricerca con e
senza contesto, digest, statistiche — creando dati temporanei con prefisso `__selfcheck__`
e rimuovendoli alla fine. Esce con codice diverso da zero se qualcosa fallisce.

Serve perche' i test dell'API usano un database finto: sono veloci ma non si accorgono se
una query non e' valida per Postgres. Un bug di questo tipo e' gia' arrivato in produzione
(un `coalesce` senza cast su una colonna `text[]`), e questo controllo lo intercetta.

## Backup

```bash
docker compose exec -T db pg_dump -U gnosis -Fc gnosis > gnosis.dump
```

Ripristino su database vuoto:

```bash
docker compose exec -T db pg_restore -U gnosis -d gnosis --clean --if-exists < gnosis.dump
```

I backup contengono messaggi personali: cifrarli e limitarne l'accesso.

## Retention

Due modi equivalenti:

- **Dashboard** (tab Impostazioni → Conservazione dati): imposta un numero di giorni oltre il quale i messaggi vengono eliminati automaticamente ogni ora dal worker (di default è vuoto, cioè per sempre). Lo stesso pannello ha un tasto per cancellare subito tutta la memoria raccolta (messaggi, chunk, digest), con conferma esplicita.
- **CLI**, per un'eliminazione una tantum:

```bash
docker compose run --rm worker gnosis prune --before 2025-01-01
```

Le cancellazioni ricevute in tempo reale da Telegram e Discord rimuovono messaggi e chunk associati. Reddit non garantisce notifiche di cancellazione retroattive: applicare una retention breve e gestire tempestivamente eventuali richieste di rimozione.

## Aggiornamento

```bash
git pull --ff-only
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d
```

## Accesso remoto

Il servizio è deliberatamente esposto solo su `127.0.0.1`. Per accesso remoto usare una rete privata o un reverse proxy HTTPS. Non esporre direttamente la porta 8080 su Internet.
