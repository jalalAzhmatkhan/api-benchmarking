#!/usr/bin/env python3
"""Bottleneck attribution for one level (monitoring plan §3-§4). Python 3 stdlib.

  python3 analysis/attribute.py <level_dir> [--pool 10] [--nic-mbit N]

Reads <level_dir>/{meta.json,result.json,sampler-sut/*.csv,sampler-lg/*.csv}, restricts to the
measure phase, derives metrics and applies the decision list in order (first match wins).
Writes <level_dir>/attribution.json and prints the verdict.

Verdicts: INVALID, LG-BOUND, NETWORK-BOUND, MEMORY-BOUND, HOST-CPU:API, HOST-CPU:DB, HOST-CPU:SHARED,
DB-LOCK-IO-BOUND, POOL-BOUND, API-RUNTIME-BOUND, NO-DATA.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# thresholds, monitoring plan §4
STEAL_INVALID = 5.0
MISSING_INVALID = 2.0
LG_CPU, LG_MEM = 80.0, 85.0
NIC_FRACTION = 0.80
HOST_SATURATED = 90.0
SHARE_DOMINANT = 60.0
IDLE_HOST = 75.0
NET_FAIL_HOST = 70.0
WAIT_FRACTION = 0.30
POOL_SAMPLE_FRACTION = 0.80
MEM_LIMIT_FRACTION = 95.0
MEM_PSI = 10.0
WARMUP_GUARD_S = 2  # skip the first seconds after the warm-up while k6 settles


def load_csv(path: Path) -> list[dict]:
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def window(rows: list[dict], t0: int, t1: int) -> list[dict]:
    return [r for r in rows if t0 <= int(r["ts_ms"]) <= t1]


def delta(rows: list[dict], col: str) -> float:
    return num(rows[-1].get(col)) - num(rows[0].get(col)) if len(rows) >= 2 else 0.0


def span_s(rows: list[dict]) -> float:
    return (int(rows[-1]["ts_ms"]) - int(rows[0]["ts_ms"])) / 1000 if len(rows) >= 2 else 0.0


def mean(rows: list[dict], col: str) -> float:
    vals = [num(r.get(col)) for r in rows if r.get(col) not in (None, "")]
    return sum(vals) / len(vals) if vals else 0.0


def host_metrics(rows: list[dict]) -> dict:
    if len(rows) < 2:
        return {}
    names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
    d = {n: delta(rows, f"cpu_{n}") for n in names}
    total = sum(d.values()) or 1.0
    ncpu = len([k for k in rows[0] if k.startswith("cpu") and k.endswith("_total") and k != "cpu_total"]) or 1
    t = span_s(rows)
    return {
        "ncpu": ncpu,
        "busy_pct": round(100.0 * (total - d["idle"] - d["iowait"]) / total, 2),
        "steal_pct": round(100.0 * d["steal"] / total, 2),
        "mem_used_pct": round(100.0 * (1 - num(rows[-1].get("mem_available_kb")) / max(num(rows[-1].get("mem_total_kb")), 1)), 1),
        "net_mbit": round((delta(rows, "net_rx_bytes") + delta(rows, "net_tx_bytes")) * 8 / 1e6 / t, 2) if t else 0.0,
        "listen_overflows": delta(rows, "listen_overflows") + delta(rows, "listen_drops"),
        "retransmits": delta(rows, "tcp_retrans_segs"),
        "psi_cpu_some_avg10": round(mean(rows, "psi_cpu_some_avg10"), 2),
        "sampler_overhead_pct": round(100.0 * delta(rows, "sampler_cpu_s") / t, 2) if t else 0.0,
        "samples": len(rows),
    }


def container_metrics(rows: list[dict], requests: float | None) -> dict:
    if len(rows) < 2:
        return {}
    t = span_s(rows)
    cpu_s = delta(rows, "usage_usec") / 1e6
    limit = rows[-1].get("memory_max", "")
    limit_b = int(limit) if str(limit).isdigit() else None
    peak_b = max(num(r.get("memory_current")) for r in rows)
    periods = delta(rows, "nr_periods")
    out = {
        "cpu_cores": round(cpu_s / t, 3) if t else 0.0,
        "cpu_s": round(cpu_s, 3),
        "cpu_pressure_some_avg10": round(mean(rows, "cpu_some_avg10"), 2),
        "mem_pressure_some_avg10": round(mean(rows, "mem_some_avg10"), 2),
        "mem_peak_mb": round(peak_b / 1048576, 1),
        "mem_limit_pct": round(100.0 * peak_b / limit_b, 1) if limit_b else None,
        "oom_kills": delta(rows, "oom_kill"),
        "throttle_ratio": round(delta(rows, "nr_throttled") / periods, 3) if periods else 0.0,
        "samples": len(rows),
    }
    if requests:
        out["cpu_ms_per_request"] = round(cpu_s * 1000 / requests, 4)
    return out


def pg_metrics(rows: list[dict], pool: int) -> dict:
    if len(rows) < 2:
        return {}
    t = span_s(rows)
    waits = [num(r.get("wait_lock")) + num(r.get("wait_lwlock")) + num(r.get("wait_io")) for r in rows]
    active = [num(r.get("active")) for r in rows]
    hit, read = delta(rows, "blks_hit"), delta(rows, "blks_read")
    return {
        "active_mean": round(sum(active) / len(active), 2),
        "idle_mean": round(mean(rows, "idle"), 2),
        "idle_in_txn_mean": round(mean(rows, "idle_in_txn"), 2),
        "samples_at_pool_max": round(sum(1 for a in active if a >= pool - 1) / len(active), 3),
        "wait_fraction": round(sum(waits) / max(sum(active), 1.0), 3),
        "commits_per_s": round(delta(rows, "xact_commit") / t, 1) if t else 0.0,
        "rollbacks": delta(rows, "xact_rollback"),
        "cache_hit_ratio": round(hit / (hit + read), 4) if (hit + read) else None,
        "deadlocks": delta(rows, "deadlocks"),
        "temp_bytes": delta(rows, "temp_bytes"),
        "samples": len(rows),
    }


def lg_metrics(host: list[dict], k6: list[dict]) -> dict:
    out = host_metrics(host)
    if len(k6) >= 2:
        t = span_s(k6)
        ticks = delta(k6, "utime_ticks") + delta(k6, "stime_ticks")
        out["k6_cpu_cores"] = round(ticks / 100.0 / t, 2) if t else 0.0  # CLK_TCK = 100
        out["k6_rss_mb"] = round(max(num(r.get("rss_kb")) for r in k6) / 1024, 1)
    return out


def decide(m: dict, *, pool: int, nic_mbit: float | None, failures: dict, expected_samples: float) -> tuple[str, list[str]]:
    sut, api, db, pg, lg = m.get("host", {}), m.get("api", {}), m.get("db", {}), m.get("pg", {}), m.get("lg", {})
    if not sut or not api or not db:
        return "NO-DATA", ["host/api/db sampler data missing"]
    why: list[str] = []

    # 1. INVALID
    missing = max(0.0, max(100.0 * (1 - c["samples"] / expected_samples) for c in (sut, api, db))) if expected_samples else 0.0
    if sut["steal_pct"] > STEAL_INVALID:
        return "INVALID", [f"SUT steal {sut['steal_pct']}% > {STEAL_INVALID}%"]
    if missing > MISSING_INVALID:
        return "INVALID", [f"{missing:.1f}% of expected samples missing"]

    # 2. LG-BOUND
    if lg:
        if lg.get("busy_pct", 0) > LG_CPU or lg.get("mem_used_pct", 0) > LG_MEM or lg.get("steal_pct", 0) > STEAL_INVALID:
            return "LG-BOUND", [f"load generator cpu {lg.get('busy_pct')}% mem {lg.get('mem_used_pct')}% steal {lg.get('steal_pct')}%"]

    # 3. NETWORK-BOUND
    if nic_mbit and sut["net_mbit"] >= NIC_FRACTION * nic_mbit:
        return "NETWORK-BOUND", [f"SUT NIC {sut['net_mbit']} Mbit/s >= {NIC_FRACTION:.0%} of {nic_mbit}"]
    transport = failures.get("transport", 0) + failures.get("timeout", 0)
    if transport and sut["busy_pct"] < NET_FAIL_HOST and sut["listen_overflows"] == 0:
        return "NETWORK-BOUND", [f"{transport} transport/timeout failures while SUT cpu {sut['busy_pct']}% and no listen overflows"]

    # 4. MEMORY-BOUND
    for name, c in (("api", api), ("db", db)):
        if c.get("oom_kills", 0) > 0 or (c.get("mem_limit_pct") or 0) >= MEM_LIMIT_FRACTION or c.get("mem_pressure_some_avg10", 0) > MEM_PSI:
            return "MEMORY-BOUND", [f"{name}: oom={c.get('oom_kills')} peak={c.get('mem_peak_mb')} MB ({c.get('mem_limit_pct')}% of limit) psi={c.get('mem_pressure_some_avg10')}"]

    # 5-7. host CPU saturated: who consumes it
    busy_cores = api["cpu_cores"] + db["cpu_cores"]
    api_share = 100.0 * api["cpu_cores"] / busy_cores if busy_cores else 0.0
    db_share = 100.0 - api_share if busy_cores else 0.0
    why.append(f"host cpu {sut['busy_pct']}%, api {api['cpu_cores']} cores ({api_share:.0f}%), db {db['cpu_cores']} cores ({db_share:.0f}%)")
    if sut["busy_pct"] >= HOST_SATURATED:
        if api_share >= SHARE_DOMINANT:
            return "HOST-CPU:API", why
        if db_share >= SHARE_DOMINANT:
            return "HOST-CPU:DB", why
        return "HOST-CPU:SHARED", why

    # 8. DB locks / IO
    if sut["busy_pct"] < IDLE_HOST and pg and pg["wait_fraction"] >= WAIT_FRACTION:
        return "DB-LOCK-IO-BOUND", why + [f"{pg['wait_fraction']:.0%} of active backends wait on Lock/LWLock/IO"]

    # 9. pool
    if sut["busy_pct"] < IDLE_HOST and pg and pg["samples_at_pool_max"] >= POOL_SAMPLE_FRACTION:
        return "POOL-BOUND", why + [f"active backends >= {pool - 1} in {pg['samples_at_pool_max']:.0%} of samples"]

    # 10. everything else: the API runtime (event loop, thread pool, per-process imbalance, accept queue)
    return "API-RUNTIME-BOUND", why + [f"host cpu below {IDLE_HOST:.0f}% and no DB or pool saturation"]


def analyze(level_dir: Path, pool: int = 10, nic_mbit: float | None = None) -> dict:
    meta = json.loads((level_dir / "meta.json").read_text()) if (level_dir / "meta.json").is_file() else {}
    result = json.loads((level_dir / "result.json").read_text()) if (level_dir / "result.json").is_file() else {}
    sut_dir, lg_dir = level_dir / "sampler-sut", level_dir / "sampler-lg"
    if not meta.get("k6_started_ms") or not (sut_dir / "host.csv").is_file():
        return {"verdict": "NO-DATA", "reasons": ["no sampler data for this level"], "metrics": {}}

    t0 = meta["k6_started_ms"] + (meta.get("warmup_s", 60) + WARMUP_GUARD_S) * 1000
    t1 = min(meta.get("k6_finished_ms", 1 << 62), t0 + (meta.get("measure_s", 120) - WARMUP_GUARD_S) * 1000)
    reqs = result.get("requests_measure")
    metrics = {
        "window": {"start_ms": t0, "end_ms": t1, "seconds": round((t1 - t0) / 1000, 1)},
        "host": host_metrics(window(load_csv(sut_dir / "host.csv"), t0, t1)),
        "api": container_metrics(window(load_csv(sut_dir / "api.csv"), t0, t1), reqs),
        "db": container_metrics(window(load_csv(sut_dir / "db.csv"), t0, t1), reqs),
        "pg": pg_metrics(window(load_csv(sut_dir / "pg.csv"), t0, t1), pool),
        "lg": lg_metrics(window(load_csv(lg_dir / "host.csv"), t0, t1), window(load_csv(lg_dir / "k6.csv"), t0, t1)),
        "requests_measure": reqs,
    }
    expected = (t1 - t0) / 1000
    verdict, reasons = decide(metrics, pool=pool, nic_mbit=nic_mbit, failures=result.get("failures_by_type") or {},
                              expected_samples=expected)
    out = {"verdict": verdict, "reasons": reasons, "metrics": metrics, "k6_verdict": meta.get("verdict"), "vus": meta.get("vus")}
    (level_dir / "attribution.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level_dir", type=Path)
    ap.add_argument("--pool", type=int, default=10)
    ap.add_argument("--nic-mbit", type=float, default=None, help="iperf3 baseline from preflight.json")
    a = ap.parse_args(argv)
    out = analyze(a.level_dir, a.pool, a.nic_mbit)
    print(f"{out['verdict']}: " + "; ".join(out["reasons"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
