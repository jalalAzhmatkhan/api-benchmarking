# java-springboot

**Stack:** JDK 25 (Temurin) · Spring Boot 4.1.1 (Spring MVC on Tomcat) · `JdbcClient` · HikariCP 7 · PgJDBC 42.7.13 (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.3.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture, package `bench.items`)
```
domain/                 Item, ItemInput (+ validation), ItemRepository port, DomainException family. No Spring imports
application/            GetItem, CreateItem, ReplaceItem, DeleteItem (plain classes)
infrastructure/         JdbcItemRepository (raw SQL), DatabaseSettings (DATABASE_URL), PoolWarmer
interfaces/http/        ItemController, ItemRequestParser (strict JSON), ItemResponse, ApiExceptionHandler
AppConfig               composition root: settings → Hikari pool → repository → use cases
ItemsApplication        bare entrypoint (excluded from coverage)
```

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench ./mvnw spring-boot:run
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench ./mvnw verify   # tests + JaCoCo gate (100 % line and branch)
```
Without `DATABASE_URL` the database-backed tests are skipped (the gate then fails on purpose: they count toward coverage).

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| HikariCP | `maximumPoolSize = minimumIdle = DB_POOL_SIZE` (10), `connectionTimeout` 5 s, idle 10 min, lifetime 30 min, pre-warmed before the web server starts | `connection-pooling.md` |
| `logging.level.root` | `WARN` | no per-request logging (`benchmark-rules.md`) |
| `spring.main.banner-mode` | `off` | startup output only |
| JSON | own strict Jackson 3 tree parsing instead of data binding | a string/fraction/overflow where an integer is required must be a contract 400, not a coerced value |
| `ApiExceptionHandler` | maps `RuntimeException` to the contract 500 | framework errors (405, 404) keep their defaults |

Everything else is the Boot default: Tomcat (200 threads), **virtual threads off** (D-13), no compression, no caching headers,
PgJDBC `prepareThreshold` (D-06), and **no JVM flags** (D-04): on 2 CPUs the JVM picks G1 with a heap of 25 % of the container limit.
