//! Shared helpers for tests that need a real PostgreSQL (CI provides one; the coverage gate runs
//! with it). Without `DATABASE_URL` those tests return early so the rest of the suite still runs.

use sqlx::postgres::{PgPool, PgPoolOptions};

pub fn database_url() -> Option<String> {
    std::env::var("DATABASE_URL").ok().filter(|v| !v.is_empty())
}

pub async fn pool() -> Option<PgPool> {
    let Some(url) = database_url() else {
        eprintln!("DATABASE_URL not set: skipping database test");
        return None;
    };
    Some(
        PgPoolOptions::new()
            .max_connections(4)
            .connect(&url)
            .await
            .expect("test database must be reachable"),
    )
}

/// Evaluates to the test pool, or returns from the calling test when no database is configured.
/// (A macro keeps the early-return branch out of the tests' own line coverage.)
macro_rules! require_pool {
    () => {
        match $crate::test_support::pool().await {
            Some(p) => p,
            None => return,
        }
    };
}

/// Like `require_pool!` but yields the database URL.
macro_rules! require_url {
    () => {
        match $crate::test_support::database_url() {
            Some(u) => u,
            None => return,
        }
    };
}
