# loadtest/: k6 load tests

Plan: `Documentation/plans/k6-test-plan.md`. Tool: Grafana k6 2.3 (v2 API), run from **K6_SERVER**.

| Path | Purpose |
|---|---|
| `lib/` | `config.js` (env), `api.js` (tags, expected statuses, failure classification, phase tag), `journeys.js` (S1/S2/S3), `payloads.js` (seeded PRNG), `think.js` (T0/T1), `options.js` (single-VU-pool options, SLO thresholds, summary) |
| `scenarios/` | `s1-user-journey.js` (primary), `s2-read-heavy.js`, `s3-get-only.js`, `open-model-validate.js` |
| `runner/` | Python 3 (stdlib only) driver, runs on K6_SERVER: `common.py`, `runlevel.py` (one level), `search.py` (VU search), `campaign.py` (matrix, seeded stack order), `preflight.py`, `test_runner.py` |

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

## Runner
```bash
python3 loadtest/runner/preflight.py --out results/c1/preflight.json
python3 loadtest/runner/campaign.py --name c1 --matrix S1-T0,S1-T1,S2-T0 --seed 20261004 --dry-run   # show the plan
tmux new -s bench 'python3 loadtest/runner/campaign.py --name c1 --matrix S1-T0,S1-T1,S2-T0 --seed 20261004'
python3 loadtest/runner/search.py --stack go-gin --scenario s1 --think T0 --out results/c1/go-gin/s1-T0   # one search
python3 loadtest/runner/runlevel.py --stack go-gin --scenario s1 --vus 100 --out /tmp/level              # one level
python3 -m unittest discover -s loadtest/runner -p 'test_*.py'
```
- **Verdicts per level:** `PASS`, `FAIL` (server), `LG-BOUND` (k6 failed while the load generator had > 80 % CPU, > 85 % RAM or > 5 % steal; re-run once, then the search stops with `LIMITED-BY-LOADGEN`), `ERROR`.
- **Search result** (`result.json`): `status` `OK | CAPPED | BELOW-MINIMUM | UNSTABLE | LIMITED-BY-LOADGEN`, `vu_star`, every level run. Re-running resumes from `levels.jsonl`.
- **SUT hooks** (ssh alias `sut`, set up by *Provision VMs*): `SUT_RESET_CMD` (default `DB_CONTAINER=bench-postgres /opt/bench/db/reset.sh`), `SUT_RESTART_CMD`/`SUT_STACK_START`/`SUT_STACK_STOP` (`/opt/bench/deploy/stack.sh`, Phase 5 T-5.3) and `SAMPLER=1` + `SUT_SAMPLER_START/STOP` (`/opt/bench/monitoring/sampler.sh`, Phase 4 T-4.1). `DRY_SUT=1` skips every SUT call (local runs, CI).
