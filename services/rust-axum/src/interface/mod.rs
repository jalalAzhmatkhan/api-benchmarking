//! Axum HTTP layer: routing, request parsing, response mapping and error-to-status mapping.
//! No SQL and no business rules here. No logger and no middleware (benchmark-rules.md).

use std::sync::Arc;

use axum::body::Bytes;
use axum::extract::{Path, State};
use axum::http::{StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::application::UseCases;
use crate::domain::{DomainError, Item, ItemInput, ItemRepository, validate_id};

#[derive(Deserialize)]
struct ItemRequest {
    name: Option<String>,
    description: Option<String>,
    price_cents: Option<i64>,
    quantity: Option<i64>,
}

#[derive(Serialize)]
struct ItemResponse {
    id: i64,
    name: String,
    description: Option<String>,
    price_cents: i64,
    quantity: i32,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Serialize)]
struct ErrorDetail {
    code: &'static str,
    message: String,
}

#[derive(Serialize)]
struct ErrorBody {
    error: ErrorDetail,
}

impl From<Item> for ItemResponse {
    fn from(i: Item) -> Self {
        Self {
            id: i.id,
            name: i.name,
            description: i.description,
            price_cents: i.price_cents,
            quantity: i.quantity,
            created_at: i.created_at,
            updated_at: i.updated_at,
        }
    }
}

/// Maps domain errors to the contract's error body. Internal details are never exposed.
struct ApiError(DomainError);

impl From<DomainError> for ApiError {
    fn from(e: DomainError) -> Self {
        Self(e)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self.0 {
            DomainError::Validation(m) => (StatusCode::BAD_REQUEST, "VALIDATION_ERROR", m),
            DomainError::NotFound => (
                StatusCode::NOT_FOUND,
                "NOT_FOUND",
                "item not found".to_string(),
            ),
            DomainError::Internal(_) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "internal error".to_string(),
            ),
        };
        (
            status,
            Json(ErrorBody {
                error: ErrorDetail { code, message },
            }),
        )
            .into_response()
    }
}

/// Accepts only decimal digits (no sign, no exponent, no fraction) within 1..=MAX_ID.
fn parse_id(s: &str) -> Result<i64, DomainError> {
    if !s.bytes().all(|b| b.is_ascii_digit()) {
        return Err(DomainError::Validation("invalid id".into()));
    }
    let id = s
        .parse::<i64>()
        .map_err(|_| DomainError::Validation("invalid id".into()))?;
    validate_id(id)?;
    Ok(id)
}

/// Syntax/type problems and missing required fields are validation errors; unknown fields are
/// ignored. Range rules live in the domain.
fn decode_input(body: &[u8]) -> Result<ItemInput, DomainError> {
    let req: ItemRequest = serde_json::from_slice(body)
        .map_err(|_| DomainError::Validation("malformed JSON body".into()))?;
    let missing = |field: &str| DomainError::Validation(format!("{field} is required"));
    Ok(ItemInput {
        name: req.name.ok_or_else(|| missing("name"))?,
        description: req.description,
        price_cents: req.price_cents.ok_or_else(|| missing("price_cents"))?,
        quantity: req.quantity.ok_or_else(|| missing("quantity"))?,
    })
}

type State_<R> = State<Arc<UseCases<R>>>;

async fn get_item<R: ItemRepository>(
    State(uc): State_<R>,
    Path(id): Path<String>,
) -> Result<Response, ApiError> {
    let item = uc.get_item(parse_id(&id)?).await?;
    Ok(Json(ItemResponse::from(item)).into_response())
}

async fn create_item<R: ItemRepository>(
    State(uc): State_<R>,
    body: Bytes,
) -> Result<Response, ApiError> {
    let item = uc.create_item(&decode_input(&body)?).await?;
    let location = [(header::LOCATION, format!("/items/{}", item.id))];
    Ok((
        StatusCode::CREATED,
        location,
        Json(ItemResponse::from(item)),
    )
        .into_response())
}

async fn replace_item<R: ItemRepository>(
    State(uc): State_<R>,
    Path(id): Path<String>,
    body: Bytes,
) -> Result<Response, ApiError> {
    let id = parse_id(&id)?;
    let item = uc.replace_item(id, &decode_input(&body)?).await?;
    Ok(Json(ItemResponse::from(item)).into_response())
}

