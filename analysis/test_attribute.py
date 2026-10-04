"""Attribution tests on synthetic sampler data (python3 -m unittest discover -s analysis)."""
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import attribute  # noqa: E402

T0 = 1_000_000_000_000          # k6 start (epoch ms)
WARMUP, MEASURE = 10, 30        # seconds
# measure window analysed: [T0+(WARMUP+2)s, T0+(WARMUP+2)s + (MEASURE-2)s] = 28 s


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def make_level(root: Path, *, host_busy=95.0, steal=0.0, api_cores=1.0, db_cores=0.8, mem_limit=3 << 30,
               api_mem=200 << 20, db_mem=300 << 20, active=3, wait_lock=0, wait_io=0, lg_busy=30.0, lg_mem_used=40.0,
               oom=0, mem_psi=0.0, nic_mbit=50.0, listen_overflows=0, drop_rows=0, failures=None, requests=100_000):
    """Samples every second for 50 s (covers warm-up+measure). 2 CPUs: jiffies at 100 Hz."""
    meta = {"k6_started_ms": T0, "k6_finished_ms": T0 + 45_000, "warmup_s": WARMUP, "measure_s": MEASURE, "vus": 100, "verdict": "FAIL"}
    (root).mkdir(parents=True, exist_ok=True)
    (root / "meta.json").write_text(json.dumps(meta))
    (root / "result.json").write_text(json.dumps({"requests_measure": requests, "failures_by_type": failures or {}}))
    host, api, db, pg, lgh, k6 = [], [], [], [], [], []
    for i in range(51):
        ts = T0 + i * 1000
        if drop_rows and 12 <= i < 12 + drop_rows:
            continue
        total = 200 * i  # 2 CPUs * 100 jiffies/s
        busy = int(total * host_busy / 100)
        st = int(total * steal / 100)
        host.append({"ts_ms": ts, "cpu_user": busy - st, "cpu_nice": 0, "cpu_system": 0, "cpu_idle": total - busy,
                     "cpu_iowait": 0, "cpu_irq": 0, "cpu_softirq": 0, "cpu_steal": st,
                     "cpu0_busy": busy // 2, "cpu0_total": total // 2, "cpu1_busy": busy // 2, "cpu1_total": total // 2,
                     "mem_total_kb": 8_000_000, "mem_available_kb": 5_000_000, "net_rx_bytes": int(i * nic_mbit * 1e6 / 16),
                     "net_tx_bytes": int(i * nic_mbit * 1e6 / 16), "listen_overflows": i * listen_overflows, "listen_drops": 0,
                     "tcp_retrans_segs": 0, "psi_cpu_some_avg10": 1.0, "sampler_cpu_s": round(i * 0.004, 3)})
        for rows, cores, mem in ((api, api_cores, api_mem), (db, db_cores, db_mem)):
            rows.append({"ts_ms": ts, "usage_usec": int(i * cores * 1e6), "nr_periods": 0, "nr_throttled": 0,
                         "cpu_some_avg10": 5.0, "mem_some_avg10": mem_psi, "memory_current": mem, "memory_max": mem_limit,
                         "oom_kill": oom if i > 20 else 0})
        pg.append({"ts_ms": ts, "active": active, "idle": 10 - active, "idle_in_txn": 0, "wait_lock": wait_lock, "wait_lwlock": 0,
                   "wait_io": wait_io, "xact_commit": i * 1000, "xact_rollback": 0, "blks_hit": i * 9000, "blks_read": i * 100,
                   "deadlocks": 0, "temp_bytes": 0})
        lgh.append({"ts_ms": ts, "cpu_user": int(total * lg_busy / 100), "cpu_nice": 0, "cpu_system": 0,
                    "cpu_idle": total - int(total * lg_busy / 100), "cpu_iowait": 0, "cpu_irq": 0, "cpu_softirq": 0, "cpu_steal": 0,
                    "cpu0_busy": 1, "cpu0_total": 1, "cpu1_busy": 1, "cpu1_total": 1,
                    "mem_total_kb": 8_000_000, "mem_available_kb": int(8_000_000 * (1 - lg_mem_used / 100)),
                    "net_rx_bytes": 0, "net_tx_bytes": 0, "listen_overflows": 0, "listen_drops": 0, "tcp_retrans_segs": 0,
                    "psi_cpu_some_avg10": 0, "sampler_cpu_s": 0})
        k6.append({"ts_ms": ts, "utime_ticks": i * 50, "stime_ticks": i * 10, "threads": 20, "rss_kb": 500_000})
    write_csv(root / "sampler-sut" / "host.csv", host)
    write_csv(root / "sampler-sut" / "api.csv", api)
    write_csv(root / "sampler-sut" / "db.csv", db)
    write_csv(root / "sampler-sut" / "pg.csv", pg)
    write_csv(root / "sampler-lg" / "host.csv", lgh)
    write_csv(root / "sampler-lg" / "k6.csv", k6)
    return root


