package bench.items.domain;

/** Base type of errors raised by the domain. */
public abstract class DomainException extends RuntimeException {

  protected DomainException(String message) {
    super(message);
  }
}
