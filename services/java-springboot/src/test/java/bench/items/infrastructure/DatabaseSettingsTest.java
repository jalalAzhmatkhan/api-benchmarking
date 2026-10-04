package bench.items.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class DatabaseSettingsTest {

  @Test
  void parsesTheContractUrl() {
    assertThat(DatabaseSettings.parse("postgres://bench:s3cret@db.internal:6432/items", 10))
        .isEqualTo(new DatabaseSettings("jdbc:postgresql://db.internal:6432/items", "bench", "s3cret", 10));
  }

  @Test
  void defaultsPortAndAcceptsThePostgresqlScheme() {
    assertThat(DatabaseSettings.parse("postgresql://bench:bench@127.0.0.1/bench", 4).jdbcUrl())
        .isEqualTo("jdbc:postgresql://127.0.0.1:5432/bench");
  }

  @Test
  void passwordsMayContainColonsAndBeMissing() {
    assertThat(DatabaseSettings.parse("postgres://u:a:b@h/db", 1).password()).isEqualTo("a:b");
    DatabaseSettings noPassword = DatabaseSettings.parse("postgres://u@h/db", 1);
    assertThat(noPassword.user()).isEqualTo("u");
    assertThat(noPassword.password()).isEmpty();
    assertThat(DatabaseSettings.parse("postgres://h/db", 1).user()).isEmpty();
  }

  @Test
  void rejectsBadInput() {
    for (String url : new String[] {"mysql://u:p@h/db", "no-scheme", "postgres://u:p@h", "postgres://u:p@h/", "postgres:///db"}) {
      assertThatThrownBy(() -> DatabaseSettings.parse(url, 10)).as(url).isInstanceOf(IllegalArgumentException.class);
    }
    assertThatThrownBy(() -> DatabaseSettings.parse("postgres://u:p@h/db", 0)).isInstanceOf(IllegalArgumentException.class);
  }
}
