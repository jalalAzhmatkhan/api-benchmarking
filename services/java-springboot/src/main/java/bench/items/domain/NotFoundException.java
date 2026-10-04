package bench.items.domain;

/** The item does not exist (maps to 404 NOT_FOUND). */
public class NotFoundException extends DomainException {

  public NotFoundException() {
    super("item not found");
  }
}
