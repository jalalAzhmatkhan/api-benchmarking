//! Items API: the shared `/items` contract, implemented with clean architecture.
//!
//! `domain` <- `application` <- `infrastructure` / `interface` <- `app` (composition root).
//! Inner layers never import outer ones; `domain` has no framework or driver dependencies.

pub mod application;
pub mod domain;
