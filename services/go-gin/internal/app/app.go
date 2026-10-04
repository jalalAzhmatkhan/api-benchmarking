// Package app is the composition root: configuration → pool → repository → use cases → HTTP server.
package app

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"time"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/application"
	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/infrastructure/config"
	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/infrastructure/postgres"
	httpapi "github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/interfaces/http"
)

// Deps are the process-level collaborators; tests replace them.
type Deps struct {
	Getenv  func(string) string
	Factory postgres.Factory
	Listen  func(network, address string) (net.Listener, error)
}

// Run starts the service and blocks until ctx is cancelled (graceful shutdown) or the server fails.
func Run(ctx context.Context, d Deps) error {
	cfg, err := config.Load(d.Getenv)
	if err != nil {
		return err
	}
	pool, err := postgres.NewPool(ctx, cfg.DatabaseURL, cfg.PoolSize, d.Factory)
	if err != nil {
		return err
	}
	defer pool.Close()

	repo := postgres.NewItemRepository(pool)
	router := httpapi.NewRouter(httpapi.Handler{
		Get:     application.GetItem{Repo: repo},
		Create:  application.CreateItem{Repo: repo},
		Replace: application.ReplaceItem{Repo: repo},
		Delete:  application.DeleteItem{Repo: repo},
	})

	ln, err := d.Listen("tcp", ":"+cfg.Port)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}
	srv := &http.Server{Handler: router}
	serveErr := make(chan error, 1)
	go func() { serveErr <- srv.Serve(ln) }()

	select {
	case err := <-serveErr:
		return err
	case <-ctx.Done():
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return srv.Shutdown(shutdownCtx)
}
