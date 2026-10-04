package postgres

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Pool is the connection pool used by the service.
type Pool interface {
	DB
	Close()
}

// Factory builds a Pool from a parsed config; tests inject fakes.
type Factory func(ctx context.Context, cfg *pgxpool.Config) (Pool, error)

// DefaultFactory creates a real pgxpool. Connections are opened lazily/in the background.
func DefaultFactory(ctx context.Context, cfg *pgxpool.Config) (Pool, error) {
	p, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	return p, nil
}

// PoolConfig applies Documentation/specs/connection-pooling.md: fixed pool (min = max = size),
// lifetime 1 h, idle 30 min. Statement caching and the protocol stay at pgx defaults (D-06).
func PoolConfig(databaseURL string, size int) (*pgxpool.Config, error) {
	cfg, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		return nil, fmt.Errorf("parse DATABASE_URL: %w", err)
	}
	cfg.MaxConns = int32(size)
	cfg.MinConns = int32(size)
	cfg.MaxConnLifetime = time.Hour
	cfg.MaxConnIdleTime = 30 * time.Minute
	return cfg, nil
}

// NewPool builds the pool and pre-warms it so the first measured requests do not pay for
// connection setup. ctx must outlive the pool (it drives background connection creation).
func NewPool(ctx context.Context, databaseURL string, size int, factory Factory) (Pool, error) {
	cfg, err := PoolConfig(databaseURL, size)
	if err != nil {
		return nil, err
	}
	pool, err := factory(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}
	if err := Warm(ctx, pool, size); err != nil {
		pool.Close()
		return nil, fmt.Errorf("warm pool: %w", err)
	}
	return pool, nil
}

// Warm opens n connections by running n overlapping queries, which forces n distinct connections.
func Warm(ctx context.Context, db DB, n int) error {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	var wg sync.WaitGroup
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := db.Exec(ctx, "SELECT pg_sleep(0.05)")
			errs <- err
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			return err
		}
	}
	return nil
}
