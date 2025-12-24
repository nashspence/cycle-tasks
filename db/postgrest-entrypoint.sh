#!/bin/sh
set -eu

: "${PGRST_DB_URI:?PGRST_DB_URI is required}"
: "${APPRISE_ENDPOINT:=http://apprise-api:8000/notify/}"

echo "[postgrest] waiting for database..."
until pg_isready -d "$PGRST_DB_URI" >/dev/null 2>&1; do
  echo "[postgrest] database not ready, retrying in 1s..."
  sleep 1
done

echo "[postgrest] database is ready; applying schema"
PGRST_DB_URI="$PGRST_DB_URI" APPRISE_ENDPOINT="$APPRISE_ENDPOINT" "$(dirname "$0")/init.sh"

echo "[postgrest] starting postgrest"
exec postgrest "$@"
