"""PostgreSQL access: raw SQL through asyncpg, no ORM and no query builder.

The pool follows Documentation/specs/connection-pooling.md: fixed size, opened (pre-warmed) before the
worker serves traffic, 5 s acquire and command timeouts, no idle or lifetime eviction. Driver defaults
(prepared-statement cache) are kept (decision D-06).
"""

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

import asyncpg

from app.domain.errors import NotFoundError
from app.domain.item import Item, ItemInput

# Canonical statements (Documentation/specs/database-schema.md section 2), shared verbatim by all stacks.
SELECT_SQL = "SELECT id, name, description, price_cents, quantity, created_at, updated_at FROM items WHERE id = $1"
INSERT_SQL = (
    "INSERT INTO items (name, description, price_cents, quantity) VALUES ($1, $2, $3, $4) "
    "RETURNING id, name, description, price_cents, quantity, created_at, updated_at"
)
UPDATE_SQL = (
    "UPDATE items SET name = $2, description = $3, price_cents = $4, quantity = $5, updated_at = now() "
    "WHERE id = $1 RETURNING id, name, description, price_cents, quantity, created_at, updated_at"
)
DELETE_SQL = "DELETE FROM items WHERE id = $1"

ACQUIRE_TIMEOUT_SECONDS = 5
COMMAND_TIMEOUT_SECONDS = 5


class Pool(Protocol):
    """The part of an asyncpg pool the repository needs."""

    def acquire(self, *, timeout: float) -> AbstractAsyncContextManager[Any]: ...

    async def close(self) -> None: ...


async def open_pool(dsn: str, size: int) -> Pool:
    """A fixed-size pool: min = max = size, connections opened up front, never evicted."""
    return await asyncpg.create_pool(
        dsn,
        min_size=size,
        max_size=size,
        max_inactive_connection_lifetime=0,
        command_timeout=COMMAND_TIMEOUT_SECONDS,
    )


def _to_item(row: Any) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price_cents=row["price_cents"],
        quantity=row["quantity"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresItemRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def _one(self, sql: str, *args: Any) -> Item:
        async with self._pool.acquire(timeout=ACQUIRE_TIMEOUT_SECONDS) as connection:
            row = await connection.fetchrow(sql, *args)
        if row is None:
            raise NotFoundError
        return _to_item(row)

    async def get(self, item_id: int) -> Item:
        return await self._one(SELECT_SQL, item_id)

    async def create(self, data: ItemInput) -> Item:
        return await self._one(INSERT_SQL, data.name, data.description, data.price_cents, data.quantity)

    async def replace(self, item_id: int, data: ItemInput) -> Item:
        return await self._one(UPDATE_SQL, item_id, data.name, data.description, data.price_cents, data.quantity)

    async def delete(self, item_id: int) -> None:
        async with self._pool.acquire(timeout=ACQUIRE_TIMEOUT_SECONDS) as connection:
            status = await connection.execute(DELETE_SQL, item_id)
        if status == "DELETE 0":
            raise NotFoundError
