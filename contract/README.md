# contract/: API contract

| File | Purpose |
|---|---|
| `openapi.yaml` | **Source of truth** for the 4-endpoint `/items` API (copied from the workspace `Documentation/specs/`; human-readable version: `api-contract.md` there) |
| `.spectral.yaml` | Lint rules (Spectral). CI: *Contract lint* |
| `conformance.js` | Black-box k6 suite (≈300 checks) every service must pass 100 %: `k6 run -e BASE_URL=http://127.0.0.1:8080 contract/conformance.js` |
| `mock/server.py` | Stdlib reference server used **only** to self-test the suite. `MOCK_BUG=status422\|no_location\|put_merge\|delete_200\|accept_float` injects a violation |
| `selftest.sh` | Suite must pass on the correct mock and fail on every injected bug. CI: *Conformance suite self-test* |

A contract change is a MAJOR version: it needs a decision-log entry and invalidates earlier results.

## Runtime configuration contract (all services)
| Env var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgres://bench:bench@127.0.0.1:5432/bench` | PostgreSQL connection string |
| `PORT` | `8080` | HTTP listen port (`0.0.0.0`) |
| `DB_POOL_SIZE` | `10` | **Total** pool size per service (split across workers; `connection-pooling.md`) |
