using Items.Infrastructure;
using Npgsql;

namespace Items.Tests;

public class DatabaseSettingsTests
{
    private static NpgsqlConnectionStringBuilder Builder(string url, int pool = 10) =>
        new(DatabaseSettings.Parse(url, pool).ConnectionString);

    [Fact]
    public void ParsesTheContractUrlAndAppliesThePoolSpec()
    {
        NpgsqlConnectionStringBuilder b = Builder("postgres://bench:s3cret@db.internal:6432/items", 10);
        Assert.Equal(("db.internal", 6432, "items", "bench", "s3cret"), (b.Host, b.Port, b.Database, b.Username, b.Password));
        Assert.Equal((10, 10, 5, 5, 600, 0), (b.MinPoolSize, b.MaxPoolSize, b.Timeout, b.CommandTimeout, b.ConnectionIdleLifetime, b.ConnectionLifetime));
        Assert.Equal(0, b.MaxAutoPrepare); // driver default kept (D-06)
    }

    [Fact]
    public void DefaultsPortAndAcceptsThePostgresqlScheme() =>
        Assert.Equal(5432, Builder("postgresql://bench:bench@127.0.0.1/bench").Port);

    [Fact]
    public void PasswordsMayContainColonsOrBeMissingAndAreUnescaped()
    {
        Assert.Equal("a:b", Builder("postgres://u:a:b@h/db").Password);
        Assert.Equal("p@ss", Builder("postgres://u:p%40ss@h/db").Password);
        NpgsqlConnectionStringBuilder none = Builder("postgres://u@h/db");
        Assert.Equal("u", none.Username);
        Assert.True(string.IsNullOrEmpty(none.Password)); // Npgsql treats an empty password as unset
    }

    [Theory]
    [InlineData("mysql://u:p@h/db")]
    [InlineData("no-scheme")]
    [InlineData("postgres://u:p@h")]
    [InlineData("postgres://u:p@h/")]
    [InlineData("postgres:///db")]
    public void RejectsBadUrls(string url) => Assert.Throws<ArgumentException>(() => DatabaseSettings.Parse(url, 10));

    [Fact]
    public void RejectsAnInvalidPoolSize() => Assert.Throws<ArgumentException>(() => DatabaseSettings.Parse("postgres://u:p@h/db", 0));
}
