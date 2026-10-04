package bench.items.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import bench.items.domain.Item;
import bench.items.domain.ItemInput;
import bench.items.domain.NotFoundException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/** Runs against the real PostgreSQL (CI provides DATABASE_URL); the repository is only SQL. */
@EnabledIfEnvironmentVariable(named = "DATABASE_URL", matches = ".+")
class JdbcItemRepositoryTest {

  private static JdbcItemRepository repository() {
    DatabaseSettings s = DatabaseSettings.parse(System.getenv("DATABASE_URL"), 1);
    return new JdbcItemRepository(JdbcClient.create(new DriverManagerDataSource(s.jdbcUrl(), s.user(), s.password())));
  }

  @Test
  void crudRoundTrip() {
    JdbcItemRepository repo = repository();
    Item created = repo.create(new ItemInput("java-crud", "desc", 1999, 5));
    assertThat(created.id()).isPositive();
    assertThat(created.name()).isEqualTo("java-crud");
    assertThat(created.description()).isEqualTo("desc");
    assertThat(created.priceCents()).isEqualTo(1999);
    assertThat(created.quantity()).isEqualTo(5);
    assertThat(created.updatedAt()).isAfterOrEqualTo(created.createdAt());
    assertThat(repo.get(created.id())).isEqualTo(created);

    ItemInput next = new ItemInput("java-crud-2", null, 7, 0);
    Item replaced = repo.replace(created.id(), next);
    assertThat(replaced.id()).isEqualTo(created.id());
    assertThat(replaced.name()).isEqualTo("java-crud-2");
    assertThat(replaced.description()).isNull();
    assertThat(replaced.createdAt()).isEqualTo(created.createdAt());
    assertThat(replaced.updatedAt()).isAfterOrEqualTo(created.updatedAt());
    assertThat(repo.get(created.id())).isEqualTo(replaced);

    repo.delete(created.id());
    assertThatThrownBy(() -> repo.get(created.id())).isInstanceOf(NotFoundException.class);
    assertThatThrownBy(() -> repo.delete(created.id())).isInstanceOf(NotFoundException.class);
    assertThatThrownBy(() -> repo.replace(created.id(), next)).isInstanceOf(NotFoundException.class);
  }

  @Test
  void unknownIdIsNotFound() {
    assertThatThrownBy(() -> repository().get(ItemInput.MAX_ID)).isInstanceOf(NotFoundException.class);
  }
}
