# go-gin

**Stack:** Go 1.27 · Gin 1.12 · pgx/v5 pgxpool
**Status:** not implemented yet. Tasks `T-2.5.a/b/c` in `Documentation/plans/implementation-tasks.md`.

Implements the shared `/items` contract (`contract/openapi.yaml`) with clean architecture
(`domain` → `application` → `infrastructure` → `interface/http`), raw SQL, connection pooling,
no ORM and no caching, at 100 % unit-test coverage.

## Run / test
_To be filled in by the implementation task._

## Non-default configuration knobs
_Every deviation from framework defaults (pool, workers, release mode, logging) is listed here._
