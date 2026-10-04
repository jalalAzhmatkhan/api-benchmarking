using System.Net;
using System.Text;
using Items.Domain;
using Items.Infrastructure;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;

namespace Items.Tests;

/// <summary>Database-backed tests (CI provides DATABASE_URL, the seeded dev PostgreSQL).</summary>
public class DatabaseTests
{
    private static NpgsqlDataSource DataSource(int pool = 4) =>
        NpgsqlDataSource.Create(DatabaseSettings.Parse(DbFactAttribute.Url!, pool).ConnectionString);

    [DbFact]
    public async Task CrudRoundTrip()
    {
        await using NpgsqlDataSource ds = DataSource();
        var repo = new NpgsqlItemRepository(ds);
        var ct = CancellationToken.None;

        Item created = await repo.CreateAsync(new ItemInput("dotnet-crud", "desc", 1999, 5), ct);
        Assert.True(created.Id > 0);
        Assert.Equal(("dotnet-crud", "desc", 1999L, 5), (created.Name, created.Description, created.PriceCents, created.Quantity));
        Assert.True(created.UpdatedAt >= created.CreatedAt);
        Assert.Equal(created, await repo.GetAsync(created.Id, ct));

        var next = new ItemInput("dotnet-crud-2", null, 7, 0);
        Item replaced = await repo.ReplaceAsync(created.Id, next, ct);
        Assert.Equal((created.Id, "dotnet-crud-2", (string?)null), (replaced.Id, replaced.Name, replaced.Description));
        Assert.Equal(created.CreatedAt, replaced.CreatedAt);
        Assert.Equal(replaced, await repo.GetAsync(created.Id, ct));

        await repo.DeleteAsync(created.Id, ct);
        await Assert.ThrowsAsync<NotFoundException>(() => repo.GetAsync(created.Id, ct));
        await Assert.ThrowsAsync<NotFoundException>(() => repo.DeleteAsync(created.Id, ct));
        await Assert.ThrowsAsync<NotFoundException>(() => repo.ReplaceAsync(created.Id, next, ct));
    }

    [DbFact]
    public async Task PoolWarmerOpensTheRequestedConnections()
    {
        await using NpgsqlDataSource ds = DataSource(3);
        await PoolWarmer.WarmAsync(ds, 3);

        // Count the pool's connections from the server side, through a separate one-connection pool.
        await using NpgsqlDataSource observer = DataSource(1);
        long count = 0;
        for (int attempt = 0; attempt < 50 && count != 3; attempt++)
        {
            await using NpgsqlCommand command = observer.CreateCommand(
                "SELECT count(*) FROM pg_stat_activity WHERE usename = 'bench' AND backend_type = 'client backend' AND pid <> pg_backend_pid()");
            count = (long)(await command.ExecuteScalarAsync())!;
            await Task.Delay(100);
        }

        Assert.Equal(3, count);
    }

    private static async Task<HttpResponseMessage> Call(HttpClient client, string method, string path, string? body = null) =>
        await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path)
        {
            Content = body is null ? null : new StringContent(body, Encoding.UTF8, "application/json"),
        });

    [DbFact]
    public async Task TheWholeServiceWorksWithExplicitSettings()
    {
        await using var factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b => b.UseSetting("DB_POOL_SIZE", "3"));
        using HttpClient client = factory.CreateClient();
        Assert.Equal(3, factory.Services.GetRequiredService<DatabaseSettings>().PoolSize);

        HttpResponseMessage seeded = await Call(client, "GET", "/items/1");
        Assert.Equal(HttpStatusCode.OK, seeded.StatusCode);
        Assert.Contains("\"name\":\"item-1\"", await seeded.Content.ReadAsStringAsync());

        HttpResponseMessage created = await Call(client, "POST", "/items", """{"name":"aspnet","price_cents":1,"quantity":1}""");
        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        string location = created.Headers.Location!.OriginalString;
        Assert.Equal(HttpStatusCode.OK, (await Call(client, "PUT", location, """{"name":"aspnet2","description":"d","price_cents":2,"quantity":2}""")).StatusCode);
        Assert.Equal(HttpStatusCode.NoContent, (await Call(client, "DELETE", location)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await Call(client, "GET", location)).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Call(client, "GET", "/items/abc")).StatusCode);
    }

    [DbFact]
    public async Task EmptySettingsFallBackToTheDefaults()
    {
        // Same database as the CI default (deploy/compose.dev.yaml); pool size falls back to 10.
        await using var factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        {
            b.UseSetting("DATABASE_URL", "");
            b.UseSetting("DB_POOL_SIZE", "");
            b.UseSetting("PORT", "");
        });
        using HttpClient client = factory.CreateClient();
        Assert.Equal(10, factory.Services.GetRequiredService<DatabaseSettings>().PoolSize);
        Assert.Equal(HttpStatusCode.OK, (await Call(client, "GET", "/items/1")).StatusCode);
    }
}
