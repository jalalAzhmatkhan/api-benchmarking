use std::future::Future;

use chrono::{DateTime, Utc};

use super::DomainError;

/// Limits from the API contract (Documentation/specs/api-contract.md).
pub const MAX_ID: i64 = 9_007_199_254_740_991;
pub const MAX_PRICE_CENTS: i64 = 9_007_199_254_740_991;
pub const MAX_QUANTITY: i64 = 2_147_483_647;
pub const MAX_NAME_LEN: usize = 100;
pub const MAX_DESCRIPTION_LEN: usize = 1000;

/// A stored item.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Item {
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub price_cents: i64,
    pub quantity: i32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

/// The payload for creating or replacing an item.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ItemInput {
    pub name: String,
    pub description: Option<String>,
    pub price_cents: i64,
    pub quantity: i64,
}

fn invalid(message: &str) -> DomainError {
    DomainError::Validation(message.to_string())
}

/// Checks that `id` is within 1..=MAX_ID.
pub fn validate_id(id: i64) -> Result<(), DomainError> {
    if (1..=MAX_ID).contains(&id) {
        Ok(())
    } else {
        Err(invalid("invalid id"))
    }
}

impl ItemInput {
    /// Applies the contract's field rules. Lengths are counted in Unicode code points.
    pub fn validate(&self) -> Result<(), DomainError> {
        if !(1..=MAX_NAME_LEN).contains(&self.name.chars().count()) {
            return Err(invalid("name must be 1-100 characters"));
        }
        if self
            .description
            .as_ref()
            .is_some_and(|d| d.chars().count() > MAX_DESCRIPTION_LEN)
        {
            return Err(invalid("description must be at most 1000 characters"));
        }
        if !(0..=MAX_PRICE_CENTS).contains(&self.price_cents) {
            return Err(invalid(
                "price_cents must be an integer in 0..9007199254740991",
            ));
        }
        if !(0..=MAX_QUANTITY).contains(&self.quantity) {
            return Err(invalid("quantity must be an integer in 0..2147483647"));
        }
        Ok(())
    }
}

/// The persistence port, implemented by the infrastructure layer.
pub trait ItemRepository: Send + Sync + 'static {
    fn get(&self, id: i64) -> impl Future<Output = Result<Item, DomainError>> + Send;
    fn create(&self, input: &ItemInput) -> impl Future<Output = Result<Item, DomainError>> + Send;
    fn replace(
        &self,
        id: i64,
        input: &ItemInput,
    ) -> impl Future<Output = Result<Item, DomainError>> + Send;
    fn delete(&self, id: i64) -> impl Future<Output = Result<(), DomainError>> + Send;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn input() -> ItemInput {
        ItemInput {
            name: "Widget".into(),
            description: Some("Blue".into()),
            price_cents: 1999,
            quantity: 5,
        }
    }

    fn is_validation(r: Result<(), DomainError>) -> bool {
        matches!(r, Err(DomainError::Validation(m)) if !m.is_empty())
    }

    #[test]
    fn ids() {
        for id in [1, 100_001, MAX_ID] {
            assert!(validate_id(id).is_ok(), "{id}");
        }
        for id in [0, -1, MAX_ID + 1] {
            assert!(is_validation(validate_id(id)), "{id}");
        }
    }

    #[test]
    fn valid_input_and_description_variants() {
        assert!(input().validate().is_ok());
        for description in [
            None,
            Some(String::new()),
            Some("d".repeat(1000)),
            Some("é".repeat(1000)),
        ] {
            let i = ItemInput {
                description,
                ..input()
            };
            assert!(i.validate().is_ok());
        }
        assert!(is_validation(
            ItemInput {
                description: Some("d".repeat(1001)),
                ..input()
            }
            .validate()
        ));
    }

    #[test]
    fn name_lengths_count_code_points() {
        for name in ["a".to_string(), "a".repeat(100), "é".repeat(100)] {
            assert!(ItemInput { name, ..input() }.validate().is_ok());
        }
        for name in [String::new(), "a".repeat(101), "é".repeat(101)] {
            assert!(is_validation(ItemInput { name, ..input() }.validate()));
        }
    }

    #[test]
    fn numeric_bounds() {
        for price_cents in [0, MAX_PRICE_CENTS] {
            assert!(
                ItemInput {
                    price_cents,
                    ..input()
                }
                .validate()
                .is_ok()
            );
        }
        for price_cents in [-1, MAX_PRICE_CENTS + 1] {
            assert!(is_validation(
                ItemInput {
                    price_cents,
                    ..input()
                }
                .validate()
            ));
        }
        for quantity in [0, MAX_QUANTITY] {
            assert!(
                ItemInput {
                    quantity,
                    ..input()
                }
                .validate()
                .is_ok()
            );
        }
        for quantity in [-1, MAX_QUANTITY + 1] {
            assert!(is_validation(
                ItemInput {
                    quantity,
                    ..input()
                }
                .validate()
            ));
        }
    }

    #[test]
    fn error_display() {
        assert_eq!(DomainError::NotFound.to_string(), "item not found");
        assert_eq!(DomainError::Validation("bad".into()).to_string(), "bad");
        assert_eq!(
            DomainError::Internal("db".into()).to_string(),
            "internal error: db"
        );
    }
}
