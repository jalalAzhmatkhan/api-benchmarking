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
