package bench.items.application;

import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;

/** Use case: delete an item. */
public class DeleteItem {

  private final ItemRepository repository;

  public DeleteItem(ItemRepository repository) {
    this.repository = repository;
  }

  public void execute(long id) {
    ItemInput.validateId(id);
    repository.delete(id);
  }
}
