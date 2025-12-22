#!/usr/bin/env bash
set -euo pipefail

: "${APPRISE_ENDPOINT:=http://apprise-api:8000/notify/}"

psql -v ON_ERROR_STOP=1 \
  --username postgres --dbname postgres \
  -v apprise_endpoint="$APPRISE_ENDPOINT" \
  -f /schema.sql