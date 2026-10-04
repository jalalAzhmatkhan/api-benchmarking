from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.errors import ValidationError
from app.domain.item import Item, ItemInput


class ItemBody(BaseModel):
    """Request body. Strict: no coercion ("10", 1.5 and true are not integers); unknown fields are ignored.
    Range and length rules belong to the domain; any violation here is remapped to the contract's 400."""

    model_config = ConfigDict(strict=True, extra="ignore")

    name: str
    description: str | None = None
    price_cents: int
    quantity: int

    def to_input(self) -> ItemInput:
        return ItemInput(self.name, self.description, self.price_cents, self.quantity)


def parse_id(raw: str) -> int:
    """Decimal digits only (no sign, spaces or underscores); range rules are the domain's."""
    if not (raw.isascii() and raw.isdigit()):
        raise ValidationError("invalid id")
    return int(raw)


def to_response(item: Item) -> dict[str, Any]:
    """Wire format of an item (snake_case names per the contract, UTC timestamps with milliseconds)."""
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "price_cents": item.price_cents,
        "quantity": item.quantity,
        "created_at": _timestamp(item.created_at),
        "updated_at": _timestamp(item.updated_at),
    }


def _timestamp(moment: Any) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}
