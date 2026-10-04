package postgres

import (
	"context"
	"errors"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/pashagolub/pgxmock/v5"
)

const unreachableURL = "postgres://bench:bench@127.0.0.1:1/bench"

func TestPoolConfig(t *testing.T) {
	cfg, err := PoolConfig(unreachableURL, 10)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.MaxConns != 10 || cfg.MinConns != 10 {
		t.Fatalf("pool must be fixed at 10: min=%d max=%d", cfg.MinConns, cfg.MaxConns)
	}
	if cfg.MaxConnLifetime.Hours() != 1 || cfg.MaxConnIdleTime.Minutes() != 30 {
		t.Fatalf("unexpected lifetimes: %v / %v", cfg.MaxConnLifetime, cfg.MaxConnIdleTime)
	}
	if _, err := PoolConfig("://not a url", 10); err == nil {
		t.Fatal("expected a parse error")
	}
}

func TestDefaultFactory(t *testing.T) {
	cfg, err := PoolConfig(unreachableURL, 2)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	p, err := DefaultFactory(ctx, cfg) // lazy: succeeds without a database
	if err != nil {
		t.Fatal(err)
	}
	p.Close()

	cfg.MaxConns = 0 // invalid pool size is rejected by the pool
	if _, err := DefaultFactory(ctx, cfg); err == nil {
		t.Fatal("expected an error for MaxConns=0")
	}
}

func fakeFactory(p Pool, err error) Factory {
	return func(context.Context, *pgxpool.Config) (Pool, error) { return p, err }
}

func TestNewPoolWarmsConnections(t *testing.T) {
	mock, _ := pgxmock.NewPool()
	for i := 0; i < 3; i++ {
		mock.ExpectExec("SELECT pg_sleep").WillReturnResult(pgxmock.NewResult("SELECT", 1))
	}
	p, err := NewPool(context.Background(), unreachableURL, 3, fakeFactory(mock, nil))
	if err != nil || p == nil {
		t.Fatalf("got %v, %v", p, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestNewPoolErrors(t *testing.T) {
	if _, err := NewPool(context.Background(), "://bad", 3, nil); err == nil {
		t.Fatal("expected a config error")
	}
	boom := errors.New("factory failed")
	if _, err := NewPool(context.Background(), unreachableURL, 3, fakeFactory(nil, boom)); !errors.Is(err, boom) {
		t.Fatalf("factory error must propagate: %v", err)
	}
	mock, _ := pgxmock.NewPool()
	warmErr := errors.New("db down")
	mock.ExpectExec("SELECT pg_sleep").WillReturnError(warmErr)
	mock.ExpectClose()
	if _, err := NewPool(context.Background(), unreachableURL, 1, fakeFactory(mock, nil)); !errors.Is(err, warmErr) {
		t.Fatalf("warm-up error must propagate: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("pool must be closed after a failed warm-up: %v", err)
	}
}
