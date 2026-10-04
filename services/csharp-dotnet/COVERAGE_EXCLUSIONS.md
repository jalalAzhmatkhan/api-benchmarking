# Coverage exclusions: csharp-dotnet

**None.** Every line and branch of `Items.Domain`, `Items.Application`, `Items.Infrastructure` and `Items.Api`
is gated, including `Program.cs` and the composition root (`WebApplicationFactory<Program>` starts them for real).

Coverlet gate (`tests/Items.Tests/Items.Tests.csproj`, run with `-p:CollectCoverage=true`): total **line 100 %** and **branch 100 %**.
Database-backed tests (`[DbFact]`) run when `DATABASE_URL` is set; CI starts the seeded dev PostgreSQL so they count toward coverage.
