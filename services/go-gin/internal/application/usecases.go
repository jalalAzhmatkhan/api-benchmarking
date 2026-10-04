// Package application contains the four use cases. They depend only on the domain.
package application

import (
	"context"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

// GetItem returns one item.
type GetItem struct{ Repo domain.ItemRepository }

// Execute validates the id and loads the item.
func (u GetItem) Execute(ctx context.Context, id int64) (domain.Item, error) {
	if err := domain.ValidateID(id); err != nil {
		return domain.Item{}, err
	}
	return u.Repo.Get(ctx, id)
}

// CreateItem stores a new item.
type CreateItem struct{ Repo domain.ItemRepository }

// Execute validates the input and creates the item.
func (u CreateItem) Execute(ctx context.Context, in domain.ItemInput) (domain.Item, error) {
	if err := in.Validate(); err != nil {
		return domain.Item{}, err
	}
	return u.Repo.Create(ctx, in)
}

// ReplaceItem fully replaces an existing item.
type ReplaceItem struct{ Repo domain.ItemRepository }

// Execute validates id and input, then replaces the item.
func (u ReplaceItem) Execute(ctx context.Context, id int64, in domain.ItemInput) (domain.Item, error) {
	if err := domain.ValidateID(id); err != nil {
		return domain.Item{}, err
	}
	if err := in.Validate(); err != nil {
		return domain.Item{}, err
	}
	return u.Repo.Replace(ctx, id, in)
}

// DeleteItem removes an item.
type DeleteItem struct{ Repo domain.ItemRepository }

// Execute validates the id and deletes the item.
func (u DeleteItem) Execute(ctx context.Context, id int64) error {
	if err := domain.ValidateID(id); err != nil {
		return err
	}
	return u.Repo.Delete(ctx, id)
}
