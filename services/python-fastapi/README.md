# python-fastapi

**Stack:** Python 3.14 · FastAPI 0.142 · gunicorn 26.2 + `uvicorn-worker` (uvicorn 0.54, uvloop, httptools) · asyncpg 0.31 (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.1.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture)
```
src/app/domain/          Item, ItemInput, ItemRepository port, validation (code points), ValidationError/NotFoundError
src/app/application/     ItemUseCases: get_item, create_item, replace_item, delete_item
src/app/infrastructure/  config.py (env contract, per-worker pool split), postgres.py (raw-SQL repository, pool)
src/app/interface/http/  routes.py (routes, error mapping), wire.py (strict body model, id parsing, wire format)
src/app/main.py          composition root: lifespan opens the pool, builds repository -> use cases; exports `app`
gunicorn.conf.py         process manager: UvicornWorker, WORKERS, access log off, pool share per worker slot
tests/unit/              fakes in place of the database; tests/integration/ needs DATABASE_URL
```
Dependencies point inward.

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
uv sync --frozen
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench PYTHONPATH=src WORKERS=2 uv run gunicorn -c gunicorn.conf.py app.main:app   # Linux/macOS (gunicorn needs fork)
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

uv run ruff check . && uv run ruff format --check .
DATABASE_URL=... uv run pytest      # 100 % line+branch gate; DATABASE_URL enables the database test
```

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| gunicorn workers | `WORKERS` (**2** on the SUT via `deploy/stacks/python-fastapi.env`) | one event loop per vCPU (D-11); ablations 3 and 5 (2n+1) |
| Worker class | `uvicorn_worker.UvicornWorker` | async ASGI workers under gunicorn's supervision |
| Pool | total `DB_POOL_SIZE` (10) split across workers (5 + 5; 3 workers: 4+3+3). Each worker: `min_size = max_size`, `max_inactive_connection_lifetime=0` (no eviction), `command_timeout=5`, `acquire(timeout=5)`, opened in the lifespan before the worker serves | `connection-pooling.md` |
| Logging | gunicorn access log off, log level `warning` | per-request logging off |
| FastAPI | no middleware; docs/OpenAPI endpoints off; no trailing-slash redirect | the service exposes exactly the contract's routes |
| Request handling | strict pydantic body (no coercion), id parsed as decimal digits; FastAPI's 422 remapped to the contract's 400 | contract error shape |

Default: asyncpg prepared-statement cache and codecs (D-06), uvicorn/gunicorn limits, no tuning flags.

**Known differences from the other stacks** (outside the conformance suite): JSON numbers written as `1.0` or `1e3` are rejected for integer fields (strict typing), where the Node stack accepts them; unknown routes answer the contract error shape with the framework's status (404 / 405).
