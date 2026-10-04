//! Entities, validation rules and the repository port. No framework, no driver.

mod item;

pub use item::{
    Item, ItemInput, ItemRepository, validate_id, MAX_DESCRIPTION_LEN, MAX_ID, MAX_NAME_LEN,
    MAX_PRICE_CENTS, MAX_QUANTITY,
};

/// Errors the domain and its ports can produce.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DomainError {
    /// The request violates a contract rule (maps to 400 `VALIDATION_ERROR`).
    Validation(String),
    /// The item does not exist (maps to 404 `NOT_FOUND`).
    NotFound,
    /// An infrastructure failure (maps to 500 `INTERNAL_ERROR`; the message is never exposed).
    Internal(String),
}

impl std::fmt::Display for DomainError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DomainError::Validation(m) => write!(f, "{m}"),
            DomainError::NotFound => write!(f, "item not found"),
            DomainError::Internal(m) => write!(f, "internal error: {m}"),
        }
    }
}

impl std::error::Error for DomainError {}
