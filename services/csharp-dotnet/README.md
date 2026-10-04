# csharp-dotnet

**Stack:** .NET 10 LTS (10.0.12) · ASP.NET Core Minimal APIs (Kestrel) · Npgsql 10.0.3 `NpgsqlDataSource` (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.4.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture, one project per layer)
```
src/Items.Domain/          Item, ItemInput (+ validation by Unicode rune), IItemRepository port, exceptions. No dependencies
src/Items.Application/     GetItem, CreateItem, ReplaceItem, DeleteItem
src/Items.Infrastructure/  NpgsqlItemRepository (raw SQL), DatabaseSettings (DATABASE_URL), PoolWarmer
src/Items.Api/             ItemEndpoints, ItemRequestParser (strict JSON), DTOs, AppComposition (composition root), Program.cs
tests/Items.Tests/         xunit: unit tests, in-memory HTTP tests (TestServer), database-backed tests ([DbFact])
```
Project references point inward: `Api` → `Application`/`Infrastructure` → `Domain`.

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench dotnet run -c Release --project src/Items.Api
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench \
  dotnet test tests/Items.Tests/Items.Tests.csproj -c Release -p:CollectCoverage=true   # gate: 100 % line and branch
```
Without `DATABASE_URL` the `[DbFact]` tests are skipped (the gate then fails on purpose: they count toward coverage).

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| Npgsql connection string | `Minimum Pool Size = Maximum Pool Size = DB_POOL_SIZE` (10), `Timeout` 5 s, `Command Timeout` 5 s, `Connection Idle Lifetime` 600 s, `Connection Lifetime` 0; pool opened before the server accepts traffic | `connection-pooling.md` |
| `appsettings.json` | `Logging:LogLevel:Default = Warning` | no per-request logging (`benchmark-rules.md`) |
| `UseUrls("http://0.0.0.0:$PORT")` | port from the env contract | |
| JSON | own strict `JsonDocument` parsing instead of model binding | a string/fraction/overflow where an integer is required must be a contract 400 |
| `InvariantGlobalization` | `true` | no ICU dependency in the runtime image |

Everything else is the default: Kestrel and thread-pool settings, **workstation concurrent GC** (the Web SDK does not turn on Server GC; recorded in `meta.json`), Npgsql auto-prepare off (D-06),
no Native AOT, no ReadyToRun, no trimming.
