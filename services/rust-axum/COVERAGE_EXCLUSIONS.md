# Coverage exclusions: rust-axum

| Path | Reason |
|---|---|
| `src/main.rs` | Bare process entrypoint (config, listener, signal handling, `process::exit`). All logic lives in the library crate (`app::run` etc.), which is fully tested. Approved by the System Analyst role per `clean-architecture.md` |

The CI gate (`.github/workflows/ci-rust-axum.yml`) runs `cargo llvm-cov --ignore-filename-regex 'src/main\.rs' --fail-under-lines 100`
with a PostgreSQL available (`DATABASE_URL`), so the database-backed tests count toward coverage.
