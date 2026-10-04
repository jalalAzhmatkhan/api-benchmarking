"""Shared helpers for the benchmark runner (stdlib only; runs on K6_SERVER, Python 3.12)."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parent
LOADTEST_DIR = RUNNER_DIR.parent
REPO_DIR = LOADTEST_DIR.parent
SCENARIOS = {
    "s1": "s1-user-journey.js",
    "s2": "s2-read-heavy.js",
    "s3": "s3-get-only.js",
}
THINKS = ("T0", "T1")
STACKS = ("python-fastapi", "node-fastify", "java-springboot", "csharp-dotnet", "go-gin", "rust-axum")


def load_sut_env(path: str = "/etc/bench/sut.env") -> None:
    """Fill os.environ defaults from the file written by deploy/provision (SUT_HOST, BASE_URL)."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


# ---- SUT access ---------------------------------------------------------------------------
def dry_sut() -> bool:
    return os.environ.get("DRY_SUT", "0") == "1"


def bench_dir() -> str:
    return os.environ.get("SUT_BENCH_DIR", "/opt/bench")


def sut(command: str, check: bool = True, timeout: int = 900) -> subprocess.CompletedProcess | None:
    """Run a shell command on the SUT through the `sut` ssh alias (DRY_SUT=1 skips it)."""
    if dry_sut():
        return None
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "sut", command],
        check=check, capture_output=True, text=True, timeout=timeout,
    )


def hook(name: str, default: str, **fmt) -> str:
    """A SUT command that can be overridden by an environment variable of the same name."""
    return os.environ.get(name, default).format(bench=bench_dir(), **{k: shlex.quote(str(v)) for k, v in fmt.items()})


def sut_clock_offset_ms() -> float | None:
    """SUT clock minus local clock in ms, compensating for half the ssh round trip."""
    if dry_sut():
        return None
    t0 = time.time()
    res = sut("date +%s%3N", check=False, timeout=15)
    t1 = time.time()
    if not res or res.returncode != 0:
        return None
    try:
        remote = int(res.stdout.strip())
    except ValueError:
        return None
    return round(remote - ((t0 + t1) / 2) * 1000, 1)


# ---- load-generator health (Linux only; None elsewhere) -------------------------------------
def cpu_snapshot() -> tuple[int, int, int] | None:
    try:
        with open("/proc/stat") as f:
            fields = [int(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    steal = fields[7] if len(fields) > 7 else 0
    total = sum(fields[:8])
    return total - idle, total, steal  # busy, total, steal


def cpu_usage(before, after) -> dict | None:
    if not before or not after or after[1] == before[1]:
        return None
    d_total = after[1] - before[1]
    return {
        "cpu_pct": round(100.0 * (after[0] - before[0]) / d_total, 1),
        "steal_pct": round(100.0 * (after[2] - before[2]) / d_total, 1),
    }


def mem_info() -> dict | None:
    try:
        kv = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                kv[k] = int(v.split()[0])  # kB
        return {
            "total_mb": kv["MemTotal"] // 1024,
            "available_mb": kv["MemAvailable"] // 1024,
            "used_pct": round(100.0 * (1 - kv["MemAvailable"] / kv["MemTotal"]), 1),
        }
    except (OSError, ValueError, KeyError):
        return None


def git_sha() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def k6_version(k6: str) -> str:
    try:
        return subprocess.run([k6, "version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    except (OSError, subprocess.CalledProcessError, IndexError):
        return "unknown"
