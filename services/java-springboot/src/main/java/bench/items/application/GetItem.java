package bench.items.application;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;

/** Use case: load one item. */
public class GetItem {

  private final ItemRepository repository;

  public GetItem(ItemRepository repository) {
    this.repository = repository;
  }

  public Item execute(long id) {
    ItemInput.validateId(id);
    return repository.get(id);
  }
}
