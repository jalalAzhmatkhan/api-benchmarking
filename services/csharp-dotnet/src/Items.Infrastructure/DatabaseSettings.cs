using Npgsql;

namespace Items.Infrastructure;

/// <summary>
/// Connection settings from the shared env contract (contract/README.md): <c>DATABASE_URL</c>
/// (<c>postgres://user:password@host:port/db</c>) and <c>DB_POOL_SIZE</c>. The pool follows
/// Documentation/specs/connection-pooling.md: fixed size (min = max), 5 s timeouts, 10 min idle,
/// no connection lifetime limit. Npgsql defaults otherwise (auto-prepare off, decision D-06).
/// </summary>
public sealed record DatabaseSettings(string ConnectionString, int PoolSize)
{
    public static DatabaseSettings Parse(string databaseUrl, int poolSize)
    {
        if (poolSize < 1)
        {
            throw new ArgumentException($"invalid DB_POOL_SIZE {poolSize}");
        }

        if (!Uri.TryCreate(databaseUrl, UriKind.Absolute, out Uri? uri) || uri.Scheme is not ("postgres" or "postgresql"))
        {
            throw new ArgumentException("DATABASE_URL must start with postgres://");
        }

        string database = uri.AbsolutePath.TrimStart('/');
        if (uri.Host.Length == 0 || database.Length == 0)
        {
            throw new ArgumentException("DATABASE_URL needs a host and a database name");
        }

        string[] credentials = Uri.UnescapeDataString(uri.UserInfo).Split(':', 2);
        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = uri.Host,
            Port = uri.Port > 0 ? uri.Port : 5432,
            Database = database,
            Username = credentials[0],
            Password = credentials.Length > 1 ? credentials[1] : "",
            MinPoolSize = poolSize,
            MaxPoolSize = poolSize,
            Timeout = 5,
            CommandTimeout = 5,
            ConnectionIdleLifetime = 600,
            ConnectionLifetime = 0,
        };
        return new DatabaseSettings(builder.ConnectionString, poolSize);
    }
}
