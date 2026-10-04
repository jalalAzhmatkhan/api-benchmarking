using Items.Application;
using Items.Domain;
using Items.Infrastructure;
using Npgsql;

namespace Items.Api;

/// <summary>Composition root: settings → data source → repository → use cases → endpoints.</summary>
public static class AppComposition
{
    public const string DefaultDatabaseUrl = "postgres://bench:bench@127.0.0.1:5432/bench";

    /// <summary>Registers the four use cases over whatever <see cref="IItemRepository"/> is registered.</summary>
    public static IServiceCollection AddItemUseCases(this IServiceCollection services) => services
        .AddSingleton<GetItem>()
        .AddSingleton<CreateItem>()
        .AddSingleton<ReplaceItem>()
        .AddSingleton<DeleteItem>();

    private static string Setting(IConfiguration configuration, string key, string fallback) =>
        string.IsNullOrEmpty(configuration[key]) ? fallback : configuration[key]!;

    public static WebApplication Build(string[] args)
    {
        WebApplicationBuilder builder = WebApplication.CreateBuilder(args);
        DatabaseSettings settings = DatabaseSettings.Parse(
            Setting(builder.Configuration, "DATABASE_URL", DefaultDatabaseUrl),
            int.Parse(Setting(builder.Configuration, "DB_POOL_SIZE", "10")));
        builder.WebHost.UseUrls($"http://0.0.0.0:{Setting(builder.Configuration, "PORT", "8080")}");

        builder.Services.AddSingleton(settings);
        builder.Services.AddSingleton(_ => NpgsqlDataSource.Create(settings.ConnectionString));
        builder.Services.AddSingleton<IItemRepository, NpgsqlItemRepository>();
        builder.Services.AddItemUseCases();

        WebApplication app = builder.Build();
        app.MapItemEndpoints();
        return app;
    }

    /// <summary>Opens the whole pool before the server accepts traffic.</summary>
    public static Task WarmPoolAsync(WebApplication app) =>
        PoolWarmer.WarmAsync(
            app.Services.GetRequiredService<NpgsqlDataSource>(),
            app.Services.GetRequiredService<DatabaseSettings>().PoolSize);
}
