package bench.items.application;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;

/** Use case: validate id and input, then replace the whole item. */
public class ReplaceItem {

  private final ItemRepository repository;

  public ReplaceItem(ItemRepository repository) {
    this.repository = repository;
  }

  public Item execute(long id, ItemInput input) {
    ItemInput.validateId(id);
    input.validate();
    return repository.replace(id, input);
  }
}
