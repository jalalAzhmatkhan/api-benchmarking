"""In-memory stand-in for an asyncpg pool: just enough SQL awareness to serve the four canonical statements."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from app.infrastructure import postgres

NOW = datetime(2026, 10, 3, 10, 0, 0, 123456, tzinfo=UTC)


class FakeConnection:
    def __init__(self, pool: FakePool) -> None:
        self._pool = pool

    def _row(self, item_id: int) -> dict[str, Any] | None:
        return self._pool.rows.get(item_id)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self._pool.statements.append((sql, args))
        if self._pool.fail:
            raise RuntimeError("database down")
        if sql == postgres.SELECT_SQL:
            return self._row(args[0])
        if sql == postgres.INSERT_SQL:
            row = self._pool.store(self._pool.next_id, *args)
            self._pool.next_id += 1
            return row
        assert sql == postgres.UPDATE_SQL
        return self._pool.store(args[0], *args[1:]) if self._row(args[0]) else None

    async def execute(self, sql: str, *args: Any) -> str:
        self._pool.statements.append((sql, args))
        assert sql == postgres.DELETE_SQL
        return f"DELETE {1 if self._pool.rows.pop(args[0], None) else 0}"


class FakePool:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}
        self.statements: list[tuple[str, tuple[Any, ...]]] = []
        self.timeouts: list[float] = []
        self.next_id = 100_001
        self.fail = False
        self.closed = False

    def store(
        self, item_id: int, name: str, description: str | None, price_cents: int, quantity: int
    ) -> dict[str, Any]:
        row = {
            "id": item_id,
            "name": name,
            "description": description,
            "price_cents": price_cents,
            "quantity": quantity,
            "created_at": NOW,
            "updated_at": NOW,
        }
        self.rows[item_id] = row
        return row

    @asynccontextmanager
    async def acquire(self, *, timeout: float):
        self.timeouts.append(timeout)
        yield FakeConnection(self)

    async def close(self) -> None:
        self.closed = True
