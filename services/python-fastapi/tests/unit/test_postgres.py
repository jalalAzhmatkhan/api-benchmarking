from typing import Any

import pytest

from app.domain.errors import NotFoundError
from app.domain.item import ItemInput
from app.infrastructure import postgres
from app.infrastructure.postgres import PostgresItemRepository, open_pool
from tests.unit.fakes import NOW, FakePool

INPUT = ItemInput("Widget", None, 1999, 5)


async def test_open_pool_is_fixed_size_and_never_evicts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def fake_create_pool(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "pool"

    monkeypatch.setattr(postgres.asyncpg, "create_pool", fake_create_pool)
    assert await open_pool("postgres://x", 5) == "pool"
    assert calls == [
        (
            ("postgres://x",),
            {"min_size": 5, "max_size": 5, "max_inactive_connection_lifetime": 0, "command_timeout": 5},
        )
    ]


async def test_crud_roundtrip_uses_canonical_sql_and_acquire_timeout() -> None:
    pool = FakePool()
    repo = PostgresItemRepository(pool)
    created = await repo.create(INPUT)
    assert (created.id, created.name, created.description, created.price_cents, created.quantity) == (
        100_001,
        "Widget",
        None,
        1999,
        5,
    )
    assert created.created_at == NOW
    assert (await repo.get(100_001)).name == "Widget"
    assert (await repo.replace(100_001, ItemInput("New", "d", 1, 2))).name == "New"
    await repo.delete(100_001)
    assert [sql for sql, _ in pool.statements] == [
        postgres.INSERT_SQL,
        postgres.SELECT_SQL,
        postgres.UPDATE_SQL,
        postgres.DELETE_SQL,
    ]
    assert pool.statements[2][1] == (100_001, "New", "d", 1, 2)
    assert set(pool.timeouts) == {5}


async def test_missing_rows_raise_not_found() -> None:
    repo = PostgresItemRepository(FakePool())
    with pytest.raises(NotFoundError):
        await repo.get(1)
    with pytest.raises(NotFoundError):
        await repo.replace(1, INPUT)
    with pytest.raises(NotFoundError):
        await repo.delete(1)
