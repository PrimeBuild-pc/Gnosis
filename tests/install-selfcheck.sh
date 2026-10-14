#!/usr/bin/env bash
# Offline installer regression: isolated fixtures, fake Docker and permission commands.
set -euo pipefail
umask 077
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/config" "$TMP/bin"
cp "$ROOT/install.sh" "$ROOT/.env.example" "$TMP/"
export GNOSIS_TEST_COMMANDS="$TMP/commands.log"
for command in docker chmod chgrp; do
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "%s $*" >> "$GNOSIS_TEST_COMMANDS"\n' "$command" > "$TMP/bin/$command"
  chmod +x "$TMP/bin/$command"
done
(
  cd "$TMP"
  printf '\nprivate-test-password\n\n\n\n' | PATH="$TMP/bin:$PATH" bash install.sh > output.log
  grep -q '^GNOSIS_PASSWORD="private-test-password"$' .env
  ! grep -q 'private-test-password' output.log
  PG_PASS=$(awk -F= '$1=="POSTGRES_PASSWORD"{gsub(/"/, "", $2); print $2}' .env)
  grep -q "^DATABASE_URL=\"postgresql://gnosis:${PG_PASS}@db:5432/gnosis\"$" .env
  grep -q 'chmod 660 .env config/sources.toml' commands.log
  grep -q 'chmod 2770 config' commands.log
  ! grep -Eq '666|777' commands.log
  grep -q 'docker compose build' commands.log
  ! grep -q 'docker compose pull' commands.log
  ! grep -Eq '\[\[discord\]\]|\[\[reddit\]\]|\[\[telegram\]\]' config/sources.toml
  printf '\n\n\n\n\n' | PATH="$TMP/bin:$PATH" bash install.sh > output.log
  grep -q '^GNOSIS_PASSWORD="private-test-password"$' .env
  grep -q "^POSTGRES_PASSWORD=\"${PG_PASS}\"$" .env
  # Shell serialization must match the Python writer even for interpolation syntax/quotes.
  export GNOSIS_TEST_SECRET='${GNOSIS_TEST_MISSING:?blocked}"back\slash'
  printf '\n%s\n\n\n\n' "$GNOSIS_TEST_SECRET" | PATH="$TMP/bin:$PATH" bash install.sh > output.log
  python - <<'PY'
import json
import os
from pathlib import Path
line = next(line for line in Path('.env').read_text().splitlines() if line.startswith('GNOSIS_PASSWORD='))
assert json.loads(line.partition('=')[2]).replace('$$', '$') == os.environ['GNOSIS_TEST_SECRET']
PY
  echo 'installer contracts: OK'
)
