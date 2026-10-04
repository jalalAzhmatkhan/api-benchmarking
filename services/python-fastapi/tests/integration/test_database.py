"""Against a real PostgreSQL (the dev compose database); skipped without DATABASE_URL. CI sets it."""

import os

import pytest

from app.domain.errors import NotFoundError
from app.domain.item import ItemInput
from app.infrastructure.postgres import PostgresItemRepository, open_pool

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


async def test_pool_is_prewarmed_and_crud_works() -> None:
    pool = await open_pool(os.environ["DATABASE_URL"], 3)
    try:
        async with pool.acquire(timeout=5) as connection:
            open_connections = await connection.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND usename = current_user"
                " AND application_name = ''"
            )
        assert open_connections >= 3, "min_size connections are opened before the first request"
        repo = PostgresItemRepository(pool)
        created = await repo.create(ItemInput("Integration", None, 1, 1))
        assert (await repo.get(created.id)).name == "Integration"
        assert (await repo.replace(created.id, ItemInput("Changed", "d", 2, 2))).updated_at >= created.created_at
        await repo.delete(created.id)
        with pytest.raises(NotFoundError):
            await repo.get(created.id)
    finally:
        await pool.close()
