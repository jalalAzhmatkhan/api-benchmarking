#!/usr/bin/env python3
"""1 Hz resource sampler (Python 3 stdlib, Linux, cgroup v2). Monitoring plan §2.

  sampler.py start <run_id> --mode sut|lg [--containers api=bench-api,db=bench-postgres] [--dir DIR]
  sampler.py stop  <run_id> [--dir DIR]
  sampler.py run   <run_id> ...        # foreground loop (what `start` launches detached)

Writes <dir>/<run_id>/{host,api,db,pg,k6}.csv, one row per second, epoch-ms timestamps. All
counters are CUMULATIVE (deltas are computed by analysis/). `host.csv` carries `sampler_cpu_s`
(the sampler's own CPU time) so the overhead can be verified (< 1 %).

sut mode: host + one CSV per container (cgroup cpu/memory/PSI/pids) + pg.csv (pg_stat_activity
          states/wait events and pg_stat_database counters through a persistent `monitor` session).
lg  mode: host + k6.csv (CPU ticks and RSS of the k6 process).
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

PROC = Path(os.environ.get("SAMPLER_PROC", "/proc"))
CGROUP = Path(os.environ.get("SAMPLER_CGROUP", "/sys/fs/cgroup"))
DEFAULT_DIR = "/var/lib/bench/runs"
END = "--END--"

PG_QUERY = (
    "SELECT "
    "count(*) FILTER (WHERE a.state='active'), "
    "count(*) FILTER (WHERE a.state='idle'), "
    "count(*) FILTER (WHERE a.state='idle in transaction'), "
    "count(*) FILTER (WHERE a.state='active' AND a.wait_event_type='Lock'), "
    "count(*) FILTER (WHERE a.state='active' AND a.wait_event_type='LWLock'), "
    "count(*) FILTER (WHERE a.state='active' AND a.wait_event_type='IO'), "
    "count(*) FILTER (WHERE a.state='active' AND a.wait_event_type='Client'), "
    "count(*) FILTER (WHERE a.state='active' AND a.wait_event_type IS NOT NULL "
    "AND a.wait_event_type NOT IN ('Lock','LWLock','IO','Client')), "
    "(SELECT xact_commit FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT xact_rollback FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT blks_read FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT blks_hit FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT tup_returned FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT tup_fetched FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT tup_inserted FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT tup_updated FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT tup_deleted FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT deadlocks FROM pg_stat_database WHERE datname='bench'), "
    "(SELECT temp_bytes FROM pg_stat_database WHERE datname='bench') "
    "FROM pg_stat_activity a WHERE a.usename='bench' AND a.backend_type='client backend';"
)
PG_COLUMNS = ["active", "idle", "idle_in_txn", "wait_lock", "wait_lwlock", "wait_io", "wait_client", "wait_other",
              "xact_commit", "xact_rollback", "blks_read", "blks_hit", "tup_returned", "tup_fetched",
              "tup_inserted", "tup_updated", "tup_deleted", "deadlocks", "temp_bytes"]


# ---- parsers (pure functions, unit-tested) ---------------------------------------------------
def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def parse_keyed(text: str | None) -> dict[str, int]:
    """'usage_usec 123\\nuser_usec 4' -> {'usage_usec': 123, 'user_usec': 4}."""
    out: dict[str, int] = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            out[parts[0]] = int(parts[1])
    return out


def parse_psi(text: str | None) -> dict[str, float]:
    """'some avg10=0.12 avg60=.. avg300=.. total=999\\nfull ...' -> some_avg10, some_total, full_avg10, full_total."""
    out: dict[str, float] = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if not parts or parts[0] not in ("some", "full"):
            continue
        kv = dict(p.split("=") for p in parts[1:] if "=" in p)
        out[f"{parts[0]}_avg10"] = float(kv.get("avg10", 0))
        out[f"{parts[0]}_total"] = float(kv.get("total", 0))
    return out


def parse_proc_stat(text: str | None) -> dict[str, int]:
    """Cumulative jiffies: cpu_* for the total line and cpuN_busy / cpuN_total for each CPU."""
    out: dict[str, int] = {}
    names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
    for line in (text or "").splitlines():
        parts = line.split()
        if not parts or not parts[0].startswith("cpu"):
            continue
        vals = [int(x) for x in parts[1:9]] + [0] * (8 - len(parts[1:9]))
        if parts[0] == "cpu":
            out.update({f"cpu_{n}": v for n, v in zip(names, vals)})
        else:
            total = sum(vals)
            out[f"{parts[0]}_busy"] = total - vals[3] - vals[4]
            out[f"{parts[0]}_total"] = total
    return out


def parse_meminfo(text: str | None) -> dict[str, int]:
    kv = {}
    for line in (text or "").splitlines():
        k, _, v = line.partition(":")
        if v.split():
            kv[k] = int(v.split()[0])
    return {"mem_total_kb": kv.get("MemTotal", 0), "mem_available_kb": kv.get("MemAvailable", 0),
            "swap_free_kb": kv.get("SwapFree", 0)}


def parse_net_dev(text: str | None) -> dict[str, int]:
    rx = tx = 0
    for line in (text or "").splitlines()[2:]:
        name, _, rest = line.partition(":")
        f = rest.split()
        if name.strip() != "lo" and len(f) >= 9:
            rx, tx = rx + int(f[0]), tx + int(f[8])
    return {"net_rx_bytes": rx, "net_tx_bytes": tx}


def parse_netstat(text: str | None) -> dict[str, int]:
    """/proc/net/netstat: pairs of header/value lines; keep the listen-queue and retransmit counters."""
    lines = (text or "").splitlines()
    want = {"ListenOverflows": "listen_overflows", "ListenDrops": "listen_drops", "TCPTimeouts": "tcp_timeouts"}
    out = {v: 0 for v in want.values()}
    for head, vals in zip(lines[::2], lines[1::2]):
        if not head.startswith("TcpExt:"):
            continue
        for k, v in zip(head.split()[1:], vals.split()[1:]):
            if k in want:
                out[want[k]] = int(v)
    return out


def parse_snmp_retrans(text: str | None) -> int:
    lines = (text or "").splitlines()
    for head, vals in zip(lines[::2], lines[1::2]):
        if head.startswith("Tcp:"):
            d = dict(zip(head.split()[1:], vals.split()[1:]))
            return int(d.get("RetransSegs", 0))
    return 0


def parse_diskstats(text: str | None) -> dict[str, int]:
    writes = write_ms = 0
    for line in (text or "").splitlines():
        f = line.split()
        if len(f) >= 14 and re.fullmatch(r"(vd[a-z]+|sd[a-z]+|xvd[a-z]+|nvme\d+n\d+)", f[2]):
            writes, write_ms = writes + int(f[7]), write_ms + int(f[10])
    return {"disk_writes": writes, "disk_write_ms": write_ms}


# ---- collectors ------------------------------------------------------------------------------
def host_row() -> dict:
    row: dict = {}
    row.update(parse_proc_stat(read(PROC / "stat")))
    row.update(parse_meminfo(read(PROC / "meminfo")))
    row.update(parse_net_dev(read(PROC / "net/dev")))
    row.update(parse_netstat(read(PROC / "net/netstat")))
    row["tcp_retrans_segs"] = parse_snmp_retrans(read(PROC / "net/snmp"))
    row.update({f"psi_cpu_{k}": v for k, v in parse_psi(read(PROC / "pressure/cpu")).items()})
    row.update({f"psi_mem_{k}": v for k, v in parse_psi(read(PROC / "pressure/memory")).items()})
    row.update(parse_diskstats(read(PROC / "diskstats")))
    la = (read(PROC / "loadavg") or "0 0 0").split()
    row["load1"] = la[0]
    row["sampler_cpu_s"] = round(time.process_time(), 4)
    return row


def container_cgroup(cid: str) -> Path | None:
    for pattern in (f"system.slice/docker-{cid}.scope", f"docker/{cid}"):
        p = CGROUP / pattern
        if p.is_dir():
            return p
    return None


def cgroup_row(cg: Path) -> dict:
    row: dict = {}
    row.update({k: v for k, v in parse_keyed(read(cg / "cpu.stat")).items()
                if k in ("usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec")})
    row.update({f"cpu_{k}": v for k, v in parse_psi(read(cg / "cpu.pressure")).items()})
    row.update({f"mem_{k}": v for k, v in parse_psi(read(cg / "memory.pressure")).items()})
    for name in ("memory.current", "memory.peak", "memory.max", "pids.current"):
        text = read(cg / name)
        row[name.replace(".", "_")] = (text or "").strip()
    stat = parse_keyed(read(cg / "memory.stat"))
    row["mem_anon"], row["mem_file"] = stat.get("anon", 0), stat.get("file", 0)
    row["oom_kill"] = parse_keyed(read(cg / "memory.events")).get("oom_kill", 0)
    return row


def find_pid(comm: str) -> int | None:
    for stat in glob.glob(str(PROC / "[0-9]*/comm")):
        if (read(Path(stat)) or "").strip() == comm:
            return int(Path(stat).parent.name)
    return None


def process_row(pid: int | None) -> dict:
    if pid is None:
        return {}
    text = read(PROC / str(pid) / "stat")
    if not text:
        return {}
    f = text[text.rindex(")") + 2:].split()  # fields after "(comm) "
    # f[0]=state ... utime=f[11] stime=f[12] num_threads=f[17] rss(pages)=f[21]
    return {"pid": pid, "utime_ticks": f[11], "stime_ticks": f[12], "threads": f[17],
            "rss_kb": int(f[21]) * (os.sysconf("SC_PAGE_SIZE") // 1024 if hasattr(os, "sysconf") else 4)}


class PgSession:
    """One persistent psql session as role `monitor` (docker exec -i), queried once per second."""

    def __init__(self, container: str):
        self.q: queue.Queue = queue.Queue()
        self.proc = subprocess.Popen(
            ["docker", "exec", "-i", container, "psql", "-X", "-q", "-At", "-F", ",", "-U", "monitor", "-d", "bench"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.q.put(line.rstrip("\n"))

    def sample(self, timeout: float = 0.8) -> dict:
        try:
            self.proc.stdin.write(PG_QUERY + f"\nSELECT '{END}';\n")
            self.proc.stdin.flush()
            lines = []
            deadline = time.time() + timeout
            while True:
                line = self.q.get(timeout=max(0.01, deadline - time.time()))
                if line == END:
                    break
                lines.append(line)
            vals = (lines[0] if lines else "").split(",")
            return dict(zip(PG_COLUMNS, vals)) if len(vals) == len(PG_COLUMNS) else {}
        except (queue.Empty, OSError, ValueError):
            return {}

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except OSError:
            pass


def container_id(name: str) -> str | None:
    p = subprocess.run(["docker", "inspect", "-f", "{{.Id}}", name], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


class Writer:
    def __init__(self, path: Path):
        self.f = open(path, "w", newline="", buffering=1)
        self.w: csv.DictWriter | None = None

    def write(self, ts: int, row: dict) -> None:
        if not row:
            return
        row = {"ts_ms": ts, **row}
        if self.w is None:
            self.w = csv.DictWriter(self.f, fieldnames=list(row))
            self.w.writeheader()
        self.w.writerow({k: row.get(k, "") for k in self.w.fieldnames})

    def close(self):
        self.f.close()


# ---- main loop ---------------------------------------------------------------------------------
def run(args) -> int:
    out = Path(args.dir) / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "pid").write_text(str(os.getpid()))
    stopping = False

    def handler(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    writers = {"host": Writer(out / "host.csv")}
    cgroups: dict[str, Path | None] = {}
    names = dict(kv.split("=") for kv in args.containers.split(",") if kv) if args.mode == "sut" else {}
    for label in names:
        writers[label] = Writer(out / f"{label}.csv")
        cgroups[label] = None
    pg = PgSession(args.pg_container) if args.mode == "sut" and args.pg_container else None
    if pg:
        writers["pg"] = Writer(out / "pg.csv")
    if args.mode == "lg":
        writers["k6"] = Writer(out / "k6.csv")
    k6_pid = None
    started = time.time()

    nxt = int(started) + 1
    while not stopping:
        delay = nxt - time.time()
        if delay > 0:
            time.sleep(delay)
        ts = int(time.time() * 1000)
        writers["host"].write(ts, host_row())
        for label, cname in names.items():
            if cgroups[label] is None or not cgroups[label].is_dir():
                cid = container_id(cname)
                cgroups[label] = container_cgroup(cid) if cid else None
            if cgroups[label]:
                writers[label].write(ts, cgroup_row(cgroups[label]))
        if pg:
            writers["pg"].write(ts, pg.sample())
        if args.mode == "lg":
            if k6_pid is None or not (PROC / str(k6_pid)).is_dir():
                k6_pid = find_pid("k6")
            writers["k6"].write(ts, process_row(k6_pid))
        nxt += 1
        if nxt < time.time():  # fell behind (suspend, heavy load): resync instead of bursting
            nxt = int(time.time()) + 1

    if pg:
        pg.close()
    for w in writers.values():
        w.close()
    (out / "done").write_text(str(int(time.time())))
    return 0


def start(args) -> int:
    out = Path(args.dir) / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, os.path.abspath(__file__), "run", args.run_id, "--mode", args.mode,
           "--containers", args.containers, "--pg-container", args.pg_container, "--dir", args.dir]
    log = open(out / "sampler.log", "w")
    proc = subprocess.Popen(["nice", "-n", "10", *cmd], stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):  # wait for the first row so callers know sampling has begun
        if (out / "host.csv").is_file() and (out / "host.csv").stat().st_size > 0:
            print(proc.pid)
            return 0
        time.sleep(0.1)
    print("sampler did not start; see", out / "sampler.log", file=sys.stderr)
    return 1


def stop(args) -> int:
    out = Path(args.dir) / args.run_id
    try:
        pid = int((out / "pid").read_text())
    except (OSError, ValueError):
        print("no running sampler for", args.run_id, file=sys.stderr)
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return 0
    for _ in range(100):
        if (out / "done").exists():
            return 0
        time.sleep(0.1)
    print("sampler did not stop in 10 s", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["start", "stop", "run"])
    ap.add_argument("run_id")
    ap.add_argument("--mode", choices=["sut", "lg"], default="sut")
    ap.add_argument("--containers", default="api=bench-api,db=bench-postgres")
    ap.add_argument("--pg-container", default="bench-postgres")
    ap.add_argument("--dir", default=DEFAULT_DIR)
    a = ap.parse_args(argv)
    return {"start": start, "stop": stop, "run": run}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
