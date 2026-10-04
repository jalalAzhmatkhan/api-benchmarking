from dataclasses import replace

import pytest

from app.domain.errors import NotFoundError, ValidationError
from app.domain.item import MAX_ID, MAX_PRICE_CENTS, MAX_QUANTITY, ItemInput, validate_id, validate_input

VALID = ItemInput(name="Widget", description="Blue", price_cents=1999, quantity=5)


def with_(**changes: object) -> ItemInput:
    return replace(VALID, **changes)


@pytest.mark.parametrize("item_id", [1, 100_001, MAX_ID])
def test_valid_ids(item_id: int) -> None:
    validate_id(item_id)


@pytest.mark.parametrize("item_id", [0, -1, MAX_ID + 1])
def test_invalid_ids(item_id: int) -> None:
    with pytest.raises(ValidationError):
        validate_id(item_id)


def test_valid_input() -> None:
    validate_input(VALID)


@pytest.mark.parametrize("description", [None, "", "d" * 1000, "é" * 1000, "😀" * 1000])
def test_valid_descriptions(description: str | None) -> None:
    validate_input(with_(description=description))


@pytest.mark.parametrize("description", ["d" * 1001, "😀" * 1001])
def test_invalid_descriptions(description: str) -> None:
    with pytest.raises(ValidationError):
        validate_input(with_(description=description))


@pytest.mark.parametrize("name", ["a", "a" * 100, "é" * 100, "😀" * 100])
def test_name_length_counts_code_points(name: str) -> None:
    validate_input(with_(name=name))


@pytest.mark.parametrize("name", ["", "a" * 101, "😀" * 101])
def test_invalid_names(name: str) -> None:
    with pytest.raises(ValidationError):
        validate_input(with_(name=name))


@pytest.mark.parametrize(
    ("field", "value"),
    [("price_cents", -1), ("price_cents", MAX_PRICE_CENTS + 1), ("quantity", -1), ("quantity", MAX_QUANTITY + 1)],
)
def test_out_of_range_numbers(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        validate_input(with_(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [("price_cents", 0), ("price_cents", MAX_PRICE_CENTS), ("quantity", 0), ("quantity", MAX_QUANTITY)],
)
def test_number_bounds_accepted(field: str, value: int) -> None:
    validate_input(with_(**{field: value}))


def test_not_found_message_is_fixed() -> None:
    assert str(NotFoundError()) == "item not found"
