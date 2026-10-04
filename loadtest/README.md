# loadtest/: k6 load tests

Plan: `Documentation/plans/k6-test-plan.md`. Tool: Grafana k6 2.3 (v2 API), run from **K6_SERVER**.

| Path | Purpose |
|---|---|
| `lib/` | `config.js` (env), `api.js` (tags, expected statuses, failure classification, phase tag), `journeys.js` (S1/S2/S3), `payloads.js` (seeded PRNG), `think.js` (T0/T1), `options.js` (single-VU-pool options, SLO thresholds, summary) |
| `scenarios/` | `s1-user-journey.js` (primary), `s2-read-heavy.js`, `s3-get-only.js`, `open-model-validate.js` |
| `runner/` | Python (stdlib) driver: `runlevel.py`, `search.py`, `campaign.py`, `preflight.py` (added next to the scenarios, same Phase 3) |

## One level
```bash
k6 run -e BASE_URL=http://127.0.0.1:8080 -e VUS=100 -e THINK=T0 -e WARMUP_S=60 -e MEASURE_S=120 \
       -e SCENARIO_NAME=s1 -e SUMMARY_PATH=summary.json -e RESULT_PATH=result.json \
       loadtest/scenarios/s1-user-journey.js
```
Exit code `0` = PASS, `99` = a threshold failed (SLO breach, any failed request or failed check).

| Env | Default | Meaning |
|---|---|---|
| `VUS` | 10 | concurrent virtual users (one pool; ramp ≤ 15 s inside the warm-up) |
| `THINK` | `T0` | `T0` no think time · `T1` uniform 0.5–1.5 s after every step |
| `WARMUP_S` / `MEASURE_S` | 60 / 120 | warm-up (failures count, latency does not) / measure phase |
| `SEED` / `SEED_ROWS` | 1 / 100000 | payload PRNG seed / seeded rows (`db/seed/seed.sql`) |
| `SLO_MS` | 1000 | p50, p95 and p99 limit |

Local try-out against the contract mock:
```bash
SEED_ROWS=100000 PORT=18080 python contract/mock/server.py &
k6 run -e BASE_URL=http://127.0.0.1:18080 -e VUS=5 -e WARMUP_S=3 -e MEASURE_S=5 loadtest/scenarios/s1-user-journey.js
```
