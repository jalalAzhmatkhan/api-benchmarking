//! The four use cases. They depend only on the domain port.

use std::sync::Arc;

use crate::domain::{DomainError, Item, ItemInput, ItemRepository, validate_id};

/// All use cases over one repository.
pub struct UseCases<R: ItemRepository> {
    repo: Arc<R>,
}

impl<R: ItemRepository> UseCases<R> {
    pub fn new(repo: Arc<R>) -> Self {
        Self { repo }
    }

    /// GetItem: validate the id, load the item.
    pub async fn get_item(&self, id: i64) -> Result<Item, DomainError> {
        validate_id(id)?;
        self.repo.get(id).await
    }

    /// CreateItem: validate the input, insert.
    pub async fn create_item(&self, input: &ItemInput) -> Result<Item, DomainError> {
        input.validate()?;
        self.repo.create(input).await
    }

    /// ReplaceItem: validate id and input, replace the whole item.
    pub async fn replace_item(&self, id: i64, input: &ItemInput) -> Result<Item, DomainError> {
        validate_id(id)?;
        input.validate()?;
        self.repo.replace(id, input).await
    }

    /// DeleteItem: validate the id, delete.
    pub async fn delete_item(&self, id: i64) -> Result<(), DomainError> {
        validate_id(id)?;
        self.repo.delete(id).await
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Mutex;

    use chrono::Utc;

    use super::*;

    /// Records calls and returns a canned result.
    #[derive(Default)]
    struct FakeRepo {
        calls: Mutex<Vec<String>>,
        fail: Option<DomainError>,
    }

    impl FakeRepo {
        fn item(id: i64) -> Item {
            let now = Utc::now();
            Item { id, name: "n".into(), description: None, price_cents: 1, quantity: 1, created_at: now, updated_at: now }
        }
        fn record(&self, call: &str) -> Result<(), DomainError> {
            self.calls.lock().unwrap().push(call.to_string());
            self.fail.clone().map_or(Ok(()), Err)
        }
        fn calls(&self) -> usize {
            self.calls.lock().unwrap().len()
        }
    }

    impl ItemRepository for FakeRepo {
        async fn get(&self, id: i64) -> Result<Item, DomainError> {
            self.record("get")?;
            Ok(Self::item(id))
        }
        async fn create(&self, _: &ItemInput) -> Result<Item, DomainError> {
            self.record("create")?;
            Ok(Self::item(100_001))
        }
        async fn replace(&self, id: i64, _: &ItemInput) -> Result<Item, DomainError> {
            self.record("replace")?;
            Ok(Self::item(id))
        }
        async fn delete(&self, _: i64) -> Result<(), DomainError> {
            self.record("delete")
        }
    }

    fn ok_input() -> ItemInput {
        ItemInput { name: "n".into(), description: None, price_cents: 1, quantity: 1 }
    }

    fn bad_input() -> ItemInput {
        ItemInput { name: String::new(), ..ok_input() }
    }

    fn use_cases(fail: Option<DomainError>) -> (UseCases<FakeRepo>, Arc<FakeRepo>) {
        let repo = Arc::new(FakeRepo { fail, ..Default::default() });
        (UseCases::new(repo.clone()), repo)
    }

    #[tokio::test]
    async fn get_item() {
        let (uc, repo) = use_cases(None);
        assert_eq!(uc.get_item(7).await.unwrap().id, 7);
        assert!(matches!(uc.get_item(0).await, Err(DomainError::Validation(_))));
        assert_eq!(repo.calls(), 1, "invalid id must not reach the repository");
        let (uc, _) = use_cases(Some(DomainError::NotFound));
        assert_eq!(uc.get_item(1).await, Err(DomainError::NotFound));
    }

    #[tokio::test]
    async fn create_item() {
        let (uc, repo) = use_cases(None);
        assert_eq!(uc.create_item(&ok_input()).await.unwrap().id, 100_001);
        assert!(matches!(uc.create_item(&bad_input()).await, Err(DomainError::Validation(_))));
        assert_eq!(repo.calls(), 1);
        let (uc, _) = use_cases(Some(DomainError::Internal("x".into())));
        assert!(matches!(uc.create_item(&ok_input()).await, Err(DomainError::Internal(_))));
    }

    #[tokio::test]
    async fn replace_item() {
        let (uc, repo) = use_cases(None);
        assert_eq!(uc.replace_item(5, &ok_input()).await.unwrap().id, 5);
        assert!(matches!(uc.replace_item(-1, &ok_input()).await, Err(DomainError::Validation(_))));
        assert!(matches!(uc.replace_item(1, &bad_input()).await, Err(DomainError::Validation(_))));
        assert_eq!(repo.calls(), 1);
        let (uc, _) = use_cases(Some(DomainError::NotFound));
        assert_eq!(uc.replace_item(1, &ok_input()).await, Err(DomainError::NotFound));
    }

    #[tokio::test]
    async fn delete_item() {
        let (uc, repo) = use_cases(None);
        assert!(uc.delete_item(9).await.is_ok());
        assert!(matches!(uc.delete_item(0).await, Err(DomainError::Validation(_))));
        assert_eq!(repo.calls(), 1);
        let (uc, _) = use_cases(Some(DomainError::NotFound));
        assert_eq!(uc.delete_item(1).await, Err(DomainError::NotFound));
    }
}
