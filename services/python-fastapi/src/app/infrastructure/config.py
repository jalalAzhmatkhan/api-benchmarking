from collections.abc import Mapping
from dataclasses import dataclass

# Matches deploy/compose.dev.yaml.
DEFAULT_DATABASE_URL = "postgres://bench:bench@127.0.0.1:5432/bench"


@dataclass(frozen=True, slots=True)
class Config:
    database_url: str
    port: int
    pool_size: int
    """Total pool size of the service (DB_POOL_SIZE); gunicorn.conf.py splits it across workers."""
    worker_pool_size: int
    """This worker's share (WORKER_DB_POOL_SIZE, set per worker by gunicorn.conf.py); the whole pool otherwise."""


def _integer(env: Mapping[str, str], key: str, fallback: int | None, maximum: int) -> int | None:
    """An optional positive integer from the environment; empty counts as unset."""
    raw = env.get(key, "")
    if raw == "":
        return fallback
    if not (raw.isascii() and raw.isdigit()) or not 1 <= int(raw) <= maximum:
        raise ValueError(f"invalid {key} {raw!r}")
    return int(raw)


def load_config(env: Mapping[str, str]) -> Config:
    """Reads the shared env contract (contract/README.md) plus the per-worker pool share."""
    pool_size = _integer(env, "DB_POOL_SIZE", 10, 10_000)
    assert pool_size is not None
    return Config(
        database_url=env.get("DATABASE_URL") or DEFAULT_DATABASE_URL,
        port=_integer(env, "PORT", 8080, 65535) or 8080,
        pool_size=pool_size,
        worker_pool_size=_integer(env, "WORKER_DB_POOL_SIZE", pool_size, 10_000) or pool_size,
    )


def worker_pool_size(total: int, workers: int, slot: int) -> int:
    """Splits the service-wide pool over the workers: the first `total % workers` slots get one extra."""
    return total // workers + (1 if slot < total % workers else 0)
