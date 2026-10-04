namespace Items.Tests;

/// <summary>A fact that runs only when DATABASE_URL is set (CI provides the seeded dev PostgreSQL).</summary>
public sealed class DbFactAttribute : FactAttribute
{
    public DbFactAttribute()
    {
        if (string.IsNullOrEmpty(Url))
        {
            Skip = "DATABASE_URL not set";
        }
    }

    public static string? Url => Environment.GetEnvironmentVariable("DATABASE_URL");
}
