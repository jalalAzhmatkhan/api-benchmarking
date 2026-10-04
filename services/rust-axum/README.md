# rust-axum

**Stack:** Rust 1.99.0 · Axum 0.8 · Tokio 1.53 · sqlx 0.9 `PgPool` (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.6.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture, one crate)
```
src/domain/          Item, ItemInput validation, ItemRepository port (async fn in trait), DomainError
src/application/     UseCases<R>: get_item, create_item, replace_item, delete_item
src/infrastructure/  config (DATABASE_URL, PORT, DB_POOL_SIZE) and postgres (raw-SQL repository + pool)
src/interface/       axum router, DTOs, error mapping
src/app.rs           composition root: pool → repository → use cases → router → server
src/main.rs          bare entrypoint (excluded from coverage)
```
Dependencies point inward; `domain` imports nothing but `chrono` and the standard library.

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench cargo run --release
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

cargo fmt --check && cargo clippy --all-targets -- -D warnings
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench \
  cargo llvm-cov --ignore-filename-regex 'src/main\.rs' --fail-under-lines 100   # needs cargo-llvm-cov
```
Without `DATABASE_URL` the database-backed tests return early, so the rest of the suite still runs.

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| Pool | `min = max = DB_POOL_SIZE` (10), acquire timeout 5 s, no idle/lifetime eviction, pre-warmed | `connection-pooling.md` |
| `[profile.release] strip = true` | symbols only | like Go's `-s -w`. Otherwise the **default** release profile: no LTO, no `codegen-units`, no `panic=abort`, no PGO |
| axum features | `http1`, `tokio`, `json` | no HTTP/2, no extra middleware, no tracing |
| Runtime | `#[tokio::main]` multi-thread, default worker threads (= available parallelism) | `connection-pooling.md` §6 |

Default: sqlx statement cache and pre-acquire ping (D-06), no panic-catching layer (handlers return `Result`s).
