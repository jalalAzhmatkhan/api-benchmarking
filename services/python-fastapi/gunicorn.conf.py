# gunicorn configuration (decision D-11: 2 async workers, one event loop per vCPU).
# Only the knobs below differ from gunicorn defaults. Bare configuration, excluded from coverage
# (COVERAGE_EXCLUSIONS.md); the pool split it uses (`worker_pool_size`) is unit-tested.
import os

from app.infrastructure.config import load_config, worker_pool_size

_total_pool = load_config(os.environ).pool_size

workers = int(os.environ.get("WORKERS") or 2)
worker_class = "uvicorn_worker.UvicornWorker"
bind = f"0.0.0.0:{load_config(os.environ).port}"
accesslog = None  # per-request logging off (benchmark-rules.md)
loglevel = "warning"


def pre_fork(server, worker):
    """Gives the new worker the lowest free slot, so a respawned worker inherits its predecessor's pool share."""
    taken = {getattr(other, "slot", None) for other in server.WORKERS.values()}
    worker.slot = next(slot for slot in range(workers) if slot not in taken)


def post_fork(server, worker):
    """Runs in the child before the app is imported: this worker's share of the service-wide pool."""
    os.environ["WORKER_DB_POOL_SIZE"] = str(worker_pool_size(_total_pool, workers, worker.slot))
