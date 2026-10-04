package bench.items;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Bare entrypoint (excluded from coverage, see COVERAGE_EXCLUSIONS.md). */
@SpringBootApplication
public class ItemsApplication {

  public static void main(String[] args) {
    SpringApplication.run(ItemsApplication.class, args);
  }
}
