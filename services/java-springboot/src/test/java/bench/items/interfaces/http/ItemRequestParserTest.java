package bench.items.interfaces.http;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import bench.items.domain.ItemInput;
import bench.items.domain.ValidationException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class ItemRequestParserTest {

  private static ItemInput parse(String json) {
    return ItemRequestParser.parse(json.getBytes(UTF_8));
  }

  @Test
  void parsesAValidBody() {
    assertThat(parse("{\"name\":\"Widget\",\"description\":\"Blue\",\"price_cents\":1999,\"quantity\":5}"))
        .isEqualTo(new ItemInput("Widget", "Blue", 1999, 5));
  }

  @Test
  void descriptionAbsentOrNullBecomesNull() {
    assertThat(parse("{\"name\":\"n\",\"price_cents\":1,\"quantity\":1}").description()).isNull();
    assertThat(parse("{\"name\":\"n\",\"description\":null,\"price_cents\":1,\"quantity\":1}").description()).isNull();
  }

  @Test
  void unknownFieldsAreIgnored() {
    assertThat(parse("{\"name\":\"n\",\"price_cents\":1,\"quantity\":1,\"unknown\":true,\"id\":9}").name()).isEqualTo("n");
  }

  @Test
  void largeIntegersWithinLongAreKept() {
    ItemInput in = parse("{\"name\":\"n\",\"price_cents\":9007199254740992,\"quantity\":2147483648}");
    assertThat(in.priceCents()).isEqualTo(9_007_199_254_740_992L); // the domain rejects it, not the parser
    assertThat(in.quantity()).isEqualTo(2_147_483_648L);
  }

  @ParameterizedTest
  @ValueSource(strings = {
      "",
      "{\"name\":",
      "[]",
      "\"x\"",
      "null",
      "5",
      "{\"price_cents\":1,\"quantity\":1}",
      "{\"name\":null,\"price_cents\":1,\"quantity\":1}",
      "{\"name\":5,\"price_cents\":1,\"quantity\":1}",
      "{\"name\":\"n\",\"description\":5,\"price_cents\":1,\"quantity\":1}",
      "{\"name\":\"n\",\"quantity\":1}",
      "{\"name\":\"n\",\"price_cents\":\"10\",\"quantity\":1}",
      "{\"name\":\"n\",\"price_cents\":1.5,\"quantity\":1}",
      "{\"name\":\"n\",\"price_cents\":null,\"quantity\":1}",
      "{\"name\":\"n\",\"price_cents\":99999999999999999999,\"quantity\":1}",
      "{\"name\":\"n\",\"price_cents\":1}",
      "{\"name\":\"n\",\"price_cents\":1,\"quantity\":1.5}",
      "{\"name\":\"n\",\"price_cents\":1,\"quantity\":\"1\"}",
      "{\"name\":\"n\",\"price_cents\":true,\"quantity\":1}"
  })
  void rejectsInvalidBodies(String json) {
    assertThatThrownBy(() -> parse(json)).isInstanceOf(ValidationException.class);
  }

  @Test
  void aMissingBodyIsInvalid() {
    assertThatThrownBy(() -> ItemRequestParser.parse(null)).isInstanceOf(ValidationException.class);
  }
}
