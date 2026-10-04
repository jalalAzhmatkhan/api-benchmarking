package app

import (
	"context"
	"errors"
	"net"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/pashagolub/pgxmock/v5"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/infrastructure/postgres"
)

func getenv(m map[string]string) func(string) string { return func(k string) string { return m[k] } }

func loopback(string, string) (net.Listener, error) { return net.Listen("tcp", "127.0.0.1:0") }

func factoryFor(p postgres.Pool, err error) postgres.Factory {
	return func(context.Context, *pgxpool.Config) (postgres.Pool, error) { return p, err }
}

func TestRunServesAndShutsDown(t *testing.T) {
	mock, _ := pgxmock.NewPool()
	mock.ExpectExec("SELECT pg_sleep").WillReturnResult(pgxmock.NewResult("SELECT", 1))
	mock.ExpectQuery("SELECT id").WithArgs(int64(1)).WillReturnError(pgx.ErrNoRows)
	mock.ExpectClose()

	lnCh := make(chan net.Listener, 1)
	listen := func(n, a string) (net.Listener, error) {
		ln, err := loopback(n, a)
		lnCh <- ln
		return ln, err
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- Run(ctx, Deps{Getenv: getenv(map[string]string{"DB_POOL_SIZE": "1"}), Factory: factoryFor(mock, nil), Listen: listen})
	}()

	ln := <-lnCh
	resp, err := http.Get("http://" + ln.Addr().String() + "/items/1")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 404 {
		t.Fatalf("status %d, want 404 for a missing item", resp.StatusCode)
	}

	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("shutdown returned %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("Run did not return after cancel")
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestRunFailures(t *testing.T) {
	ctx := context.Background()

	if err := Run(ctx, Deps{Getenv: getenv(map[string]string{"PORT": "x"})}); err == nil || !strings.Contains(err.Error(), "PORT") {
		t.Fatalf("config error expected, got %v", err)
	}

	boom := errors.New("factory failed")
	if err := Run(ctx, Deps{Getenv: getenv(nil), Factory: factoryFor(nil, boom)}); !errors.Is(err, boom) {
		t.Fatalf("pool error expected, got %v", err)
	}

	mock, _ := pgxmock.NewPool()
	for i := 0; i < 10; i++ {
		mock.ExpectExec("SELECT pg_sleep").WillReturnResult(pgxmock.NewResult("SELECT", 1))
	}
	mock.ExpectClose()
	listenErr := errors.New("port busy")
	err := Run(ctx, Deps{
		Getenv:  getenv(nil),
		Factory: factoryFor(mock, nil),
		Listen:  func(string, string) (net.Listener, error) { return nil, listenErr },
	})
	if !errors.Is(err, listenErr) {
		t.Fatalf("listen error expected, got %v", err)
	}

	// A listener that is already closed makes Serve fail immediately.
	mock2, _ := pgxmock.NewPool()
	for i := 0; i < 10; i++ {
		mock2.ExpectExec("SELECT pg_sleep").WillReturnResult(pgxmock.NewResult("SELECT", 1))
	}
	mock2.ExpectClose()
	err = Run(ctx, Deps{
		Getenv:  getenv(nil),
		Factory: factoryFor(mock2, nil),
		Listen: func(n, a string) (net.Listener, error) {
			ln, e := loopback(n, a)
			if e == nil {
				ln.Close()
			}
			return ln, e
		},
	})
	if err == nil {
		t.Fatal("expected a Serve error for a closed listener")
	}
}
