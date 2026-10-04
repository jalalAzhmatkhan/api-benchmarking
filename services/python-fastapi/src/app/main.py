"""Composition root: config -> pool -> repository -> use cases -> FastAPI app.

Served by gunicorn (`app.main:app`, see gunicorn.conf.py); each worker process runs its own lifespan,
so each owns its share of the connection pool.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.use_cases import ItemUseCases
from app.infrastructure.config import load_config
from app.infrastructure.postgres import Pool, PostgresItemRepository, open_pool
from app.interface.http import routes

PoolFactory = Callable[[str, int], Awaitable[Pool]]


def create_app(env: Mapping[str, str] | None = None, pool_factory: PoolFactory = open_pool) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = load_config(os.environ if env is None else env)
        pool = await pool_factory(config.database_url, config.worker_pool_size)
        app.state.use_cases = ItemUseCases(PostgresItemRepository(pool))
        try:
            yield
        finally:
            await pool.close()

    # Docs and OpenAPI endpoints are off: the service exposes exactly the contract's routes.
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.router.redirect_slashes = False
    routes.install(app)
    return app


app = create_app()
