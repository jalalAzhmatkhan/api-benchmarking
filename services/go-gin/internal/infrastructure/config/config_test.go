package config

import "testing"

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestLoadDefaults(t *testing.T) {
	c, err := Load(env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if c.DatabaseURL != DefaultDatabaseURL || c.Port != "8080" || c.PoolSize != 10 {
		t.Fatalf("unexpected defaults: %+v", c)
	}
}

func TestLoadOverrides(t *testing.T) {
	c, err := Load(env(map[string]string{"DATABASE_URL": "postgres://x", "PORT": "9000", "DB_POOL_SIZE": "20"}))
	if err != nil {
		t.Fatal(err)
	}
	if c.DatabaseURL != "postgres://x" || c.Port != "9000" || c.PoolSize != 20 {
		t.Fatalf("unexpected config: %+v", c)
	}
}

func TestLoadInvalid(t *testing.T) {
	for name, m := range map[string]map[string]string{
		"port text":      {"PORT": "abc"},
		"port zero":      {"PORT": "0"},
		"port too large": {"PORT": "70000"},
		"pool text":      {"DB_POOL_SIZE": "ten"},
		"pool zero":      {"DB_POOL_SIZE": "0"},
	} {
		if _, err := Load(env(m)); err == nil {
			t.Errorf("%s: expected an error", name)
		}
	}
}