async fn delete_item<R: ItemRepository>(
    State(uc): State_<R>,
    Path(id): Path<String>,
) -> Result<Response, ApiError> {
    uc.delete_item(parse_id(&id)?).await?;
    Ok(StatusCode::NO_CONTENT.into_response())
}

/// The four endpoints of the contract.
pub fn router<R: ItemRepository>(use_cases: Arc<UseCases<R>>) -> Router {
    Router::new()
        .route("/items", post(create_item::<R>))
        .route(
            "/items/{id}",
            get(get_item::<R>)
                .put(replace_item::<R>)
                .delete(delete_item::<R>),
        )
        .with_state(use_cases)
}

#[cfg(test)]
mod tests {
    use std::sync::Mutex;

    use axum::body::Body;
    use axum::http::{Method, Request};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    use super::*;

    /// In-memory repository; `fail` makes every call return that error.
    #[derive(Default)]
    struct FakeRepo {
        fail: Option<DomainError>,
        items: Mutex<Vec<Item>>,
    }

    fn item(id: i64, description: Option<&str>) -> Item {
        let now = DateTime::parse_from_rfc3339("2026-10-03T10:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        Item {
            id,
            name: "Widget".into(),
            description: description.map(str::to_string),
            price_cents: 1999,
            quantity: 5,
            created_at: now,
            updated_at: now,
        }
    }

    impl ItemRepository for FakeRepo {
        async fn get(&self, id: i64) -> Result<Item, DomainError> {
            self.fail.clone().map_or(Ok(()), Err)?;
            Ok(self
                .items
                .lock()
                .unwrap()
                .iter()
                .find(|i| i.id == id)
                .cloned()
                .unwrap_or_else(|| item(id, None)))
        }
        async fn create(&self, _: &ItemInput) -> Result<Item, DomainError> {
            self.fail.clone().map_or(Ok(()), Err)?;
            Ok(item(100_001, Some("Blue")))
        }
        async fn replace(&self, id: i64, _: &ItemInput) -> Result<Item, DomainError> {
            self.fail.clone().map_or(Ok(()), Err)?;
            Ok(item(id, Some("Red")))
        }
        async fn delete(&self, _: i64) -> Result<(), DomainError> {
            self.fail.clone().map_or(Ok(()), Err)
        }
    }

    fn app(fail: Option<DomainError>) -> Router {
        router(Arc::new(UseCases::new(Arc::new(FakeRepo {
            fail,
            ..Default::default()
        }))))
    }

    async fn send(
        app: &Router,
        method: Method,
        path: &str,
        body: &str,
    ) -> (StatusCode, axum::http::HeaderMap, String) {
        let req = Request::builder()
            .method(method)
            .uri(path)
            .header("content-type", "application/json")
            .body(Body::from(body.to_string()))
            .unwrap();
        let res = app.clone().oneshot(req).await.unwrap();
        let (parts, body) = res.into_parts();
        (
            parts.status,
            parts.headers,
            String::from_utf8(body.collect().await.unwrap().to_bytes().to_vec()).unwrap(),
        )
    }

    const VALID: &str = r#"{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}"#;

    fn error_code(body: &str) -> String {
        let v: serde_json::Value = serde_json::from_str(body).expect("response body must be JSON");
        assert!(
            v["error"]["message"]
                .as_str()
                .is_some_and(|m| !m.is_empty()),
            "{body}"
        );
        v["error"]["code"].as_str().unwrap().to_string()
    }

    #[tokio::test]
    async fn get_ok() {
        let (status, headers, body) = send(&app(None), Method::GET, "/items/7", "").await;
        assert_eq!(status, StatusCode::OK);
        assert!(
            headers["content-type"]
                .to_str()
                .unwrap()
                .starts_with("application/json")
        );
        for h in ["etag", "cache-control", "last-modified", "content-encoding"] {
            assert!(!headers.contains_key(h), "unexpected header {h}");
        }
        let v: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert_eq!(
            (
                v["id"].as_i64(),
                v["name"].as_str(),
                v["price_cents"].as_i64(),
                v["quantity"].as_i64()
            ),
            (Some(7), Some("Widget"), Some(1999), Some(5))
        );
        assert_eq!(v["created_at"], "2026-10-03T10:00:00Z");
        assert!(
            v["description"].is_null(),
            "null description must be explicit: {body}"
        );
    }

