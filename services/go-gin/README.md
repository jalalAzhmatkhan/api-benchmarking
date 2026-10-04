# go-gin

**Stack:** Go 1.27.1 · Gin 1.12 · pgx/v5 `pgxpool` (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.5.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture)
```
cmd/server/main.go                 bare entrypoint (excluded from coverage)
internal/domain/                   Item, ItemInput validation, ItemRepository port, errors
internal/application/              GetItem, CreateItem, ReplaceItem, DeleteItem
internal/infrastructure/config/    DATABASE_URL, PORT, DB_POOL_SIZE
internal/infrastructure/postgres/  raw-SQL repository + pgxpool setup
internal/interfaces/http/          Gin routes, DTOs, error mapping
internal/app/                      composition root, graceful shutdown
```
Dependencies point inward: `interfaces`/`infrastructure` → `application` → `domain` (stdlib only).

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench go run ./cmd/server
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

go test ./... -covermode=atomic -coverprofile=cover.out     # 100 % except cmd/server
```

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| `gin.SetMode(gin.ReleaseMode)`, `gin.New()` | no Logger middleware | per-request logging off (`benchmark-rules.md`) |
| `gin.CustomRecovery` | maps panics to the contract 500 body | the only middleware |
| Pool | `MinConns = MaxConns = DB_POOL_SIZE` (10), lifetime 1 h, idle 30 min, pre-warmed | `connection-pooling.md` |
| Request timeout | 5 s around acquire + query | acquire timeout |
| `CGO_ENABLED=0 -trimpath -ldflags="-s -w"` | release build | no PGO, no GC flags |

Everything else is default: pgx statement caching (D-06), `GOMAXPROCS` (cgroup-aware), `net/http` server settings.
