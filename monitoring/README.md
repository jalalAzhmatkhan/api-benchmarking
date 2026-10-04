# monitoring/: resource samplers

Plan: `Documentation/plans/monitoring-plan.md`. One Python 3 stdlib script, no agents or exporters
(nothing heavy runs on the 2-vCPU SUT).

```bash
python3 monitoring/sampler.py start <run_id> --mode sut --containers api=bench-api,db=bench-postgres   # on the SUT
python3 monitoring/sampler.py start <run_id> --mode lg                                                   # on K6_SERVER
python3 monitoring/sampler.py stop  <run_id>
```
Output `/var/lib/bench/runs/<run_id>/` (override with `--dir`), 1 row per second, epoch-ms `ts_ms`, cumulative counters:

| File | Content |
|---|---|
| `host.csv` | `/proc/stat` jiffies (total + per CPU, incl. **steal**), memory, NIC bytes, `ListenOverflows/Drops`, TCP retransmits, host PSI, disk writes, load, `sampler_cpu_s` (own CPU time) |
| `api.csv`, `db.csv` | container cgroup v2: `usage_usec`, throttling, **CPU/memory PSI**, `memory.current/peak/max`, anon/file, `oom_kill`, pids |
| `pg.csv` | `pg_stat_activity` states and wait events of the `bench` role, `pg_stat_database` counters (via the persistent `monitor` role session) |
| `k6.csv` (lg mode) | CPU ticks, threads and RSS of the k6 process |

The runner starts and stops both samplers per level when `SAMPLER=1` and pulls the SUT files into
`<level>/sampler-sut/` (the LG's are written to `<level>/sampler-lg/`). Tests: `python3 -m unittest discover -s monitoring`.