    #[tokio::test]
    async fn invalid_ids() {
        for id in [
            "abc",
            "0",
            "-1",
            "1.5",
            "1e3",
            "+5",
            "9007199254740992",
            "99999999999999999999",
        ] {
            for method in [Method::GET, Method::DELETE, Method::PUT] {
                let (status, _, body) =
                    send(&app(None), method.clone(), &format!("/items/{id}"), VALID).await;
                assert_eq!(status, StatusCode::BAD_REQUEST, "{method} /items/{id}");
                assert_eq!(error_code(&body), "VALIDATION_ERROR");
            }
        }
    }

    #[tokio::test]
    async fn create_returns_201_with_location() {
        let (status, headers, body) = send(&app(None), Method::POST, "/items", VALID).await;
        assert_eq!(status, StatusCode::CREATED);
        assert_eq!(headers["location"], "/items/100001");
        let v: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert_eq!(v["id"], 100_001);
    }

    #[tokio::test]
    async fn body_validation() {
        let bad = [
            "",
            r#"{"name":"#,
            "[]",
            r#""x""#,
            "null",
            r#"{"price_cents":1,"quantity":1}"#,
            r#"{"name":null,"price_cents":1,"quantity":1}"#,
            r#"{"name":5,"price_cents":1,"quantity":1}"#,
            r#"{"name":"n","quantity":1}"#,
            r#"{"name":"n","price_cents":"10","quantity":1}"#,
            r#"{"name":"n","price_cents":1.5,"quantity":1}"#,
            r#"{"name":"n","price_cents":99999999999999999999,"quantity":1}"#,
            r#"{"name":"n","price_cents":1}"#,
            r#"{"name":"n","price_cents":1,"quantity":1.5}"#,
            r#"{"name":"n","price_cents":1,"quantity":"1"}"#,
            r#"{"name":"","price_cents":1,"quantity":1}"#,
            r#"{"name":"n","price_cents":-1,"quantity":1}"#,
            r#"{"name":"n","price_cents":1,"quantity":2147483648}"#,
        ];
        for body in bad {
            for (method, path) in [(Method::POST, "/items"), (Method::PUT, "/items/5")] {
                let (status, _, out) = send(&app(None), method.clone(), path, body).await;
                assert_eq!(status, StatusCode::BAD_REQUEST, "{method} {path} {body:?}");
                assert_eq!(error_code(&out), "VALIDATION_ERROR");
            }
        }
        let ok = r#"{"name":"n","price_cents":1,"quantity":1,"unknown":true,"id":1}"#;
        assert_eq!(
            send(&app(None), Method::POST, "/items", ok).await.0,
            StatusCode::CREATED
        );
    }

    #[tokio::test]
    async fn replace_and_delete() {
        let (status, _, body) = send(&app(None), Method::PUT, "/items/5", VALID).await;
        assert_eq!(status, StatusCode::OK);
        assert!(body.contains(r#""id":5"#));
        let (status, _, body) = send(&app(None), Method::DELETE, "/items/5", "").await;
        assert_eq!((status, body.as_str()), (StatusCode::NO_CONTENT, ""));
    }

    #[tokio::test]
    async fn error_mapping_and_no_leaks() {
        let cases = [
            (DomainError::NotFound, StatusCode::NOT_FOUND, "NOT_FOUND"),
            (
                DomainError::Validation("bad".into()),
                StatusCode::BAD_REQUEST,
                "VALIDATION_ERROR",
            ),
            (
                DomainError::Internal("secret connection string".into()),
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
            ),
        ];
        for (err, status, code) in cases {
            let app = app(Some(err));
            for (method, path, body) in [
                (Method::GET, "/items/1", ""),
                (Method::POST, "/items", VALID),
                (Method::PUT, "/items/1", VALID),
                (Method::DELETE, "/items/1", ""),
            ] {
                let (got, _, out) = send(&app, method.clone(), path, body).await;
                assert_eq!(
                    (got, error_code(&out).as_str()),
                    (status, code),
                    "{method} {path}"
                );
                assert!(!out.contains("secret"), "internal error leaked: {out}");
            }
        }
    }

    #[tokio::test]
    async fn only_the_contract_routes_exist() {
        assert_eq!(
            send(&app(None), Method::GET, "/items", "").await.0,
            StatusCode::METHOD_NOT_ALLOWED
        );
        assert_eq!(
            send(&app(None), Method::GET, "/health", "").await.0,
            StatusCode::NOT_FOUND
        );
        assert_eq!(
            send(&app(None), Method::PATCH, "/items/1", "").await.0,
            StatusCode::METHOD_NOT_ALLOWED
        );
    }
}
