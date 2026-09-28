#!/bin/sh
set -eu
: "${PERIOP_DATABASE_URL:?PERIOP_DATABASE_URL must be set}"
for f in /migrations/*.sql; do
  echo "==> applying $f"
  psql "$PERIOP_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "==> all migrations applied"
