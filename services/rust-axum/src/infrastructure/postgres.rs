//! PostgreSQL repository: raw SQL through sqlx, no ORM and no query macros.
//! The pool follows Documentation/specs/connection-pooling.md: fixed size (min = max), pre-warmed,
//! 5 s acquire timeout, no lifetime/idle eviction. sqlx defaults (statement cache, pre-acquire
//! ping) are kept (decision D-06).

use std::time::Duration;

use chrono::{DateTime, Utc};
use sqlx::Row;
use sqlx::postgres::{PgPool, PgPoolOptions, PgRow};
use tokio::task::JoinSet;

use crate::domain::{DomainError, Item, ItemInput, ItemRepository};

// Canonical statements (Documentation/specs/database-schema.md §2), shared verbatim by all stacks.
const SELECT_SQL: &str = "SELECT id, name, description, price_cents, quantity, created_at, updated_at \
FROM items WHERE id = $1";
const INSERT_SQL: &str = "INSERT INTO items (name, description, price_cents, quantity) \
VALUES ($1, $2, $3, $4) \
RETURNING id, name, description, price_cents, quantity, created_at, updated_at";
const UPDATE_SQL: &str = "UPDATE items \
SET name = $2, description = $3, price_cents = $4, quantity = $5, updated_at = now() \
WHERE id = $1 \
RETURNING id, name, description, price_cents, quantity, created_at, updated_at";
const DELETE_SQL: &str = "DELETE FROM items WHERE id = $1";

impl From<sqlx::Error> for DomainError {
    fn from(e: sqlx::Error) -> Self {
        DomainError::Internal(e.to_string())
    }
}

/// Builds the fixed-size pool and opens every connection before returning, so the first measured
/// requests do not pay for connection setup.
pub async fn connect(database_url: &str, size: u32) -> Result<PgPool, DomainError> {
    let pool = PgPoolOptions::new()
        .max_connections(size)
        .min_connections(size)
        .acquire_timeout(Duration::from_secs(5))
        .idle_timeout(None)
        .max_lifetime(None)
        .connect(database_url)
        .await?;
    warm(&pool, size).await?;
    Ok(pool)
}

/// Opens `n` connections by running `n` overlapping queries (forces `n` distinct connections).
pub async fn warm(pool: &PgPool, n: u32) -> Result<(), DomainError> {
    let mut tasks = JoinSet::new();
    for _ in 0..n {
        let pool = pool.clone();
        tasks.spawn(async move { sqlx::query("SELECT pg_sleep(0.05)").execute(&pool).await });
    }
    while let Some(joined) = tasks.join_next().await {
        joined.expect("warm-up task panicked")?;
    }
    Ok(())
}

fn to_item(row: &PgRow) -> Result<Item, sqlx::Error> {
    Ok(Item {
        id: row.try_get("id")?,
        name: row.try_get("name")?,
        description: row.try_get("description")?,
        price_cents: row.try_get("price_cents")?,
        quantity: row.try_get("quantity")?,
        created_at: row.try_get::<DateTime<Utc>, _>("created_at")?,
        updated_at: row.try_get::<DateTime<Utc>, _>("updated_at")?,
    })
}

/// `ItemRepository` over a PostgreSQL pool.
#[derive(Clone)]
pub struct PgItemRepository {
    pool: PgPool,
}

impl PgItemRepository {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }
}

impl ItemRepository for PgItemRepository {
    async fn get(&self, id: i64) -> Result<Item, DomainError> {
        let row = sqlx::query(SELECT_SQL)
            .bind(id)
            .fetch_optional(&self.pool)
            .await?;
        Ok(to_item(&row.ok_or(DomainError::NotFound)?)?)
    }

    async fn create(&self, input: &ItemInput) -> Result<Item, DomainError> {
        let row = sqlx::query(INSERT_SQL)
            .bind(&input.name)
            .bind(&input.description)
            .bind(input.price_cents)
            .bind(input.quantity as i32) // range validated by the domain (0..=i32::MAX)
            .fetch_one(&self.pool)
            .await?;
        Ok(to_item(&row)?)
    }

