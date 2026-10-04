package bench.items.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class ItemInputTest {

  private static ItemInput input(String name, String description, long price, long quantity) {
    return new ItemInput(name, description, price, quantity);
  }

  private static ItemInput valid() {
    return input("Widget", "Blue", 1999, 5);
  }

  private static void assertInvalid(ItemInput in) {
    assertThatThrownBy(in::validate).isInstanceOf(ValidationException.class).hasMessageNotContaining("null");
  }

  @Test
  void validInputPasses() {
    assertThatCode(valid()::validate).doesNotThrowAnyException();
  }

  @Test
  void descriptionVariants() {
    for (String d : new String[] {null, "", "d".repeat(1000), "é".repeat(1000)}) {
      assertThatCode(input("n", d, 1, 1)::validate).doesNotThrowAnyException();
    }
    assertInvalid(input("n", "d".repeat(1001), 1, 1));
  }

  @Test
  void nameLengthsCountCodePoints() {
    for (String n : new String[] {"a", "a".repeat(100), "é".repeat(100), "😀".repeat(100)}) {
      assertThatCode(input(n, null, 1, 1)::validate).doesNotThrowAnyException();
    }
    for (String n : new String[] {"", "a".repeat(101), "😀".repeat(101)}) {
      assertInvalid(input(n, null, 1, 1));
    }
  }

  @Test
  void priceBounds() {
    assertThatCode(input("n", null, 0, 1)::validate).doesNotThrowAnyException();
    assertThatCode(input("n", null, ItemInput.MAX_PRICE_CENTS, 1)::validate).doesNotThrowAnyException();
    assertInvalid(input("n", null, -1, 1));
    assertInvalid(input("n", null, ItemInput.MAX_PRICE_CENTS + 1, 1));
  }

  @Test
  void quantityBounds() {
    assertThatCode(input("n", null, 1, 0)::validate).doesNotThrowAnyException();
    assertThatCode(input("n", null, 1, ItemInput.MAX_QUANTITY)::validate).doesNotThrowAnyException();
    assertInvalid(input("n", null, 1, -1));
    assertInvalid(input("n", null, 1, ItemInput.MAX_QUANTITY + 1));
  }

  @ParameterizedTest
  @ValueSource(longs = {1, 100_001, ItemInput.MAX_ID})
  void validIds(long id) {
    assertThatCode(() -> ItemInput.validateId(id)).doesNotThrowAnyException();
  }

  @ParameterizedTest
  @ValueSource(longs = {0, -1, ItemInput.MAX_ID + 1})
  void invalidIds(long id) {
    assertThatThrownBy(() -> ItemInput.validateId(id)).isInstanceOf(ValidationException.class).hasMessage("invalid id");
  }

  @Test
  void exceptionTypes() {
    assertThat(new NotFoundException()).hasMessage("item not found").isInstanceOf(DomainException.class);
    assertThat(new ValidationException("bad")).hasMessage("bad").isInstanceOf(DomainException.class);
  }
}
