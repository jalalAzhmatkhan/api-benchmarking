from app.domain.item import Item, ItemInput, ItemRepository, validate_id, validate_input


class ItemUseCases:
    """The four operations of the contract: validate, then delegate to the repository port."""

    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    async def get_item(self, item_id: int) -> Item:
        validate_id(item_id)
        return await self._repository.get(item_id)

    async def create_item(self, data: ItemInput) -> Item:
        validate_input(data)
        return await self._repository.create(data)

    async def replace_item(self, item_id: int, data: ItemInput) -> Item:
        validate_id(item_id)
        validate_input(data)
        return await self._repository.replace(item_id, data)

    async def delete_item(self, item_id: int) -> None:
        validate_id(item_id)
        await self._repository.delete(item_id)
