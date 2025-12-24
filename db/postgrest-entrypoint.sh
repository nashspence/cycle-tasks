#!/bin/sh
set -eu

# Ensure bundled utilities are discoverable even if the base image PATH is minimal
PATH="/usr/lib/postgresql/15/bin:/usr/bin:/bin:${PATH:-}"

: "${PGRST_DB_URI:?PGRST_DB_URI is required}"
: "${APPRISE_ENDPOINT:=http://apprise-api:8000/notify/}"

echo "[postgrest] waiting for database..."
while true; do
  if output=$(psql "$PGRST_DB_URI" -c 'select 1' 2>&1); then
    break
  fi

  echo "[postgrest] database not ready: ${output:-unknown error}; retrying in 1s..."
  sleep 1
done

echo "[postgrest] database is ready; applying schema"
PGRST_DB_URI="$PGRST_DB_URI" APPRISE_ENDPOINT="$APPRISE_ENDPOINT" "$(dirname "$0")/init.sh"

CONFIG_PATH=${1:-/db/postgrest.conf}

cat >"$CONFIG_PATH" <<EOF
db-uri = "${PGRST_DB_URI}"
db-schemas = "${PGRST_DB_SCHEMAS:-api}"
db-anon-role = "${PGRST_DB_ANON_ROLE:-anon}"
server-host = "${PGRST_SERVER_HOST:-0.0.0.0}"
server-port = ${PGRST_SERVER_PORT:-3000}
EOF

echo "[postgrest] starting postgrest with config ${CONFIG_PATH}"
exec postgrest "$CONFIG_PATH"
