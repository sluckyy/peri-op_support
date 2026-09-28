#!/bin/sh
# Default (no args): apply every migration in order -- for a fresh
# database only, since re-running an already-applied file fails (no
# schema_migrations tracking table yet, see docs/ops/azure-deployment.md).
# With one or more filenames as args: apply just those, in the order
# given -- for adding a new migration to an already-migrated database.
set -eu
: "${PERIOP_DATABASE_URL:?PERIOP_DATABASE_URL must be set}"
if [ "$#" -gt 0 ]; then
  files=""
  for name in "$@"; do
    files="$files /migrations/$name"
  done
else
  files="/migrations/*.sql"
fi
for f in $files; do
  echo "==> applying $f"
  psql "$PERIOP_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "==> all migrations applied"
