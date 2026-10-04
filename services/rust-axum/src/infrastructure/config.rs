//! Runtime configuration contract shared by all services (contract/README.md):
//! `DATABASE_URL`, `PORT` and `DB_POOL_SIZE`.

/// Matches deploy/compose.dev.yaml.
pub const DEFAULT_DATABASE_URL: &str = "postgres://bench:bench@127.0.0.1:5432/bench";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub database_url: String,
    pub port: u16,
    pub pool_size: u32,
}

impl Config {
    /// Reads the configuration through `get` (`std::env::var(..).ok()` in production).
    pub fn load(get: impl Fn(&str) -> Option<String>) -> Result<Self, String> {
        let non_empty = |key: &str| get(key).filter(|v| !v.is_empty());
        let port = match non_empty("PORT") {
            None => 8080,
            Some(v) => v
                .parse::<u16>()
                .ok()
                .filter(|p| *p >= 1)
                .ok_or(format!("invalid PORT {v:?}"))?,
        };
        let pool_size = match non_empty("DB_POOL_SIZE") {
            None => 10,
            Some(v) => v
                .parse::<u32>()
                .ok()
                .filter(|n| *n >= 1)
                .ok_or(format!("invalid DB_POOL_SIZE {v:?}"))?,
        };
        Ok(Self {
            database_url: non_empty("DATABASE_URL")
                .unwrap_or_else(|| DEFAULT_DATABASE_URL.to_string()),
            port,
            pool_size,
        })
    }
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use super::*;

    fn env(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let map: HashMap<String, String> = pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        move |k| map.get(k).cloned()
    }

    #[test]
    fn defaults() {
        let c = Config::load(env(&[])).unwrap();
        assert_eq!(
            c,
            Config {
                database_url: DEFAULT_DATABASE_URL.into(),
                port: 8080,
                pool_size: 10
            }
        );
        // empty values behave like unset ones
        assert_eq!(
            Config::load(env(&[("PORT", ""), ("DB_POOL_SIZE", "")]))
                .unwrap()
                .port,
            8080
        );
    }

    #[test]
    fn overrides() {
        let c = Config::load(env(&[
            ("DATABASE_URL", "postgres://x"),
            ("PORT", "9000"),
            ("DB_POOL_SIZE", "20"),
        ]))
        .unwrap();
        assert_eq!(
            c,
            Config {
                database_url: "postgres://x".into(),
                port: 9000,
                pool_size: 20
            }
        );
    }

    #[test]
    fn invalid_values() {
        for pairs in [
            vec![("PORT", "abc")],
            vec![("PORT", "0")],
            vec![("PORT", "70000")],
            vec![("DB_POOL_SIZE", "ten")],
            vec![("DB_POOL_SIZE", "0")],
        ] {
            assert!(Config::load(env(&pairs)).is_err(), "{pairs:?}");
        }
    }
}
