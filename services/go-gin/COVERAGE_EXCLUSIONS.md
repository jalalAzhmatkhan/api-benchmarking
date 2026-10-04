# Coverage exclusions: go-gin

| Path | Reason |
|---|---|
| `cmd/server/` | Bare process entrypoint (signal wiring + `os.Exit`). All logic is in `internal/app`, which is fully tested. Approved by the System Analyst role per `clean-architecture.md` |

The CI gate (`.github/workflows/ci-go-gin.yml`) filters `cmd/server/` out of the coverage profile and
requires `total: 100.0%` for everything else.
