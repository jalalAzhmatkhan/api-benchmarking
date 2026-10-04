package bench.items.domain;

/** Persistence port, implemented by the infrastructure layer. */
public interface ItemRepository {

  /** @throws NotFoundException if the item does not exist */
  Item get(long id);

  Item create(ItemInput input);

  /** @throws NotFoundException if the item does not exist */
  Item replace(long id, ItemInput input);

  /** @throws NotFoundException if the item does not exist */
  void delete(long id);
}
