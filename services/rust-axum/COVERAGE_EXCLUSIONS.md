# Coverage exclusions: rust-axum

| Path | Reason |
|---|---|
| `src/main.rs` | Bare process entrypoint (config, listener, signal handling, `process::exit`). All logic lives in the library crate (`app::run` etc.), which is fully tested. Approved by the System Analyst role per `clean-architecture.md` |
| `src/test_support.rs` | Test-only helper that opens the test database (the `DATABASE_URL`-unset branch cannot run in CI, where the database exists) |

The CI gate (`.github/workflows/ci-rust-axum.yml`) runs `cargo llvm-cov --ignore-filename-regex 'src/(main|test_support)\.rs' --fail-under-lines 100`
with a PostgreSQL available (`DATABASE_URL`), so the database-backed tests count toward coverage.
