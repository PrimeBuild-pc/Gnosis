#!/usr/bin/env bash
# Installer guidato per Gnosis: configura .env/config/sources.toml e avvia lo stack.
set -euo pipefail
cd "$(dirname "$0")"

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { printf "${BLUE}==>${NC} %s\n" "$1"; }
ok()   { printf "${GREEN}OK${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}!${NC} %s\n" "$1"; }

# Aggiorna (o aggiunge) una riga KEY=value in .env senza problemi di escaping sed.
set_env() {
  local key="$1" value="$2"
  awk -v k="$key" -v v="$value" -F'=' '
    BEGIN { done = 0 }
    $1 == k { print k "=" v; done = 1; next }
    { print }
    END { if (!done) print k "=" v }
  ' .env > .env.tmp && mv .env.tmp .env
}

SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"
DC="docker compose"

install_docker() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Docker non trovato e distribuzione non basata su apt. Installalo a mano e rilancia:" >&2
    echo "  https://docs.docker.com/engine/install/" >&2
    exit 1
  fi
  info "Docker non trovato, lo installo (serve sudo)"
  # DPkg::Lock::Timeout: su una VM appena creata unattended-upgrades tiene il lock di apt per
  # qualche minuto, senza attesa l'installer fallirebbe proprio al primo avvio.
  $SUDO apt-get -o DPkg::Lock::Timeout=600 update -qq
  $SUDO DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 install -y -qq     docker.io docker-compose-v2
  # set -e: entrambi possono fallire legittimamente (host senza systemd, oppure gia' root),
  # e nessuno dei due deve interrompere l'installazione.
  $SUDO systemctl enable --now docker >/dev/null 2>&1 ||
    warn "Servizio docker non avviato da systemd: avvialo a mano se non parte."
  if [ -n "$SUDO" ]; then
    $SUDO usermod -aG docker "$USER"
  fi
  ok "Docker installato"
}

command -v docker >/dev/null 2>&1 || install_docker
if ! docker compose version >/dev/null 2>&1; then
  echo "Plugin Docker Compose non trovato ('docker compose'). Installa docker-compose-v2." >&2
  exit 1
fi
# Subito dopo usermod il gruppo docker non è ancora attivo in questa shell: si applica al
# prossimo login, quindi per adesso si passa da sudo.
if ! docker info >/dev/null 2>&1; then
  DC="$SUDO docker compose"
  warn "Gruppo docker non ancora attivo in questa sessione: usa 'sudo docker compose' finché non rifai il login."
fi

[ -f .env ] || cp .env.example .env
[ -f config/sources.toml ] || cp config/sources.example.toml config/sources.toml
# Il container web scrive .env/config/sources.toml da dashboard con un utente non privilegiato
# (uid diverso da quello dell'host): permessi aperti in scrittura, coerente con un host dedicato
# a uso personale (Oracle Free Tier o simile), non un server condiviso multi-utente.
chmod 666 .env
chmod -R a+rwX config

info "Accesso web privato"
read -rp "Username admin [admin]: " WEB_USER
WEB_USER=${WEB_USER:-admin}
read -rsp "Password admin (vuoto = generata automaticamente): " WEB_PASS
echo
if [ -z "$WEB_PASS" ]; then
  WEB_PASS=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)
  warn "Password generata: $WEB_PASS (salvala ora, non verrà mostrata di nuovo)"
fi
set_env GNOSIS_USERNAME "$WEB_USER"
set_env GNOSIS_PASSWORD "$WEB_PASS"

info "Provider chat (gli embedding sono locali e gratuiti; serve comunque un modello per generare le risposte)"
echo "  1) OpenRouter    - https://openrouter.ai/keys       (free tier, modelli con suffisso :free)"
echo "  2) Groq          - https://console.groq.com/keys    (free tier)"
echo "  3) NVIDIA NIM    - https://build.nvidia.com          (free tier)"
echo "  4) OpenAI        - a pagamento"
echo "  5) Salta, lo configuro a mano dopo in .env"
read -rp "Scelta [1-5]: " CHAT_CHOICE
case "${CHAT_CHOICE:-5}" in
  1) BASE_URL="https://openrouter.ai/api/v1"; DEFAULT_MODEL="meta-llama/llama-3.3-70b-instruct:free" ;;
  2) BASE_URL="https://api.groq.com/openai/v1"; DEFAULT_MODEL="llama-3.3-70b-versatile" ;;
  3) BASE_URL="https://integrate.api.nvidia.com/v1"; DEFAULT_MODEL="meta/llama-3.1-70b-instruct" ;;
  4) BASE_URL=""; DEFAULT_MODEL="gpt-4o-mini" ;;
  *) BASE_URL=""; DEFAULT_MODEL="" ;;
