#!/usr/bin/env python3
"""Pre-campaign checks on K6_SERVER (deployment plan §9 step 3). Writes preflight.json.

  python3 loadtest/runner/preflight.py --out results/c1/preflight.json [--with-service]

Measures: load-generator health (steal, memory, ulimit, k6 version), RTT/loss and bandwidth to the
SUT, SUT steal and clock offset, an optional 1-VU latency floor against a running service, and an
estimate of MAX_VUS from load-generator memory. Exit code 1 if a blocking problem is found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import common as c

try:
    import resource  # Unix only; the load generator is Linux
except ImportError:  # pragma: no cover
    resource = None

MB_PER_VU = float(os.environ.get("MB_PER_VU", "3"))  # k6: 1-5 MB per VU, ~2-3 MB for these scripts


def steal_sample(seconds: int = 5) -> dict | None:
    before = c.cpu_snapshot()
    time.sleep(seconds)
    return c.cpu_usage(before, c.cpu_snapshot())


def ping(host: str, count: int = 100) -> dict:
    if not shutil.which("ping"):
        return {"error": "ping not installed"}
    p = subprocess.run(["ping", "-c", str(count), "-i", "0.2", "-q", host], capture_output=True, text=True)
    loss = re.search(r"([\d.]+)% packet loss", p.stdout)
    rtt = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", p.stdout)
    if not loss:
        return {"error": (p.stdout + p.stderr).strip()[-200:] or "ping failed"}
    out = {"loss_pct": float(loss.group(1))}
    if rtt:
        out.update(rtt_min_ms=float(rtt.group(1)), rtt_avg_ms=float(rtt.group(2)),
                   rtt_max_ms=float(rtt.group(3)), rtt_mdev_ms=float(rtt.group(4)))
    return out


def iperf(host: str) -> dict:
    """TCP bandwidth LG→SUT and SUT→LG over 5 s each (iperf3 is installed by the provisioning)."""
    if not shutil.which("iperf3"):
        return {"error": "iperf3 not installed on the load generator"}
    if c.dry_sut():
        return {"skipped": "DRY_SUT"}
    c.sut("pkill iperf3 || true; nohup iperf3 -s -1 >/dev/null 2>&1 &", check=False, timeout=20)
    time.sleep(1)
    out = {}
    for name, extra in (("up_mbit", []), ("down_mbit", ["-R"])):
        if name == "down_mbit":
            c.sut("pkill iperf3 || true; nohup iperf3 -s -1 >/dev/null 2>&1 &", check=False, timeout=20)
            time.sleep(1)
        p = subprocess.run(["iperf3", "-c", host, "-t", "5", "-J", *extra], capture_output=True, text=True)
        try:
            out[name] = round(json.loads(p.stdout)["end"]["sum_received"]["bits_per_second"] / 1e6, 1)
        except (ValueError, KeyError):
            out[name] = None
            out["error"] = (p.stdout + p.stderr).strip()[-200:]
    c.sut("pkill iperf3 || true", check=False, timeout=20)
    return out


def sut_steal() -> float | None:
    res = c.sut("vmstat 1 6 | awk 'NR>3{s+=$NF; n++} END{printf \"%.1f\", s/n}'", check=False, timeout=30)
    try:
        return float(res.stdout) if res and res.returncode == 0 else None
    except ValueError:
        return None


def latency_floor(base_url: str, n: int = 200) -> dict:
    """Sequential GETs of one seeded row from this host: the best latency one VU can see."""
    url = f"{base_url}/items/1"
    times = []
    try:
        for _ in range(n):
            t0 = time.perf_counter()
            urllib.request.urlopen(url, timeout=5).read()
            times.append((time.perf_counter() - t0) * 1000)
    except OSError as e:
        return {"error": str(e)}
    times.sort()
    return {"requests": n, "p50_ms": round(statistics.median(times), 2), "p99_ms": round(times[int(n * 0.99) - 1], 2)}


def main(argv=None) -> int:
    c.load_sut_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--with-service", action="store_true", help="a stack is running: measure the 1-VU latency floor")
    a = ap.parse_args(argv)

    host = os.environ.get("SUT_HOST", "")
    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
    mem = c.mem_info()
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE) if resource else (None, None)
    report: dict = {
        "time": c.now_iso(), "git_sha": c.git_sha(), "k6": c.k6_version(os.environ.get("K6", "k6")),
        "lg": {"memory": mem, "steal": steal_sample(), "nofile_soft": soft, "python": sys.version.split()[0]},
        "sut_host_set": bool(host),
    }
    if mem:
        report["max_vus_estimate"] = int(0.85 * mem["total_mb"] / MB_PER_VU)
    if host:
        report["network"] = {"ping": ping(host), "iperf3": iperf(host)}
    report["sut"] = {"clock_offset_ms": c.sut_clock_offset_ms(), "steal_pct": sut_steal()}
    if a.with_service:
        report["latency_floor"] = latency_floor(base_url)

    problems, warnings = [], []
    if report["k6"] == "unknown":
        problems.append("k6 not found")
    if soft is not None and soft < 65535:
        problems.append(f"ulimit -n is {soft} (need >= 65535)")
    lg_steal = (report["lg"]["steal"] or {}).get("steal_pct")
    if lg_steal is not None and lg_steal > 5:
        problems.append(f"load generator steal {lg_steal}% > 5%")
    if (report["sut"]["steal_pct"] or 0) > 5:
        problems.append(f"SUT steal {report['sut']['steal_pct']}% > 5%")
    if lg_steal is not None and lg_steal > 2:
        warnings.append(f"load generator steal {lg_steal}% > 2%")
    rtt = (report.get("network", {}).get("ping") or {}).get("rtt_avg_ms")
    if rtt is not None and rtt > 2:
        warnings.append(f"RTT {rtt} ms > 2 ms: is the private network in use?")
    loss = (report.get("network", {}).get("ping") or {}).get("loss_pct")
    if loss:
        problems.append(f"packet loss {loss}%")
    report["problems"], report["warnings"] = problems, warnings

    c.write_json(a.out, report)
    print(json.dumps(report, indent=2))
    for w in warnings:
        c.log(f"WARNING: {w}")
    for p in problems:
        c.log(f"PROBLEM: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
