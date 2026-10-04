package bench.items.interfaces.http;

import bench.items.application.CreateItem;
import bench.items.application.DeleteItem;
import bench.items.application.GetItem;
import bench.items.application.ReplaceItem;
import bench.items.domain.Item;
import bench.items.domain.ValidationException;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** The four endpoints of the contract. No SQL and no business rules here. */
@RestController
@RequestMapping("/items")
public class ItemController {

  private static final Pattern DIGITS = Pattern.compile("[0-9]+");

  private final GetItem getItem;
  private final CreateItem createItem;
  private final ReplaceItem replaceItem;
  private final DeleteItem deleteItem;

  public ItemController(GetItem getItem, CreateItem createItem, ReplaceItem replaceItem, DeleteItem deleteItem) {
    this.getItem = getItem;
    this.createItem = createItem;
    this.replaceItem = replaceItem;
    this.deleteItem = deleteItem;
  }

  /** Decimal digits only (no sign, exponent or fraction) that fit a long; range rules are the domain's. */
  private static long parseId(String raw) {
    if (!DIGITS.matcher(raw).matches()) {
      throw new ValidationException("invalid id");
    }
    try {
      return Long.parseLong(raw);
    } catch (NumberFormatException overflow) {
      throw new ValidationException("invalid id");
    }
  }

  @GetMapping("/{id}")
  ResponseEntity<ItemResponse> get(@PathVariable String id) {
    return ResponseEntity.ok(ItemResponse.from(getItem.execute(parseId(id))));
  }

  @PostMapping
  ResponseEntity<ItemResponse> create(@RequestBody(required = false) byte[] body) {
    Item item = createItem.execute(ItemRequestParser.parse(body));
    return ResponseEntity.status(HttpStatus.CREATED)
        .header("Location", "/items/" + item.id())
        .body(ItemResponse.from(item));
  }

  @PutMapping("/{id}")
  ResponseEntity<ItemResponse> replace(@PathVariable String id, @RequestBody(required = false) byte[] body) {
    long itemId = parseId(id);
    return ResponseEntity.ok(ItemResponse.from(replaceItem.execute(itemId, ItemRequestParser.parse(body))));
  }

  @DeleteMapping("/{id}")
  ResponseEntity<Void> delete(@PathVariable String id) {
    deleteItem.execute(parseId(id));
    return ResponseEntity.noContent().build();
  }
}
