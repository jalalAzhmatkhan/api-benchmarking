package bench.items.interfaces.http;

import bench.items.domain.ItemInput;
import bench.items.domain.ValidationException;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Parses the request body strictly: syntax errors, wrong JSON types (a string where a number is
 * expected, a fraction where an integer is expected, a number above 64 bits) and missing required
 * fields are validation errors; unknown fields are ignored. Range rules live in the domain.
 */
final class ItemRequestParser {

  private static final JsonMapper MAPPER = JsonMapper.builder().build();

  private ItemRequestParser() {}

  static ItemInput parse(byte[] body) {
    JsonNode root;
    try {
      root = MAPPER.readTree(body == null ? new byte[0] : body);
    } catch (JacksonException e) {
      throw new ValidationException("malformed JSON body");
    }
    if (!root.isObject()) {
      throw new ValidationException("body must be a JSON object");
    }
    return new ItemInput(
        requiredString(root, "name"),
        optionalString(root, "description"),
        requiredLong(root, "price_cents"),
        requiredLong(root, "quantity"));
  }

  private static String requiredString(JsonNode root, String field) {
    JsonNode value = root.get(field);
    if (value == null || !value.isString()) {
      throw new ValidationException(field + " is required and must be a string");
    }
    return value.stringValue();
  }

  private static String optionalString(JsonNode root, String field) {
    JsonNode value = root.get(field);
    if (value == null || value.isNull()) {
      return null;
    }
    if (!value.isString()) {
      throw new ValidationException(field + " must be a string or null");
    }
    return value.stringValue();
  }

  private static long requiredLong(JsonNode root, String field) {
    JsonNode value = root.get(field);
    if (value == null || !value.isIntegralNumber() || !value.canConvertToLong()) {
      throw new ValidationException(field + " is required and must be an integer");
    }
    return value.longValue();
  }
}
