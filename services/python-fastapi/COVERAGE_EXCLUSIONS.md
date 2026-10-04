# Coverage exclusions: python-fastapi

None inside the application package.

Gate (`uv run pytest`): **100 % line and branch coverage** of everything under `src/app/` (`--cov-fail-under=100`),
including the composition root `src/app/main.py`, which the HTTP tests drive through `create_app`.

| Path | Reason |
|---|---|
| `gunicorn.conf.py` | Bare process-manager configuration, outside the measured package. Its only logic (assigning each worker a pool share) is unit-tested in `tests/unit/test_gunicorn_conf.py` and the share arithmetic (`worker_pool_size`) is in the measured package |
| `tests/` | Test files themselves |

Everything but the database-backed integration test (`tests/integration/`, skipped without `DATABASE_URL`) runs without a
database; CI sets `DATABASE_URL` so it runs too.
