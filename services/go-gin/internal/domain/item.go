// Package domain holds the Item entity, its validation rules and the repository port.
// It imports nothing outside the standard library.
package domain

import (
	"context"
	"errors"
	"time"
	"unicode/utf8"
)

// Limits from the API contract (Documentation/specs/api-contract.md).
const (
	MaxID             int64 = 9_007_199_254_740_991
	MaxPriceCents     int64 = 9_007_199_254_740_991
	MaxQuantity       int64 = 2_147_483_647
	MaxNameLength           = 100
	MaxDescriptionLen       = 1000
)

// ErrNotFound is returned when an item does not exist.
var ErrNotFound = errors.New("item not found")

// ValidationError describes why a request is invalid.
type ValidationError struct{ Message string }

func (e *ValidationError) Error() string { return e.Message }

// Item is a stored item.
type Item struct {
	ID          int64
	Name        string
	Description *string
	PriceCents  int64
	Quantity    int32
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// ItemInput is the payload for creating or replacing an item.
type ItemInput struct {
	Name        string
	Description *string
	PriceCents  int64
	Quantity    int64
}

// ValidateID checks that id is within 1..MaxID.
func ValidateID(id int64) error {
	if id < 1 || id > MaxID {
		return &ValidationError{Message: "invalid id"}
	}
	return nil
}

// Validate applies the contract's field rules. Lengths are counted in Unicode code points.
func (in ItemInput) Validate() error {
	if n := utf8.RuneCountInString(in.Name); n < 1 || n > MaxNameLength {
		return &ValidationError{Message: "name must be 1-100 characters"}
	}
	if in.Description != nil && utf8.RuneCountInString(*in.Description) > MaxDescriptionLen {
		return &ValidationError{Message: "description must be at most 1000 characters"}
	}
	if in.PriceCents < 0 || in.PriceCents > MaxPriceCents {
		return &ValidationError{Message: "price_cents must be an integer in 0..9007199254740991"}
	}
	if in.Quantity < 0 || in.Quantity > MaxQuantity {
		return &ValidationError{Message: "quantity must be an integer in 0..2147483647"}
	}
	return nil
}

// ItemRepository is the persistence port implemented by the infrastructure layer.
type ItemRepository interface {
	Get(ctx context.Context, id int64) (Item, error)
	Create(ctx context.Context, in ItemInput) (Item, error)
	Replace(ctx context.Context, id int64, in ItemInput) (Item, error)
	Delete(ctx context.Context, id int64) error
}
