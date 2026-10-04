package bench.items.domain;

/** A request violates a contract rule (maps to 400 VALIDATION_ERROR). */
public class ValidationException extends DomainException {

  public ValidationException(String message) {
    super(message);
  }
}
