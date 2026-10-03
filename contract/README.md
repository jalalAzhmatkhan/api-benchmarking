# contract/: API contract

| File | Purpose |
|---|---|
| `openapi.yaml` | **Source of truth** for the 4-endpoint `/items` API (copied from the workspace `Documentation/specs/`; human-readable version: `api-contract.md` there) |
| `.spectral.yaml` | Lint rules (Spectral). CI: *Contract lint* |
| `conformance.js` | Black-box k6 suite every service must pass 100 % (task T-1.3) |
| `mock/server.py` | Stdlib reference server used **only** to self-test the suite in CI (T-1.3) |

A contract change is a MAJOR version: it needs a decision-log entry and invalidates earlier results.

## Runtime configuration contract (all services)
| Env var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgres://bench:bench@127.0.0.1:5432/bench` | PostgreSQL connection string |
| `PORT` | `8080` | HTTP listen port (`0.0.0.0`) |
| `DB_POOL_SIZE` | `10` | **Total** pool size per service (split across workers; `connection-pooling.md`) |
