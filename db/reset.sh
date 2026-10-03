#!/usr/bin/env bash
# Reset the benchmark database to its pristine seeded state (between levels and repetitions).
# Spec: Documentation/specs/database-schema.md §4. Requires a superuser (CHECKPOINT, pg_stat_reset).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "${HERE}/lib.sh"

start_ns=$(date +%s%N)
psql_run -c "TRUNCATE items RESTART IDENTITY"
psql_run -f - < "${HERE}/seed/seed.sql"
psql_run -c "VACUUM (ANALYZE) items"   # separate calls: VACUUM cannot run in a transaction block
psql_run -c "CHECKPOINT"
psql_run -c "SELECT pg_stat_reset()" >/dev/null
rows="$(psql_run -tAc "SELECT count(*) FROM items")"
elapsed_ms=$(( ($(date +%s%N) - start_ns) / 1000000 ))
echo "reset: ${rows} rows in ${elapsed_ms} ms"
[[ "${rows}" == "100000" ]] || { echo "unexpected row count: ${rows}" >&2; exit 1; }
