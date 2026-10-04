package bench.items.application;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;

/** Use case: validate and create an item. */
public class CreateItem {

  private final ItemRepository repository;

  public CreateItem(ItemRepository repository) {
    this.repository = repository;
  }

  public Item execute(ItemInput input) {
    input.validate();
    return repository.create(input);
  }
}
