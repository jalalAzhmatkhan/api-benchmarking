class ValidationError(Exception):
    """A request violates a contract rule (maps to 400 VALIDATION_ERROR)."""


class NotFoundError(Exception):
    """The item does not exist (maps to 404 NOT_FOUND)."""

    def __init__(self) -> None:
        super().__init__("item not found")