esac
if [ "${CHAT_CHOICE:-5}" != "5" ]; then
  read -rp "Modello [$DEFAULT_MODEL]: " CHAT_MODEL
  CHAT_MODEL=${CHAT_MODEL:-$DEFAULT_MODEL}
  read -rsp "Chiave API: " CHAT_KEY
  echo
  set_env GNOSIS_CHAT_API_KEY "$CHAT_KEY"
  set_env GNOSIS_CHAT_BASE_URL "$BASE_URL"
  set_env OPENAI_CHAT_MODEL "$CHAT_MODEL"
else
  warn "Provider chat non configurato: imposta GNOSIS_CHAT_API_KEY in .env prima di avviare il worker."
fi

info "Sorgenti dati (facoltative, si possono aggiungere anche dopo - vedi docs/setup-platforms.md)"
read -rp "Abilitare Telegram? [y/N]: " ENABLE_TG
if [[ "${ENABLE_TG:-}" =~ ^[Yy]$ ]]; then
  read -rp "TELEGRAM_API_ID: " TG_ID
  read -rp "TELEGRAM_API_HASH: " TG_HASH
  set_env TELEGRAM_API_ID "$TG_ID"
  set_env TELEGRAM_API_HASH "$TG_HASH"
  warn "Dopo l'avvio esegui: $DC run --rm worker gnosis telegram-login"
fi
read -rp "Abilitare Discord? [y/N]: " ENABLE_DC
if [[ "${ENABLE_DC:-}" =~ ^[Yy]$ ]]; then
  read -rp "DISCORD_BOT_TOKEN: " DC_TOKEN
  set_env DISCORD_BOT_TOKEN "$DC_TOKEN"
fi
read -rp "Abilitare Reddit? [y/N]: " ENABLE_RD
if [[ "${ENABLE_RD:-}" =~ ^[Yy]$ ]]; then
  read -rp "REDDIT_CLIENT_ID: " RD_ID
  read -rp "REDDIT_CLIENT_SECRET: " RD_SECRET
  set_env REDDIT_CLIENT_ID "$RD_ID"
  set_env REDDIT_CLIENT_SECRET "$RD_SECRET"
fi
warn "Aggiungi le fonti abilitate (chat/canali/subreddit) in config/sources.toml prima di avviare."

info "Avvio Gnosis"
if $DC pull >/dev/null 2>&1; then
  ok "Immagine pre-costruita scaricata"
else
  info "Immagine pre-costruita non disponibile, compilo da sorgente (qualche minuto)..."
  $DC build
fi
$DC run --rm web gnosis db-init
$DC up -d

PORT=$(awk -F= '$1=="GNOSIS_PORT"{print $2}' .env)
HOST=$(awk -F= '$1=="GNOSIS_HOST"{print $2}' .env)
PORT=${PORT:-8080}
echo
ok "Gnosis è avviato. Username: $WEB_USER"
echo
echo "Apri la dashboard su http://${HOST:-127.0.0.1}:${PORT}"
echo "Su una macchina remota (VPS, VM, server) la porta resta chiusa verso Internet di"
echo "proposito: raggiungila con un tunnel SSH dal tuo computer, senza aprire nulla."
echo
echo "  ssh -L ${PORT}:127.0.0.1:${PORT} $(id -un)@<ip-del-server>"
echo
echo "Il resto (chiavi delle piattaforme, canali da seguire, conservazione dati) si configura"
echo "dalla dashboard: tab Impostazioni per le credenziali, tab Sorgenti per i canali."
