package bench.items;

import bench.items.application.CreateItem;
import bench.items.application.DeleteItem;
import bench.items.application.GetItem;
import bench.items.application.ReplaceItem;
import bench.items.domain.ItemRepository;
import bench.items.infrastructure.DatabaseSettings;
import bench.items.infrastructure.JdbcItemRepository;
import bench.items.infrastructure.PoolWarmer;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.simple.JdbcClient;

/** Composition root: settings → pool → repository → use cases (the controller is component-scanned). */
@Configuration(proxyBeanMethods = false)
public class AppConfig {

  /**
   * Fixed-size, pre-warmed HikariCP pool (Documentation/specs/connection-pooling.md): min = max =
   * DB_POOL_SIZE, 5 s acquire timeout, 10 min idle / 30 min lifetime (irrelevant at min = max).
   * Everything else is the Boot/Hikari default (decision D-06).
   */
  @Bean
  DataSource dataSource(
      @Value("${DATABASE_URL:postgres://bench:bench@127.0.0.1:5432/bench}") String databaseUrl,
      @Value("${DB_POOL_SIZE:10}") int poolSize) {
    DatabaseSettings settings = DatabaseSettings.parse(databaseUrl, poolSize);
    HikariConfig config = new HikariConfig();
    config.setJdbcUrl(settings.jdbcUrl());
    config.setUsername(settings.user());
    config.setPassword(settings.password());
    config.setMaximumPoolSize(settings.poolSize());
    config.setMinimumIdle(settings.poolSize());
    config.setConnectionTimeout(5_000);
    config.setIdleTimeout(600_000);
    config.setMaxLifetime(1_800_000);
    config.setInitializationFailTimeout(1);
    HikariDataSource dataSource = new HikariDataSource(config);
    PoolWarmer.warm(dataSource, settings.poolSize());
    return dataSource;
  }

  @Bean
  ItemRepository itemRepository(DataSource dataSource) {
    return new JdbcItemRepository(JdbcClient.create(dataSource));
  }

  @Bean
  GetItem getItem(ItemRepository repository) {
    return new GetItem(repository);
  }

  @Bean
  CreateItem createItem(ItemRepository repository) {
    return new CreateItem(repository);
  }

  @Bean
  ReplaceItem replaceItem(ItemRepository repository) {
    return new ReplaceItem(repository);
  }

  @Bean
  DeleteItem deleteItem(ItemRepository repository) {
    return new DeleteItem(repository);
  }
}
