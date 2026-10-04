#!/usr/bin/env bash
# Idempotent: create the schema (001) if missing, apply the idempotent migrations (002+), then seed
# if the table is empty. Used by the db-init container.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${HERE}/lib.sh"

if [[ "$(psql_run -tAc "SELECT to_regclass('public.items') IS NOT NULL")" != "t" ]]; then
  echo "applying 001_init.sql"
  psql_run -f - < "${HERE}/migrations/001_init.sql"
fi
for f in "${HERE}"/migrations/00[2-9]_*.sql "${HERE}"/migrations/0[1-9][0-9]_*.sql; do
  [[ -e "$f" ]] || continue
  echo "applying $(basename "$f")"
  psql_run -f - < "$f"
done
if [[ "$(psql_run -tAc "SELECT count(*) FROM items")" == "0" ]]; then
  echo "seeding"
  psql_run -f - < "${HERE}/seed/seed.sql"
  psql_run -c "VACUUM (ANALYZE) items"
fi
echo "items: $(psql_run -tAc "SELECT count(*) FROM items") rows"
