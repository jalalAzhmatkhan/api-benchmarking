// Package postgres implements the ItemRepository port with raw SQL over pgx.
package postgres

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

// Canonical statements (Documentation/specs/database-schema.md §2), shared verbatim by all stacks.
const (
	selectSQL = `SELECT id, name, description, price_cents, quantity, created_at, updated_at
FROM items WHERE id = $1`
	insertSQL = `INSERT INTO items (name, description, price_cents, quantity)
VALUES ($1, $2, $3, $4)
RETURNING id, name, description, price_cents, quantity, created_at, updated_at`
	updateSQL = `UPDATE items
SET name = $2, description = $3, price_cents = $4, quantity = $5, updated_at = now()
WHERE id = $1
RETURNING id, name, description, price_cents, quantity, created_at, updated_at`
	deleteSQL = `DELETE FROM items WHERE id = $1`
)

// requestTimeout bounds pool acquisition plus the query (connection-pooling.md: acquire timeout 5 s).
const requestTimeout = 5 * time.Second

// DB is the subset of *pgxpool.Pool the repository needs; pgxmock satisfies it in tests.
type DB interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
}

// ItemRepository is the PostgreSQL implementation of domain.ItemRepository.
type ItemRepository struct{ db DB }

// NewItemRepository wraps a pool.
func NewItemRepository(db DB) *ItemRepository { return &ItemRepository{db: db} }

func scan(row pgx.Row) (domain.Item, error) {
	var it domain.Item
	err := row.Scan(&it.ID, &it.Name, &it.Description, &it.PriceCents, &it.Quantity, &it.CreatedAt, &it.UpdatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return domain.Item{}, domain.ErrNotFound
	}
	if err != nil {
		return domain.Item{}, fmt.Errorf("scan item: %w", err)
	}
	it.CreatedAt, it.UpdatedAt = it.CreatedAt.UTC(), it.UpdatedAt.UTC()
	return it, nil
}

// Get loads one item.
func (r *ItemRepository) Get(ctx context.Context, id int64) (domain.Item, error) {
	ctx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	return scan(r.db.QueryRow(ctx, selectSQL, id))
}

// Create inserts an item.
func (r *ItemRepository) Create(ctx context.Context, in domain.ItemInput) (domain.Item, error) {
	ctx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	return scan(r.db.QueryRow(ctx, insertSQL, in.Name, in.Description, in.PriceCents, in.Quantity))
}

// Replace overwrites an item. A missing row yields domain.ErrNotFound.
func (r *ItemRepository) Replace(ctx context.Context, id int64, in domain.ItemInput) (domain.Item, error) {
	ctx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	return scan(r.db.QueryRow(ctx, updateSQL, id, in.Name, in.Description, in.PriceCents, in.Quantity))
}

// Delete removes an item. Zero affected rows yields domain.ErrNotFound.
func (r *ItemRepository) Delete(ctx context.Context, id int64) error {
	ctx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	tag, err := r.db.Exec(ctx, deleteSQL, id)
	if err != nil {
		return fmt.Errorf("delete item: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return domain.ErrNotFound
	}
	return nil
}
