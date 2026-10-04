using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using Items.Api;
using Items.Domain;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;

namespace Items.Tests;

public class ItemEndpointsTests
{
    private const string Valid = """{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}""";
    private static readonly DateTime Ts = new(2026, 10, 3, 10, 0, 0, DateTimeKind.Utc);

    /// <summary>Canned repository: every call fails with the supplied exception, if any.</summary>
    private sealed class FakeRepository(Exception? failure) : IItemRepository
    {
        private void MaybeFail()
        {
            if (failure is not null)
            {
                throw failure;
            }
        }

        private static Item Item(long id, string? description) => new(id, "Widget", description, 1999, 5, Ts, Ts);

        public Task<Item> GetAsync(long id, CancellationToken ct) { MaybeFail(); return Task.FromResult(Item(id, null)); }
        public Task<Item> CreateAsync(ItemInput input, CancellationToken ct) { MaybeFail(); return Task.FromResult(Item(100_001, "Blue")); }
        public Task<Item> ReplaceAsync(long id, ItemInput input, CancellationToken ct) { MaybeFail(); return Task.FromResult(Item(id, "Red")); }
        public Task DeleteAsync(long id, CancellationToken ct) { MaybeFail(); return Task.CompletedTask; }
    }

    private static async Task<(WebApplication App, HttpClient Client)> StartAsync(Exception? failure = null)
    {
        WebApplicationBuilder builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        builder.Services.AddSingleton<IItemRepository>(new FakeRepository(failure));
        builder.Services.AddItemUseCases();
        WebApplication app = builder.Build();
        app.MapItemEndpoints();
        await app.StartAsync();
        return (app, app.GetTestClient());
    }

    private static Task<HttpResponseMessage> Send(HttpClient client, string method, string path, string? body = null) =>
        client.SendAsync(new HttpRequestMessage(new HttpMethod(method), path)
        {
            Content = body is null ? null : new StringContent(body, Encoding.UTF8, "application/json"),
        });

    private static async Task<string> ErrorCode(HttpResponseMessage response)
    {
        string json = await response.Content.ReadAsStringAsync();
        Assert.Matches("""^\{"error":\{"code":"[A-Z_]+","message":"[^"]+"\}\}$""", json);
        return Regex.Match(json, "\"code\":\"([A-Z_]+)\"").Groups[1].Value;
    }

    [Fact]
    public async Task GetReturnsTheItemWithAnExplicitNullDescription()
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            HttpResponseMessage r = await Send(client, "GET", "/items/7");
            Assert.Equal(HttpStatusCode.OK, r.StatusCode);
            Assert.StartsWith("application/json", r.Content.Headers.ContentType!.ToString());
            Assert.Equal(
                """{"id":7,"name":"Widget","description":null,"price_cents":1999,"quantity":5,"created_at":"2026-10-03T10:00:00Z","updated_at":"2026-10-03T10:00:00Z"}""",
                await r.Content.ReadAsStringAsync());
            Assert.Null(r.Headers.ETag);
            Assert.Null(r.Headers.CacheControl);
            Assert.Null(r.Content.Headers.LastModified);
            Assert.Empty(r.Content.Headers.ContentEncoding);
        }
    }

    [Theory]
    [InlineData("abc")]
    [InlineData("0")]
    [InlineData("-1")]
    [InlineData("1.5")]
    [InlineData("1e3")]
    [InlineData("+5")]
    [InlineData("9007199254740992")]
    [InlineData("99999999999999999999")]
    public async Task InvalidIdsAre400(string id)
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            foreach (string method in new[] { "GET", "DELETE", "PUT" })
            {
                HttpResponseMessage r = await Send(client, method, "/items/" + id, method == "PUT" ? Valid : null);
                Assert.Equal(HttpStatusCode.BadRequest, r.StatusCode);
                Assert.Equal("VALIDATION_ERROR", await ErrorCode(r));
            }
        }
    }

    [Fact]
    public async Task CreateReturns201WithLocation()
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            HttpResponseMessage r = await Send(client, "POST", "/items", Valid);
            Assert.Equal(HttpStatusCode.Created, r.StatusCode);
            Assert.Equal("/items/100001", r.Headers.Location!.OriginalString);
            string body = await r.Content.ReadAsStringAsync();
            Assert.Contains("\"id\":100001", body);
            Assert.Contains("\"description\":\"Blue\"", body);
        }
    }

    [Fact]
    public async Task InvalidBodiesAre400OnPostAndPut()
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            string[] bodies =
            [
                """{"name":""", "[]", """{"price_cents":1,"quantity":1}""",
                """{"name":"","price_cents":1,"quantity":1}""",
                """{"name":"n","price_cents":-1,"quantity":1}""",
                """{"name":"n","price_cents":1,"quantity":2147483648}""",
            ];
            foreach (string body in bodies)
            {
                foreach ((string method, string path) in new[] { ("POST", "/items"), ("PUT", "/items/5") })
                {
                    HttpResponseMessage r = await Send(client, method, path, body);
                    Assert.Equal(HttpStatusCode.BadRequest, r.StatusCode);
                    Assert.Equal("VALIDATION_ERROR", await ErrorCode(r));
                }
            }

            Assert.Equal(HttpStatusCode.BadRequest, (await Send(client, "POST", "/items")).StatusCode); // no body
            Assert.Equal(HttpStatusCode.BadRequest, (await Send(client, "PUT", "/items/5")).StatusCode);
        }
    }

    [Fact]
    public async Task ReplaceAndDelete()
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            HttpResponseMessage put = await Send(client, "PUT", "/items/5", Valid);
            Assert.Equal(HttpStatusCode.OK, put.StatusCode);
            string body = await put.Content.ReadAsStringAsync();
            Assert.Contains("\"id\":5", body);
            Assert.Contains("\"description\":\"Red\"", body);

            HttpResponseMessage del = await Send(client, "DELETE", "/items/5");
            Assert.Equal(HttpStatusCode.NoContent, del.StatusCode);
            Assert.Equal("", await del.Content.ReadAsStringAsync());
        }
    }

    [Theory]
    [InlineData(true, 404, "NOT_FOUND")]
    [InlineData(false, 500, "INTERNAL_ERROR")]
    public async Task ErrorMappingAndNoLeaks(bool notFound, int status, string code)
    {
        Exception failure = notFound ? new NotFoundException() : new InvalidOperationException("secret connection string");
        var (app, client) = await StartAsync(failure);
        await using (app)
        {
            foreach ((string method, string path, string? body) in new[]
                     {
                         ("GET", "/items/1", (string?)null), ("POST", "/items", Valid), ("PUT", "/items/1", Valid), ("DELETE", "/items/1", null),
                     })
            {
                HttpResponseMessage r = await Send(client, method, path, body);
                Assert.Equal(status, (int)r.StatusCode);
                Assert.Equal(code, await ErrorCode(r));
                Assert.DoesNotContain("secret", await r.Content.ReadAsStringAsync());
            }
        }
    }

    [Fact]
    public async Task OnlyTheContractRoutesExist()
    {
        var (app, client) = await StartAsync();
        await using (app)
        {
            Assert.Equal(HttpStatusCode.MethodNotAllowed, (await Send(client, "GET", "/items")).StatusCode);
            Assert.Equal(HttpStatusCode.MethodNotAllowed, (await Send(client, "PATCH", "/items/1")).StatusCode);
            Assert.Equal(HttpStatusCode.NotFound, (await Send(client, "GET", "/health")).StatusCode);
        }
    }
}
