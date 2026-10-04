// Command server is the bare process entrypoint; all logic lives in internal/app
// (excluded from the coverage gate, see COVERAGE_EXCLUSIONS.md).
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/app"
	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/infrastructure/postgres"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	err := app.Run(ctx, app.Deps{Getenv: os.Getenv, Factory: postgres.DefaultFactory, Listen: net.Listen})
	if err != nil {
		fmt.Fprintln(os.Stderr, "fatal:", err)
		os.Exit(1)
	}
}
