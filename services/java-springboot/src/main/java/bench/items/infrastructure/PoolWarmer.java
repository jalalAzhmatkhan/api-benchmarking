package bench.items.infrastructure;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import javax.sql.DataSource;
import org.springframework.jdbc.core.simple.JdbcClient;

/**
 * Opens {@code size} pool connections before the service accepts traffic, by running {@code size}
 * overlapping queries (forces {@code size} distinct connections). The first measured requests then
 * do not pay for connection setup.
 */
public final class PoolWarmer {

  private PoolWarmer() {}

  public static void warm(DataSource dataSource, int size) {
    JdbcClient jdbc = JdbcClient.create(dataSource);
    try (var executor = Executors.newFixedThreadPool(size)) {
      CompletableFuture<?>[] tasks = new CompletableFuture<?>[size];
      for (int i = 0; i < size; i++) {
        tasks[i] = CompletableFuture.runAsync(() -> jdbc.sql("SELECT pg_sleep(0.05)").query().listOfRows(), executor);
      }
      CompletableFuture.allOf(tasks).join();
    }
  }
}
