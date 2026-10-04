using Npgsql;

namespace Items.Infrastructure;

/// <summary>
/// Opens <c>size</c> pool connections before the service accepts traffic, by running <c>size</c>
/// overlapping queries (forces <c>size</c> distinct connections). The first measured requests then
/// do not pay for connection setup.
/// </summary>
public static class PoolWarmer
{
    public static async Task WarmAsync(NpgsqlDataSource dataSource, int size, CancellationToken ct = default)
    {
        static async Task RunOne(NpgsqlDataSource ds, CancellationToken ct)
        {
            using NpgsqlCommand command = ds.CreateCommand("SELECT pg_sleep(0.05)");
            await command.ExecuteNonQueryAsync(ct);
        }

        await Task.WhenAll(Enumerable.Range(0, size).Select(_ => RunOne(dataSource, ct)));
    }
}
