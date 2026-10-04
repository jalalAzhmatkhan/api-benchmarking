//! Composition root: pool → repository → use cases → router → server.

use std::future::Future;
use std::sync::Arc;

use tokio::net::TcpListener;

use crate::application::UseCases;
use crate::infrastructure::config::Config;
use crate::infrastructure::postgres::{PgItemRepository, connect};
use crate::interface::router;

/// Why the service stopped abnormally.
#[derive(Debug)]
pub enum AppError {
    Database(String),
    Server(std::io::Error),
}

impl std::fmt::Display for AppError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AppError::Database(m) => write!(f, "database: {m}"),
            AppError::Server(e) => write!(f, "server: {e}"),
        }
    }
}

impl std::error::Error for AppError {}

/// Starts the service on `listener` and serves until `shutdown` completes (graceful shutdown).
pub async fn run(
    config: &Config,
    listener: TcpListener,
    shutdown: impl Future<Output = ()> + Send + 'static,
) -> Result<(), AppError> {
    let pool = connect(&config.database_url, config.pool_size)
        .await
        .map_err(|e| AppError::Database(e.to_string()))?;
    let repo = Arc::new(PgItemRepository::new(pool.clone()));
    let app = router(Arc::new(UseCases::new(repo)));
    let served = axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await;
    pool.close().await;
    served.map_err(AppError::Server)
}

#[cfg(test)]
mod tests {
    use std::io::{Read, Write};
    use std::net::TcpStream;

    use tokio::sync::oneshot;

    use super::*;

    fn http_get(addr: std::net::SocketAddr, path: &str) -> String {
        let mut s = TcpStream::connect(addr).unwrap();
        write!(
            s,
            "GET {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
        )
        .unwrap();
        let mut out = String::new();
        s.read_to_string(&mut out).unwrap();
        out
    }

    #[tokio::test]
    async fn serves_the_contract_and_shuts_down_gracefully() {
        let url = require_url!();
        let config = Config {
            database_url: url,
            port: 0,
            pool_size: 2,
        };
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let (tx, rx) = oneshot::channel::<()>();
        let server = tokio::spawn(async move {
            run(&config, listener, async {
                rx.await.ok();
            })
            .await
        });

        let seeded = tokio::task::spawn_blocking(move || http_get(addr, "/items/1"))
            .await
            .unwrap();
        assert!(seeded.starts_with("HTTP/1.1 200"), "{seeded}");
        let missing =
            tokio::task::spawn_blocking(move || http_get(addr, "/items/9007199254740991"))
                .await
                .unwrap();
        assert!(missing.starts_with("HTTP/1.1 404"), "{missing}");

        tx.send(()).unwrap();
        server.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn database_errors_stop_startup() {
        let config = Config {
            database_url: "postgres://bench:bench@127.0.0.1:1/bench".into(),
            port: 0,
            pool_size: 1,
        };
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let err = run(&config, listener, async {}).await.unwrap_err();
        assert!(matches!(err, AppError::Database(_)));
        assert!(err.to_string().starts_with("database: "));
    }

    #[test]
    fn server_error_display() {
        let e = AppError::Server(std::io::Error::other("boom"));
        assert_eq!(e.to_string(), "server: boom");
    }
}
