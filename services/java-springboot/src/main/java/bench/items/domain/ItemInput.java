package bench.items.domain;

/**
 * The payload for creating or replacing an item. {@code description} may be null.
 * Lengths are counted in Unicode code points (Documentation/specs/api-contract.md).
 */
public record ItemInput(String name, String description, long priceCents, long quantity) {

  public static final long MAX_ID = 9_007_199_254_740_991L;
  public static final long MAX_PRICE_CENTS = 9_007_199_254_740_991L;
  public static final long MAX_QUANTITY = 2_147_483_647L;
  public static final int MAX_NAME_LENGTH = 100;
  public static final int MAX_DESCRIPTION_LENGTH = 1000;

  /** Checks the contract's field rules. */
  public void validate() {
    int nameLength = name.codePointCount(0, name.length());
    if (nameLength < 1 || nameLength > MAX_NAME_LENGTH) {
      throw new ValidationException("name must be 1-100 characters");
    }
    if (description != null && description.codePointCount(0, description.length()) > MAX_DESCRIPTION_LENGTH) {
      throw new ValidationException("description must be at most 1000 characters");
    }
    if (priceCents < 0 || priceCents > MAX_PRICE_CENTS) {
      throw new ValidationException("price_cents must be an integer in 0..9007199254740991");
    }
    if (quantity < 0 || quantity > MAX_QUANTITY) {
      throw new ValidationException("quantity must be an integer in 0..2147483647");
    }
  }

  /** Checks that {@code id} is within 1..MAX_ID. */
  public static void validateId(long id) {
    if (id < 1 || id > MAX_ID) {
      throw new ValidationException("invalid id");
    }
  }
}
