from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.errors import ValidationError

# Limits from the API contract (Documentation/specs/api-contract.md).
MAX_ID = 9_007_199_254_740_991
MAX_PRICE_CENTS = 9_007_199_254_740_991
MAX_QUANTITY = 2_147_483_647
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    name: str
    description: str | None
    price_cents: int
    quantity: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ItemInput:
    name: str
    description: str | None
    price_cents: int
    quantity: int


class ItemRepository(Protocol):
    """Persistence port, implemented by the infrastructure layer. Missing items raise NotFoundError."""

    async def get(self, item_id: int) -> Item: ...

    async def create(self, data: ItemInput) -> Item: ...

    async def replace(self, item_id: int, data: ItemInput) -> Item: ...

    async def delete(self, item_id: int) -> None: ...


def validate_id(item_id: int) -> None:
    if not 1 <= item_id <= MAX_ID:
        raise ValidationError("invalid id")


def validate_input(data: ItemInput) -> None:
    """Applies the contract's field rules. Python's len() counts Unicode code points."""
    if not 1 <= len(data.name) <= MAX_NAME_LENGTH:
        raise ValidationError("name must be 1-100 characters")
    if data.description is not None and len(data.description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError("description must be at most 1000 characters")
    if not 0 <= data.price_cents <= MAX_PRICE_CENTS:
        raise ValidationError("price_cents must be an integer in 0..9007199254740991")
    if not 0 <= data.quantity <= MAX_QUANTITY:
        raise ValidationError("quantity must be an integer in 0..2147483647")
