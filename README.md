# API Benchmarking

Cross-language REST API performance study. The **same 4-endpoint API** (`GET`, `POST`, `PUT`,
`DELETE` on `/items`) is implemented in six stacks against PostgreSQL. Each stack uses minimal
default configuration, raw SQL with a connection pool, no ORM, no caching, clean architecture and
100 % unit-test coverage. Grafana k6 finds the **maximum number of concurrent users** each stack
sustains with **p50/p95/p99 ≤ 1 s and zero failed requests**, while CPU and RAM of both the API and
the database are captured to locate the bottleneck.

| Stack | Folder |
|---|---|
| Python · FastAPI (uv, gunicorn + uvicorn workers, asyncpg) | `services/python-fastapi` |
| Node.js · Fastify (TypeScript, pg, `node:cluster`) | `services/node-fastify` |
| Java · Spring Boot (MVC, JdbcClient, HikariCP) | `services/java-springboot` |
| C# · ASP.NET Core (.NET 10 LTS, Npgsql) | `services/csharp-dotnet` |
| Go · Gin (pgx/pgxpool) | `services/go-gin` |
| Rust · Axum (Tokio, sqlx) | `services/rust-axum` |

## Infrastructure
- **DEV_SERVER**: system under test (2 vCPU / 8 GB). One API stack + PostgreSQL at a time, with unpinned CPU.
- **K6_SERVER**: dedicated k6 load generator in the same region.
- Both VMs are provisioned by the **Provision VMs** workflow (`.github/workflows/provision-vms.yml`,
  manual trigger), using the GitHub environments `DEV_SERVER` and `K6_SERVER`
  (`VM_IP_ADDRESS`, `VM_USERNAME`, secret `VM_PASSWORD`). See [`deploy/README.md`](deploy/README.md).

## Branching: Git flow
`master` = released, benchmark-ready states (tagged `vX.Y.Z`). `develop` = integration.
Work happens on `feature/<task-id>-<slug>` branches with PRs into `develop`. Use `release/x.y.z` and
`hotfix/x.y.z` per Git flow. Commits follow Conventional Commits (`feat(go-gin): …`).
Every benchmark campaign runs from a tag.

## Documentation
Specifications, research, plans and the IEEE-style report are maintained in the workspace's
`Documentation/` folder (kept outside this repository by decision D-14). Each result's `meta.json`
records a hash of the spec set it was produced under.
