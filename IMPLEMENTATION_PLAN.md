# Implementation plan

- [x] Preparare repository e requisiti
- [x] Definire l'MVP e i criteri di accettazione
- [x] Creare la struttura minima del progetto
- [x] Impostare runtime e configurazione
- [x] Realizzare PostgreSQL e pgvector
- [x] Implementare i connettori ufficiali
- [x] Costruire la pipeline di ingestione
- [x] Implementare retrieval e risposte RAG
- [x] Generare il digest settimanale
- [x] Creare l'interfaccia web privata
- [x] Preparare CLI, worker e Docker
- [x] Aggiungere verifiche automatiche
- [x] Documentare installazione e gestione

## Accettazione MVP

- allowlist obbligatoria e credenziali escluse da Git;
- ingestion idempotente da Telegram, Discord e Reddit;
- ricerca ibrida full-text/vettoriale;
- risposte e digest rifiutati se privi di citazioni valide;
- interfaccia privata protetta da HTTP Basic;
- avvio riproducibile tramite Docker Compose;
- test e build eseguiti dalla CI.

La verifica live dei connettori richiede credenziali e community autorizzate del proprietario.
