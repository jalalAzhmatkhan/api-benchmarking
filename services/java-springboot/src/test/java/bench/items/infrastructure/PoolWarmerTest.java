package bench.items.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.util.concurrent.CompletionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

class PoolWarmerTest {

  @Test
  @EnabledIfEnvironmentVariable(named = "DATABASE_URL", matches = ".+")
  void opensExactlyTheRequestedNumberOfConnections() {
    DatabaseSettings s = DatabaseSettings.parse(System.getenv("DATABASE_URL"), 3);
    HikariConfig config = new HikariConfig();
    config.setJdbcUrl(s.jdbcUrl());
    config.setUsername(s.user());
    config.setPassword(s.password());
    config.setMaximumPoolSize(3);
    config.setMinimumIdle(3);
    try (HikariDataSource ds = new HikariDataSource(config)) {
      PoolWarmer.warm(ds, 3);
      assertThat(ds.getHikariPoolMXBean().getTotalConnections()).isEqualTo(3);
    }
  }

  @Test
  void aFailingDatabaseFailsTheWarmUp() {
    DriverManagerDataSource unreachable =
        new DriverManagerDataSource("jdbc:postgresql://127.0.0.1:1/bench", "bench", "bench");
    assertThatThrownBy(() -> PoolWarmer.warm(unreachable, 2)).isInstanceOf(CompletionException.class);
  }
}
