# db/: Database schema & data

Spec: `Documentation/specs/database-schema.md`. PostgreSQL 18.

| Path | Purpose |
|---|---|
| `migrations/001_init.sql` | `items` table (primary-key index only) |
| `seed/seed.sql` | 100 000 deterministic rows. Ids `1..100000` are read-only during benchmarks |
| `init.sh` | Idempotent: apply migrations, seed if empty (runs in the `db-init` container) |
| `reset.sh` | Pristine state between levels: truncate + restart identity, reseed, `VACUUM (ANALYZE)`, `CHECKPOINT`, `pg_stat_reset()`. First id created afterwards is `100001` |
| `lib.sh` | `psql_run` helper. Set `DB_CONTAINER=<name>` to run through `docker exec` (SUT host has no psql) |

```bash
# local dev (see deploy/compose.dev.yaml)
PGHOST=127.0.0.1 PGPASSWORD=bench db/reset.sh
# on the SUT
DB_CONTAINER=bench-postgres db/reset.sh
```
The `bench` role is a PostgreSQL superuser (it is the image's bootstrap user), which `CHECKPOINT` and
`pg_stat_reset()` need. Services connect as the same role.
