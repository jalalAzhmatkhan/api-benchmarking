//! Bare process entrypoint: configuration, listener and signal handling. All logic lives in the
//! library crate (excluded from the coverage gate, see COVERAGE_EXCLUSIONS.md).

use items_api::app::run;
use items_api::infrastructure::config::Config;
use tokio::net::TcpListener;

async fn shutdown_signal() {
    let ctrl_c = async { tokio::signal::ctrl_c().await.ok() };
    #[cfg(unix)]
    {
        let mut term = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("SIGTERM handler");
        tokio::select! { _ = ctrl_c => {}, _ = term.recv() => {} }
    }
    #[cfg(not(unix))]
    ctrl_c.await;
}

#[tokio::main]
async fn main() {
    let config = Config::load(|k| std::env::var(k).ok()).unwrap_or_else(|e| {
        eprintln!("fatal: {e}");
        std::process::exit(1);
    });
    let listener = TcpListener::bind(("0.0.0.0", config.port))
        .await
        .unwrap_or_else(|e| {
            eprintln!("fatal: listen on :{}: {e}", config.port);
            std::process::exit(1);
        });
    if let Err(e) = run(&config, listener, shutdown_signal()).await {
        eprintln!("fatal: {e}");
        std::process::exit(1);
    }
}
