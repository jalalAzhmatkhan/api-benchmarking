package bench.items.infrastructure;

import java.net.URI;
import java.util.Objects;

/**
 * Connection settings from the shared env contract (contract/README.md): {@code DATABASE_URL}
 * ({@code postgres://user:password@host:port/db}) and {@code DB_POOL_SIZE}.
 */
public record DatabaseSettings(String jdbcUrl, String user, String password, int poolSize) {

  public static DatabaseSettings parse(String databaseUrl, int poolSize) {
    if (poolSize < 1) {
      throw new IllegalArgumentException("invalid DB_POOL_SIZE " + poolSize);
    }
    URI uri = URI.create(databaseUrl);
    String scheme = Objects.requireNonNullElse(uri.getScheme(), "");
    if (!scheme.equals("postgres") && !scheme.equals("postgresql")) {
      throw new IllegalArgumentException("DATABASE_URL must start with postgres://");
    }
    // a hierarchical URI with a host always has a non-null path
    String path = uri.getHost() == null ? "" : uri.getPath();
    if (path.length() < 2) {
      throw new IllegalArgumentException("DATABASE_URL needs a host and a database name");
    }
    String[] credentials = Objects.requireNonNullElse(uri.getUserInfo(), "").split(":", 2);
    String password = credentials.length > 1 ? credentials[1] : "";
    int port = uri.getPort() > 0 ? uri.getPort() : 5432;
    String jdbcUrl = "jdbc:postgresql://" + uri.getHost() + ":" + port + path;
    return new DatabaseSettings(jdbcUrl, credentials[0], password, poolSize);
  }
}