class AttributionTests(unittest.TestCase):
    def verdict(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            out = attribute.analyze(make_level(Path(tmp) / "lvl", **kw), pool=10)
            return out["verdict"], out

    def test_host_cpu_api_dominant(self):
        v, out = self.verdict(host_busy=96, api_cores=1.4, db_cores=0.4)
        self.assertEqual(v, "HOST-CPU:API")
        m = out["metrics"]
        self.assertAlmostEqual(m["api"]["cpu_cores"], 1.4, places=2)
        self.assertAlmostEqual(m["api"]["cpu_ms_per_request"], 1.4 * 28 * 1000 / 100_000, places=3)  # cores*seconds*1000/requests
        self.assertAlmostEqual(m["host"]["busy_pct"], 96, delta=1)

    def test_host_cpu_db_dominant(self):
        self.assertEqual(self.verdict(host_busy=95, api_cores=0.5, db_cores=1.4)[0], "HOST-CPU:DB")

    def test_host_cpu_shared(self):
        self.assertEqual(self.verdict(host_busy=95, api_cores=1.0, db_cores=0.9)[0], "HOST-CPU:SHARED")

    def test_lg_bound_wins_over_everything_below(self):
        self.assertEqual(self.verdict(host_busy=96, lg_busy=92)[0], "LG-BOUND")
        self.assertEqual(self.verdict(host_busy=50, lg_mem_used=90)[0], "LG-BOUND")

    def test_invalid_on_steal_or_missing_samples(self):
        self.assertEqual(self.verdict(steal=7)[0], "INVALID")
        self.assertEqual(self.verdict(drop_rows=6)[0], "INVALID")  # 6 of 28 samples missing (> 2 %)

    def test_network_bound(self):
        self.assertEqual(self.verdict(host_busy=40, nic_mbit=900)[0] in ("NETWORK-BOUND", "API-RUNTIME-BOUND"), True)
        with tempfile.TemporaryDirectory() as tmp:
            out = attribute.analyze(make_level(Path(tmp) / "l", host_busy=40, nic_mbit=900), pool=10, nic_mbit=1000)
            self.assertEqual(out["verdict"], "NETWORK-BOUND")
        v, _ = self.verdict(host_busy=40, failures={"transport": 3})
        self.assertEqual(v, "NETWORK-BOUND")
        v, _ = self.verdict(host_busy=40, failures={"transport": 3}, listen_overflows=5)
        self.assertNotEqual(v, "NETWORK-BOUND", "listen overflows point at the server, not the network")

    def test_memory_bound(self):
        self.assertEqual(self.verdict(host_busy=50, oom=1)[0], "MEMORY-BOUND")
        self.assertEqual(self.verdict(host_busy=50, api_mem=int(2.95 * (1 << 30)))[0], "MEMORY-BOUND")
        self.assertEqual(self.verdict(host_busy=50, mem_psi=12.0)[0], "MEMORY-BOUND")

    def test_db_lock_io(self):
        self.assertEqual(self.verdict(host_busy=50, active=8, wait_lock=4, wait_io=1)[0], "DB-LOCK-IO-BOUND")

    def test_pool_bound(self):
        self.assertEqual(self.verdict(host_busy=50, active=10)[0], "POOL-BOUND")

    def test_api_runtime_bound(self):
        self.assertEqual(self.verdict(host_busy=50, active=2)[0], "API-RUNTIME-BOUND")

    def test_no_sampler_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "meta.json").write_text("{}")
            self.assertEqual(attribute.analyze(Path(tmp))["verdict"], "NO-DATA")

    def test_attribution_file_written_and_lg_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            lvl = make_level(Path(tmp) / "lvl")
            out = attribute.analyze(lvl)
            self.assertTrue((lvl / "attribution.json").is_file())
            self.assertAlmostEqual(out["metrics"]["lg"]["k6_cpu_cores"], 0.6, places=1)
            self.assertAlmostEqual(out["metrics"]["host"]["sampler_overhead_pct"], 0.4, places=1)
            self.assertAlmostEqual(out["metrics"]["pg"]["cache_hit_ratio"], 0.989, places=3)



class SummarizeTests(unittest.TestCase):
    def test_cell_summary(self):
        import summarize
        with tempfile.TemporaryDirectory() as tmp:
            cell = Path(tmp) / "c1" / "go-gin" / "s1-T0"
            for name, vus, tag in (("a", 100, "confirm1-1"), ("b", 100, "confirm1-2"), ("c", 120, "search")):
                d = cell / "levels" / name
                make_level(d, host_busy=96 if name == "c" else 70, api_cores=1.5 if name == "c" else 1.0)
                attribute.analyze(d)
            levels = [
                {"vus": 100, "tag": "confirm1-1", "verdict": "PASS", "p50": 10, "p95": 20, "p99": 40, "rps": 1000, "dir": str(cell / "levels" / "a")},
                {"vus": 100, "tag": "confirm1-2", "verdict": "PASS", "p50": 12, "p95": 22, "p99": 44, "rps": 1100, "dir": str(cell / "levels" / "b")},
                {"vus": 120, "tag": "search", "verdict": "FAIL", "dir": str(cell / "levels" / "c")},
            ]
            (cell / "levels.jsonl").write_text("\n".join(json.dumps(l) for l in levels) + "\n")
            (cell / "result.json").write_text(json.dumps({"stack": "go-gin", "scenario": "s1", "think": "T0", "status": "OK", "vu_star": 100}))
            rows = summarize.collect(Path(tmp) / "c1")
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual((r["stack"], r["cell"], r["vu_star"], r["p50_ms"], r["rps"]), ("go-gin", "s1-T0", 100, 11.0, 1050.0))
            self.assertEqual((r["limit_vus"], r["limit_bound"]), (120, "HOST-CPU:API"))
            self.assertIsNotNone(r["api_cpu_ms_per_req"])
            self.assertIn("| go-gin | s1-T0 | OK | 100 |", summarize.to_markdown(rows))


if __name__ == "__main__":
    unittest.main()
