#!/usr/bin/env python3
"""Summarize a campaign into a table (markdown + CSV). Python 3 stdlib.

  python3 analysis/summarize.py results/c1 [--out results/c1/summary]

One row per (stack, scenario-think): VU*, status, latency and throughput at VU* (median of the
passing confirmation runs), API and DB CPU-ms per request, peak memory, and the bottleneck verdict
of the first failing level above VU* (what actually limited the stack).
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

COLUMNS = ["stack", "cell", "status", "vu_star", "p50_ms", "p95_ms", "p99_ms", "rps", "api_cpu_ms_per_req",
           "db_cpu_ms_per_req", "api_cores", "db_cores", "api_mem_mb", "db_mem_mb", "limit_vus", "limit_bound", "limit_reason"]


def jload(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def med(values):
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 3) if vals else None


def summarize_cell(cell_dir: Path) -> dict | None:
    result = jload(cell_dir / "result.json")
    if not result:
        return None
    star = result.get("vu_star", 0)
    levels = [json.loads(l) for l in (cell_dir / "levels.jsonl").read_text().splitlines()] if (cell_dir / "levels.jsonl").is_file() else []
    confirms = [l for l in levels if str(l.get("tag", "")).startswith("confirm") and l.get("vus") == star and l.get("verdict") == "PASS"]
    # the first failing level above VU* tells what limited the stack
    fails = sorted((l for l in levels if l.get("verdict") == "FAIL" and l.get("vus", 0) > star), key=lambda l: l["vus"])
    limit = jload(Path(fails[0]["dir"]) / "attribution.json") if fails and fails[0].get("dir") else None
    attrs = [jload(Path(l["dir"]) / "attribution.json", {}) for l in confirms if l.get("dir")]

    def metric(group, key):
        return med([(a.get("metrics", {}).get(group) or {}).get(key) for a in attrs])

    return {
        "stack": result.get("stack"), "cell": f"{result.get('scenario')}-{result.get('think')}",
        "status": result.get("status"), "vu_star": star,
        "p50_ms": med([l.get("p50") for l in confirms]), "p95_ms": med([l.get("p95") for l in confirms]),
        "p99_ms": med([l.get("p99") for l in confirms]), "rps": med([l.get("rps") for l in confirms]),
        "api_cpu_ms_per_req": metric("api", "cpu_ms_per_request"), "db_cpu_ms_per_req": metric("db", "cpu_ms_per_request"),
        "api_cores": metric("api", "cpu_cores"), "db_cores": metric("db", "cpu_cores"),
        "api_mem_mb": metric("api", "mem_peak_mb"), "db_mem_mb": metric("db", "mem_peak_mb"),
        "limit_vus": fails[0]["vus"] if fails else None,
        "limit_bound": limit.get("verdict") if limit else None,
        "limit_reason": "; ".join(limit.get("reasons", [])) if limit else None,
    }


def collect(campaign: Path) -> list[dict]:
    rows = []
    for result in sorted(campaign.glob("*/*/result.json")):
        row = summarize_cell(result.parent)
        if row:
            rows.append(row)
    return rows


def to_markdown(rows: list[dict]) -> str:
    head = ["Stack", "Cell", "Status", "VU*", "p50 ms", "p95 ms", "p99 ms", "req/s", "API cpu-ms/req", "DB cpu-ms/req", "Limited by"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        lines.append("| " + " | ".join(str("" if v is None else v) for v in (
            r["stack"], r["cell"], r["status"], r["vu_star"], r["p50_ms"], r["p95_ms"], r["p99_ms"],
            round(r["rps"]) if r["rps"] else "", r["api_cpu_ms_per_req"], r["db_cpu_ms_per_req"], r["limit_bound"])) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--out", type=Path, help="write <out>.md and <out>.csv")
    a = ap.parse_args(argv)
    rows = collect(a.campaign)
    md = to_markdown(rows)
    print(md)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        Path(str(a.out) + ".md").write_text(md)
        with open(str(a.out) + ".csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
