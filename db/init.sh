#!/usr/bin/env bash
# Idempotent: apply migrations, then seed if the table is empty. Used by the db-init container.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${HERE}/lib.sh"

if [[ "$(psql_run -tAc "SELECT to_regclass('public.items') IS NOT NULL")" != "t" ]]; then
  for f in "${HERE}"/migrations/*.sql; do
    echo "applying $(basename "$f")"
    psql_run -f - < "$f"
  done
fi
if [[ "$(psql_run -tAc "SELECT count(*) FROM items")" == "0" ]]; then
  echo "seeding"
  psql_run -f - < "${HERE}/seed/seed.sql"
  psql_run -c "VACUUM (ANALYZE) items"
fi
echo "items: $(psql_run -tAc "SELECT count(*) FROM items") rows"
