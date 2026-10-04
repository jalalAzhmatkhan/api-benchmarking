using Items.Domain;
using Npgsql;

namespace Items.Infrastructure;

/// <summary>PostgreSQL repository: raw SQL through Npgsql, no ORM.</summary>
public sealed class NpgsqlItemRepository(NpgsqlDataSource dataSource) : IItemRepository
{
    // Canonical statements (Documentation/specs/database-schema.md §2), shared verbatim by all stacks.
    internal const string SelectSql =
        "SELECT id, name, description, price_cents, quantity, created_at, updated_at FROM items WHERE id = $1";

    internal const string InsertSql =
        "INSERT INTO items (name, description, price_cents, quantity) VALUES ($1, $2, $3, $4) " +
        "RETURNING id, name, description, price_cents, quantity, created_at, updated_at";

    internal const string UpdateSql =
        "UPDATE items SET name = $2, description = $3, price_cents = $4, quantity = $5, updated_at = now() " +
        "WHERE id = $1 RETURNING id, name, description, price_cents, quantity, created_at, updated_at";

    internal const string DeleteSql = "DELETE FROM items WHERE id = $1";

    private static Item Map(NpgsqlDataReader r) => new(
        r.GetInt64(0),
        r.GetString(1),
        r.IsDBNull(2) ? null : r.GetString(2),
        r.GetInt64(3),
        r.GetInt32(4),
        r.GetDateTime(5),
        r.GetDateTime(6));

    private static NpgsqlParameter P(object? value) => new() { Value = value ?? DBNull.Value };

    private async Task<Item> QuerySingleAsync(string sql, NpgsqlParameter[] parameters, CancellationToken ct)
    {
        await using NpgsqlCommand command = dataSource.CreateCommand(sql);
        command.Parameters.AddRange(parameters);
        await using NpgsqlDataReader reader = await command.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : throw new NotFoundException();
    }

    public Task<Item> GetAsync(long id, CancellationToken ct) => QuerySingleAsync(SelectSql, [P(id)], ct);

    public Task<Item> CreateAsync(ItemInput input, CancellationToken ct) =>
        QuerySingleAsync(InsertSql, [P(input.Name), P(input.Description), P(input.PriceCents), P((int)input.Quantity)], ct);

    public Task<Item> ReplaceAsync(long id, ItemInput input, CancellationToken ct) =>
        QuerySingleAsync(UpdateSql, [P(id), P(input.Name), P(input.Description), P(input.PriceCents), P((int)input.Quantity)], ct);

    public async Task DeleteAsync(long id, CancellationToken ct)
    {
        await using NpgsqlCommand command = dataSource.CreateCommand(DeleteSql);
        command.Parameters.Add(P(id));
        if (await command.ExecuteNonQueryAsync(ct) == 0)
        {
            throw new NotFoundException();
        }
    }
}
