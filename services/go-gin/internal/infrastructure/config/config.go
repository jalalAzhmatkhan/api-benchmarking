// Package config loads the runtime configuration contract shared by all services
// (contract/README.md): DATABASE_URL, PORT and DB_POOL_SIZE.
package config

import (
	"fmt"
	"strconv"
)

// DefaultDatabaseURL matches deploy/compose.dev.yaml.
const DefaultDatabaseURL = "postgres://bench:bench@127.0.0.1:5432/bench"

// Config is the service configuration.
type Config struct {
	DatabaseURL string
	Port        string
	PoolSize    int
}

// Load reads the configuration through getenv (os.Getenv in production).
func Load(getenv func(string) string) (Config, error) {
	c := Config{DatabaseURL: getenv("DATABASE_URL"), Port: getenv("PORT"), PoolSize: 10}
	if c.DatabaseURL == "" {
		c.DatabaseURL = DefaultDatabaseURL
	}
	if c.Port == "" {
		c.Port = "8080"
	}
	if p, err := strconv.Atoi(c.Port); err != nil || p < 1 || p > 65535 {
		return Config{}, fmt.Errorf("invalid PORT %q", c.Port)
	}
	if v := getenv("DB_POOL_SIZE"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 {
			return Config{}, fmt.Errorf("invalid DB_POOL_SIZE %q", v)
		}
		c.PoolSize = n
	}
	return c, nil
}
