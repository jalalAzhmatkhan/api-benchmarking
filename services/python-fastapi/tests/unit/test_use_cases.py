from datetime import UTC, datetime

import pytest

from app.application.use_cases import ItemUseCases
from app.domain.errors import NotFoundError, ValidationError
from app.domain.item import Item, ItemInput

NOW = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)
OK = ItemInput(name="n", description=None, price_cents=1, quantity=1)
BAD = ItemInput(name="", description=None, price_cents=1, quantity=1)


def item(item_id: int) -> Item:
    return Item(item_id, "n", None, 1, 1, NOW, NOW)


class FakeRepository:
    """Records calls; with `missing` every call raises NotFoundError."""

    def __init__(self, *, missing: bool = False) -> None:
        self.calls: list[str] = []
        self._missing = missing

    def _record(self, call: str) -> None:
        self.calls.append(call)
        if self._missing:
            raise NotFoundError

    async def get(self, item_id: int) -> Item:
        self._record("get")
        return item(item_id)

    async def create(self, data: ItemInput) -> Item:
        self._record("create")
        return item(100_001)

    async def replace(self, item_id: int, data: ItemInput) -> Item:
        self._record("replace")
        return item(item_id)

    async def delete(self, item_id: int) -> None:
        self._record("delete")


async def test_get() -> None:
    repo = FakeRepository()
    assert (await ItemUseCases(repo).get_item(7)).id == 7
    with pytest.raises(ValidationError):
        await ItemUseCases(repo).get_item(0)
    assert repo.calls == ["get"], "an invalid id must not reach the repository"
    with pytest.raises(NotFoundError):
        await ItemUseCases(FakeRepository(missing=True)).get_item(1)


async def test_create() -> None:
    repo = FakeRepository()
    assert (await ItemUseCases(repo).create_item(OK)).id == 100_001
    with pytest.raises(ValidationError):
        await ItemUseCases(repo).create_item(BAD)
    assert repo.calls == ["create"]


async def test_replace() -> None:
    repo = FakeRepository()
    assert (await ItemUseCases(repo).replace_item(5, OK)).id == 5
    with pytest.raises(ValidationError):
        await ItemUseCases(repo).replace_item(-1, OK)
    with pytest.raises(ValidationError):
        await ItemUseCases(repo).replace_item(1, BAD)
    assert repo.calls == ["replace"]
    with pytest.raises(NotFoundError):
        await ItemUseCases(FakeRepository(missing=True)).replace_item(1, OK)


async def test_delete() -> None:
    repo = FakeRepository()
    await ItemUseCases(repo).delete_item(3)
    with pytest.raises(ValidationError):
        await ItemUseCases(repo).delete_item(0)
    assert repo.calls == ["delete"]
    with pytest.raises(NotFoundError):
        await ItemUseCases(FakeRepository(missing=True)).delete_item(1)
