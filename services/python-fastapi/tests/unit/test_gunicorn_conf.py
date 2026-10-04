"""gunicorn.conf.py is outside the coverage gate (bare configuration) but its pool-slot logic is checked here."""

import os
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

CONF = Path(__file__).parents[2] / "gunicorn.conf.py"


def load(monkeypatch: pytest.MonkeyPatch, **env: str) -> dict[str, Any]:
    for key in ("WORKERS", "DB_POOL_SIZE", "PORT", "WORKER_DB_POOL_SIZE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return runpy.run_path(str(CONF))


def spawn(conf: dict[str, Any], server: SimpleNamespace, pid: int) -> SimpleNamespace:
    worker = SimpleNamespace()
    conf["pre_fork"](server, worker)
    server.WORKERS[pid] = worker
    return worker


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = load(monkeypatch)
    assert (conf["workers"], conf["worker_class"], conf["accesslog"], conf["loglevel"]) == (
        2,
        "uvicorn_worker.UvicornWorker",
        None,
        "warning",
    )
    assert conf["bind"] == "0.0.0.0:8080"


def test_workers_share_the_pool_and_respawn_keeps_the_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = load(monkeypatch, WORKERS="3", DB_POOL_SIZE="10", PORT="9000")
    assert conf["bind"] == "0.0.0.0:9000"
    server = SimpleNamespace(WORKERS={})
    sizes = []
    for pid in (1, 2, 3):
        worker = spawn(conf, server, pid)
        conf["post_fork"](server, worker)
        sizes.append(int(os.environ["WORKER_DB_POOL_SIZE"]))
    assert sizes == [4, 3, 3]
    del server.WORKERS[1]  # worker in slot 0 dies; its replacement takes the same slot and share
    replacement = spawn(conf, server, 4)
    assert replacement.slot == 0
