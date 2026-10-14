#!/usr/bin/env bash
# Guided local install. Never downloads or executes a remote installer.
set -euo pipefail
umask 0077
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo 'Install Docker Engine and Compose >= 2.30 first (README).'; exit 1; }
docker compose version >/dev/null || { echo 'Docker Compose plugin missing.'; exit 1; }
docker info >/dev/null || { echo 'Docker daemon unavailable; check permissions (README).'; exit 1; }

# ENVIRON keeps backslashes and dollar signs literal, unlike awk -v.
set_env() {
  local temporary encoded="$2"
  encoded=${encoded//\\/\\\\}
  encoded=${encoded//\"/\\\"}
  encoded=${encoded//\$/\$\$}
  encoded=${encoded//$'\t'/\\t}
  temporary=$(mktemp .env.XXXXXX)
  GNOSIS_SET_KEY="$1" GNOSIS_SET_VALUE="\"$encoded\"" awk -F= '
    BEGIN { k = ENVIRON["GNOSIS_SET_KEY"]; v = ENVIRON["GNOSIS_SET_VALUE"]; done = 0 }
    $1 == k { if (!done) print k "=" v; done = 1; next }
    { print }
    END { if (!done) print k "=" v }
  ' .env > "$temporary"
  mv "$temporary" .env
}
# Only checks emptiness/defaults and reads the numeric port; never eval secret values.
get_env() {
  local value
  value=$(awk -v k="$1" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }' .env)
  if [[ "$value" == \"*\" ]]; then value=${value:1:${#value}-2}; fi
  printf '%s' "$value"
}

if [ ! -f .env ]; then
  cp .env.example .env
  DB_PASS=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
  set_env POSTGRES_PASSWORD "$DB_PASS"
  set_env DATABASE_URL "postgresql://gnosis:${DB_PASS}@db:5432/gnosis"
fi
if [ -z "$(get_env POSTGRES_PASSWORD)" ]; then
  echo 'Existing .env: set POSTGRES_PASSWORD to the CURRENT database password first.' >&2
  echo 'Do not rotate only .env; see README, Existing installations.' >&2
  exit 1
fi
[ -f config/sources.toml ] || printf '# Add authorized sources in the dashboard.\n' > config/sources.toml

read -rp 'Admin username [keep current / admin]: ' WEB_USER
if [ -n "$WEB_USER" ]; then
  set_env GNOSIS_USERNAME "$WEB_USER"
elif [ -z "$(get_env GNOSIS_USERNAME)" ]; then
  set_env GNOSIS_USERNAME admin
fi
read -rsp 'Admin password (empty = keep current): ' WEB_PASS; echo
if [ -n "$WEB_PASS" ]; then set_env GNOSIS_PASSWORD "$WEB_PASS"; fi
if [ -z "$(get_env GNOSIS_PASSWORD)" ] || [ "$(get_env GNOSIS_PASSWORD)" = change-me ]; then
  echo 'Set a personal admin password before starting.' >&2; exit 1
fi

echo 'Chat: OpenAI-compatible API (paid or provider-limited tier), or your local model server.'
echo 'An agent/ChatGPT subscription does not include OpenAI API credits.'
read -rp 'Chat base URL (empty = keep current; OpenAI default if unset): ' BASE_URL
if [ -n "$BASE_URL" ]; then set_env GNOSIS_CHAT_BASE_URL "$BASE_URL"; fi
read -rp 'Chat model (empty = keep current): ' MODEL
if [ -n "$MODEL" ]; then set_env OPENAI_CHAT_MODEL "$MODEL"; fi
read -rsp 'Chat API key (local server: local; empty = keep current): ' CHAT_KEY; echo
if [ -n "$CHAT_KEY" ]; then set_env GNOSIS_CHAT_API_KEY "$CHAT_KEY"; fi

echo 'Platform credentials and channel allowlist can be added later in the dashboard.'
echo 'Allow UID/GID 10001 (container only) to write .env and config; no world permissions.'
# The operator owns these files; only the dedicated container group shares access.
if ! chgrp 10001 .env config config/sources.toml 2>/dev/null; then
  sudo chgrp 10001 .env config config/sources.toml
fi
chmod 660 .env config/sources.toml
chmod 2770 config

# A local build runs the checked-out fixes, not an older registry tag.
docker compose config --quiet
docker compose build
docker compose run --rm web gnosis db-init
docker compose up -d --force-recreate
printf '\nOpen http://127.0.0.1:%s (remote host: use an SSH tunnel).\n' "$(get_env GNOSIS_PORT)"
echo 'See README for Discord permissions, workspace isolation, health and backups.'
