//! Items API: the shared `/items` contract, implemented with clean architecture.
//!
//! `domain` <- `application` <- `infrastructure` / `interface` <- `app` (composition root).
//! Inner layers never import outer ones; `domain` has no framework or driver dependencies.

// Declared first: it defines the `require_pool!` / `require_url!` macros the other test modules use.
#[cfg(test)]
#[macro_use]
pub(crate) mod test_support;

pub mod app;
pub mod application;
pub mod domain;
pub mod infrastructure;
pub mod interface;
