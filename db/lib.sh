# Shared helpers for db/*.sh. Source this file; do not execute it.
# Connection: standard libpq env vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE), or set
# DB_CONTAINER=<name> to run psql inside a running PostgreSQL container (used on the SUT host,
# which only has Docker installed).
DB_USER="${PGUSER:-bench}"
DB_NAME="${PGDATABASE:-bench}"

psql_run() {
  if [[ -n "${DB_CONTAINER:-}" ]]; then
    docker exec -i "${DB_CONTAINER}" psql -X -q -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" "$@"
  else
    psql -X -q -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" "$@"
  fi
}
