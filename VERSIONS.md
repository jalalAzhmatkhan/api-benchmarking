# Frozen versions (task T-0.4)

Frozen on **2026-10-03**. Policy: the newest GA (stable) release that the framework officially
supports. Exceptions are decided in the decision log: D-03 (.NET 10 LTS) and D-15 (JDK 25 LTS).
Changing anything here requires a decision-log entry and re-running **all** stacks. Lockfiles pin
transitive dependencies. Docker images are referenced **by digest**.

## Runtimes, frameworks and drivers

| Stack | Runtime | Framework / server | PostgreSQL driver + pool | Notes |
|---|---|---|---|---|
| python-fastapi | Python **3.14.8** | FastAPI **0.142.2**, pydantic **2.13.5**, gunicorn **26.2.0** + uvicorn-worker **0.4.0** (uvicorn **0.54.0**) | asyncpg **0.31.0** | uv **0.12.22**. Python 3.15.0 GA is on 2026-10-09, after the freeze date |
| node-fastify | Node.js **26.10.0** (26.x becomes Active LTS on 2026-10-28) | Fastify **5.12.5**, TypeScript **7.0.2** | pg **8.23.1** | `node:cluster` × 2 (D-16) |
| java-springboot | JDK **25.0.4.1** (Temurin 25.0.4.1+1, LTS) | Spring Boot **4.1.1** (MVC, Tomcat) | PgJDBC **42.7.13** + HikariCP (Boot-managed) | Maven **3.9.16** via wrapper |
| csharp-dotnet | .NET **10.0.12** LTS | ASP.NET Core 10 Minimal APIs | Npgsql **10.0.3** | SDK image tag `10.0` |
| go-gin | Go **1.27.1** | Gin **v1.12.0** | pgx **v5.11.0** (pgxpool) | |
| rust-axum | Rust **1.99.0** | Axum **0.8.9**, Tokio **1.53.2**, serde **1.0.229**, serde_json **1.0.151** | sqlx **0.9.0** (PgPool) | |
| database | PostgreSQL **18.6** | | | PG 19 not GA at freeze |
| load generator | Grafana k6 **2.3.0** | | | binary is checksum-verified by `deploy/provision` |

Test and coverage tooling is pinned in each service's lockfile when it is implemented.

## Container base images (multi-arch index digests)

| Use | Image |
|---|---|
| Python build + runtime | `python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e` |
| uv binary (copied into the build stage) | `ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc` |
| Node build + runtime | `node:26.10.0-trixie-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1` |
| Java build | `eclipse-temurin:25.0.4.1_1-jdk-noble@sha256:0d623ea18d7b0fe1e12a2c0a920f7e950cad433387e5a49d3611e1507fa07602` |
| Java runtime | `eclipse-temurin:25.0.4.1_1-jre-noble@sha256:398f810215757dc1926390014272579fb0e57c41ef1c8aa4f64ae761613a168b` |
| .NET build | `mcr.microsoft.com/dotnet/sdk:10.0@sha256:e70cdb7f80b0348f5cb85f19a8f670fca061f033d57eed12fa003d58b0e06317` |
| .NET runtime | `mcr.microsoft.com/dotnet/aspnet:10.0.12@sha256:222759b391a1aaf241166672c8f99b2d4ada452e7b5319f3c6e8f265a37b5ad4` |
| Go build | `golang:1.27.1-trixie@sha256:3b77fc618ec235a1ab412de7737f120dd507c57e8d87de4cbb7994fb94275ed5` |
| Rust build | `rust:1.99.0-slim-trixie@sha256:01dd4f9c24801cfc8ba9cf8a5dd6dcca451cd17d1ae73574edc22591de6e6816` |
| Go / Rust runtime | `debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a` |
| PostgreSQL | `postgres:18.6-trixie@sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722` |
| k6 (CI conformance) | `grafana/k6:2.3.0@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34` |

Runtime images share one OS family (Debian trixie) wherever the upstream offers it. Temurin publishes
Ubuntu-based images only. .NET uses Microsoft's default Debian-based `aspnet` tag.

## Sources (checked 2026-10-03)
PyPI, npm, NuGet, crates.io and Maven Central registry APIs. go.dev/dl, static.rust-lang.org,
nodejs.org/dist, the Adoptium API, endoflife.date and GitHub releases (k6, gin, pgx, axum, Spring
Boot, uv). Digests come from Docker Hub, MCR and GHCR registry APIs.
