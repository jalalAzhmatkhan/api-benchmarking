package bench.items.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.ItemRepository;
import bench.items.domain.NotFoundException;
import bench.items.domain.ValidationException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class UseCasesTest {

  /** Records calls; optionally fails every call with NotFoundException. */
  static class FakeRepository implements ItemRepository {
    final List<String> calls = new ArrayList<>();
    final boolean missing;

    FakeRepository(boolean missing) {
      this.missing = missing;
    }

    private Item item(long id) {
      Instant now = Instant.parse("2026-10-03T10:00:00Z");
      return new Item(id, "n", null, 1, 1, now, now);
    }

    private void record(String call) {
      calls.add(call);
      if (missing) {
        throw new NotFoundException();
      }
    }

    @Override
    public Item get(long id) {
      record("get");
      return item(id);
    }

    @Override
    public Item create(ItemInput input) {
      record("create");
      return item(100_001);
    }

    @Override
    public Item replace(long id, ItemInput input) {
      record("replace");
      return item(id);
    }

    @Override
    public void delete(long id) {
      record("delete");
    }
  }

  private static final ItemInput OK = new ItemInput("n", null, 1, 1);
  private static final ItemInput BAD = new ItemInput("", null, 1, 1);

  @Test
  void getItem() {
    FakeRepository repo = new FakeRepository(false);
    assertThat(new GetItem(repo).execute(7).id()).isEqualTo(7);
    assertThatThrownBy(() -> new GetItem(repo).execute(0)).isInstanceOf(ValidationException.class);
    assertThat(repo.calls).containsExactly("get");
    assertThatThrownBy(() -> new GetItem(new FakeRepository(true)).execute(1)).isInstanceOf(NotFoundException.class);
  }

  @Test
  void createItem() {
    FakeRepository repo = new FakeRepository(false);
    assertThat(new CreateItem(repo).execute(OK).id()).isEqualTo(100_001);
    assertThatThrownBy(() -> new CreateItem(repo).execute(BAD)).isInstanceOf(ValidationException.class);
    assertThat(repo.calls).containsExactly("create");
  }

  @Test
  void replaceItem() {
    FakeRepository repo = new FakeRepository(false);
    assertThat(new ReplaceItem(repo).execute(5, OK).id()).isEqualTo(5);
    assertThatThrownBy(() -> new ReplaceItem(repo).execute(-1, OK)).isInstanceOf(ValidationException.class);
    assertThatThrownBy(() -> new ReplaceItem(repo).execute(1, BAD)).isInstanceOf(ValidationException.class);
    assertThat(repo.calls).containsExactly("replace");
    assertThatThrownBy(() -> new ReplaceItem(new FakeRepository(true)).execute(1, OK)).isInstanceOf(NotFoundException.class);
  }

  @Test
  void deleteItem() {
    FakeRepository repo = new FakeRepository(false);
    new DeleteItem(repo).execute(9);
    assertThatThrownBy(() -> new DeleteItem(repo).execute(0)).isInstanceOf(ValidationException.class);
    assertThat(repo.calls).containsExactly("delete");
    assertThatThrownBy(() -> new DeleteItem(new FakeRepository(true)).execute(1)).isInstanceOf(NotFoundException.class);
  }
}
