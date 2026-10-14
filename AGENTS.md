# Gnosis: procedure per coding agent

- Installazione o controllo homelab: leggi `README.md` (limiti, Discord, agenti). Backup,
  restore, retention, aggiornamenti o selfcheck: leggi `docs/operations.md` prima dei comandi.
- Scope: un operatore fidato globale, non SaaS multi-tenant. Il selettore web non è ACL.
  Nei comandi Discord mantieni workspace obbligatorio, guild verificabile, ruoli fail-closed,
  filtri prima del ranking, permessi canale e risposte ephemeral senza menzioni.
- Lavora solo nel checkout richiesto; controlla `git status` e preserva modifiche altrui.
  Test offline con fake DB/provider/Discord. Comandi di verifica sono nel README; selfcheck
  scrive fixture e migration, richiede un database esplicitamente autorizzato.
- Concorda host, server/workspace e azioni prima di installare, contattare piattaforme,
  scaricare modelli, pubblicare digest o modificare permessi. Wipe/prune/restore/volumi
  richiedono consenso specifico e un backup verificato. Non fare deploy o commit impliciti.
- L'utente inserisce segreti/login/2FA. Non leggere `.env` reali, sessioni o backup, né stampare
  credenziali/header/webhook. Usa `.env.example` e fixture temporanee per verifiche.
- Controllo dopo consenso: CLI `gnosis`/Docker Compose, API admin autenticata `/docs` o browser
  con sessione autorizzata. Nessun nuovo token globale, MCP o Docker socket nel container.
  API admin e bot Telegram hanno visibilità globale: solo agenti/operatori fidati.
- Mantieni I/O delle piattaforme asincrono in `collectors/`, configurazione immutabile in
  `config.py` e persistenza in `db.py` con migration SQL numerate in `migrations/`.
  Lo schema si aggiorna tramite CLI, non durante l'avvio web.
- Verifica callers e regression test per ogni cambio di scope/config. Riporta esiti e ciò
  che resta non verificato; abbonamenti coding agent non includono credito API del modello chat.
