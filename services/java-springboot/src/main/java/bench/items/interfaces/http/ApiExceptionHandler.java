package bench.items.interfaces.http;

import bench.items.domain.NotFoundException;
import bench.items.domain.ValidationException;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** Maps domain errors to the contract's error body. Internal details are never exposed. */
@RestControllerAdvice
public class ApiExceptionHandler {

  record ErrorDetail(@JsonProperty("code") String code, @JsonProperty("message") String message) {}

  record ErrorBody(@JsonProperty("error") ErrorDetail error) {}

  private static ResponseEntity<ErrorBody> body(HttpStatus status, String code, String message) {
    return ResponseEntity.status(status).body(new ErrorBody(new ErrorDetail(code, message)));
  }

  @ExceptionHandler(ValidationException.class)
  ResponseEntity<ErrorBody> validation(ValidationException e) {
    return body(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", e.getMessage());
  }

  @ExceptionHandler(NotFoundException.class)
  ResponseEntity<ErrorBody> notFound(NotFoundException e) {
    return body(HttpStatus.NOT_FOUND, "NOT_FOUND", e.getMessage());
  }

  /** Unexpected failures (database errors, bugs). Framework errors such as 405 keep their defaults. */
  @ExceptionHandler(RuntimeException.class)
  ResponseEntity<ErrorBody> unexpected(RuntimeException e) {
    return body(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "internal error");
  }
}
