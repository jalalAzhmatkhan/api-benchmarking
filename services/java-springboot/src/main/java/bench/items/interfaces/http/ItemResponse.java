package bench.items.interfaces.http;

import bench.items.domain.Item;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.format.DateTimeFormatter;

/** Wire format of an item (snake_case field names per the contract). */
public record ItemResponse(
    @JsonProperty("id") long id,
    @JsonProperty("name") String name,
    @JsonProperty("description") String description,
    @JsonProperty("price_cents") long priceCents,
    @JsonProperty("quantity") int quantity,
    @JsonProperty("created_at") String createdAt,
    @JsonProperty("updated_at") String updatedAt) {

  static ItemResponse from(Item item) {
    return new ItemResponse(
        item.id(),
        item.name(),
        item.description(),
        item.priceCents(),
        item.quantity(),
        DateTimeFormatter.ISO_INSTANT.format(item.createdAt()),
        DateTimeFormatter.ISO_INSTANT.format(item.updatedAt()));
  }
}