    async fn replace(&self, id: i64, input: &ItemInput) -> Result<Item, DomainError> {
        let row = sqlx::query(UPDATE_SQL)
            .bind(id)
            .bind(&input.name)
            .bind(&input.description)
            .bind(input.price_cents)
            .bind(input.quantity as i32)
            .fetch_optional(&self.pool)
            .await?;
        Ok(to_item(&row.ok_or(DomainError::NotFound)?)?)
    }

    async fn delete(&self, id: i64) -> Result<(), DomainError> {
        let result = sqlx::query(DELETE_SQL).bind(id).execute(&self.pool).await?;
        if result.rows_affected() == 0 {
            return Err(DomainError::NotFound);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::MAX_ID;

    fn input(name: &str) -> ItemInput {
        ItemInput {
            name: name.into(),
            description: Some("desc".into()),
            price_cents: 1999,
            quantity: 5,
        }
    }

    #[tokio::test]
    async fn crud_round_trip() {
        let pool = require_pool!();
        let repo = PgItemRepository::new(pool);

        let created = repo.create(&input("rust-crud")).await.unwrap();
        assert!(created.id > 0);
        assert_eq!(
            (created.name.as_str(), created.price_cents, created.quantity),
            ("rust-crud", 1999, 5)
        );
        assert_eq!(created.description.as_deref(), Some("desc"));
        assert!(created.updated_at >= created.created_at);

        assert_eq!(repo.get(created.id).await.unwrap(), created);

        let next = ItemInput {
            name: "rust-crud-2".into(),
            description: None,
            price_cents: 7,
            quantity: 0,
        };
        let replaced = repo.replace(created.id, &next).await.unwrap();
        assert_eq!(
            (
                replaced.id,
                replaced.name.as_str(),
                replaced.description.clone()
            ),
            (created.id, "rust-crud-2", None)
        );
        assert_eq!(replaced.created_at, created.created_at);
        assert!(replaced.updated_at >= created.updated_at);
        assert_eq!(repo.get(created.id).await.unwrap(), replaced);

        repo.delete(created.id).await.unwrap();
        assert_eq!(repo.get(created.id).await, Err(DomainError::NotFound));
        assert_eq!(repo.delete(created.id).await, Err(DomainError::NotFound));
        assert_eq!(
            repo.replace(created.id, &next).await,
            Err(DomainError::NotFound)
        );
    }

    #[tokio::test]
    async fn unknown_id_is_not_found() {
        let pool = require_pool!();
        let repo = PgItemRepository::new(pool);
        assert_eq!(repo.get(MAX_ID).await, Err(DomainError::NotFound));
    }

    #[tokio::test]
    async fn closed_pool_is_an_internal_error() {
        let pool = require_pool!();
        let repo = PgItemRepository::new(pool.clone());
        pool.close().await;
        assert!(matches!(repo.get(1).await, Err(DomainError::Internal(_))));
        assert!(matches!(
            repo.create(&input("x")).await,
            Err(DomainError::Internal(_))
        ));
        assert!(matches!(
            repo.replace(1, &input("x")).await,
            Err(DomainError::Internal(_))
        ));
        assert!(matches!(
            repo.delete(1).await,
            Err(DomainError::Internal(_))
        ));
        assert!(warm(&pool, 2).await.is_err());
    }

    #[tokio::test]
    async fn connect_opens_exactly_the_pool_size() {
        let url = require_url!();
        let pool = connect(&url, 3).await.unwrap();
        assert_eq!(pool.size(), 3);
        pool.close().await;
    }

    #[tokio::test]
    async fn connect_fails_for_an_unreachable_database() {
        let r = connect("postgres://bench:bench@127.0.0.1:1/bench", 1).await;
        assert!(matches!(r, Err(DomainError::Internal(_))));
    }
}
