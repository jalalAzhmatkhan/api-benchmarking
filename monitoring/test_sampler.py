"""Tests for monitoring/sampler.py: parsers on synthetic /proc and cgroup text, plus a live run on Linux."""
import csv
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sampler  # noqa: E402

PROC_STAT = """cpu  1000 0 500 8000 100 0 50 25 0 0
cpu0 600 0 300 4000 50 0 30 10 0 0
cpu1 400 0 200 4000 50 0 20 15 0 0
intr 1 2 3
"""
NETSTAT = """TcpExt: SyncookiesSent ListenOverflows ListenDrops TCPTimeouts
TcpExt: 0 7 9 3
IpExt: InNoRoutes
IpExt: 0
"""
SNMP = """Tcp: RtoAlgorithm RetransSegs OutSegs
Tcp: 1 42 1000
"""


class ParserTests(unittest.TestCase):
    def test_keyed(self):
        self.assertEqual(sampler.parse_keyed("usage_usec 123\nnr_throttled 0\nbad line here\n"),
                         {"usage_usec": 123, "nr_throttled": 0})
        self.assertEqual(sampler.parse_keyed(None), {})

    def test_psi(self):
        t = "some avg10=1.50 avg60=0.5 avg300=0.1 total=12345\nfull avg10=0.25 avg60=0 avg300=0 total=99\n"
        p = sampler.parse_psi(t)
        self.assertEqual((p["some_avg10"], p["some_total"], p["full_avg10"], p["full_total"]), (1.5, 12345.0, 0.25, 99.0))
        self.assertEqual(sampler.parse_psi(None), {})

    def test_proc_stat(self):
        s = sampler.parse_proc_stat(PROC_STAT)
        self.assertEqual((s["cpu_user"], s["cpu_idle"], s["cpu_steal"]), (1000, 8000, 25))
        self.assertEqual(s["cpu0_total"], 600 + 300 + 4000 + 50 + 30 + 10)
        self.assertEqual(s["cpu0_busy"], s["cpu0_total"] - 4000 - 50)  # busy excludes idle and iowait
        self.assertIn("cpu1_busy", s)

    def test_meminfo_and_net(self):
        m = sampler.parse_meminfo("MemTotal: 8000000 kB\nMemAvailable: 6000000 kB\nSwapFree: 0 kB\n")
        self.assertEqual((m["mem_total_kb"], m["mem_available_kb"]), (8000000, 6000000))
        net = sampler.parse_net_dev("h1\nh2\n  lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\neth0: 500 5 0 0 0 0 0 0 700 7 0 0 0 0 0 0\n")
        self.assertEqual(net, {"net_rx_bytes": 500, "net_tx_bytes": 700})

    def test_netstat_snmp_disk(self):
        n = sampler.parse_netstat(NETSTAT)
        self.assertEqual((n["listen_overflows"], n["listen_drops"], n["tcp_timeouts"]), (7, 9, 3))
        self.assertEqual(sampler.parse_snmp_retrans(SNMP), 42)
        d = sampler.parse_diskstats(
            "   8   0 sda 10 0 100 5 20 0 200 15 0 0 0 0 0 0 0\n   8   1 sda1 1 0 1 1 1 0 1 1 0 0 0 0 0 0 0\n"
            "   7   0 loop0 1 0 1 1 1 0 1 1 0 0 0 0 0 0 0\n")
        self.assertEqual(d, {"disk_writes": 20, "disk_write_ms": 15})


class CgroupTests(unittest.TestCase):
    def test_cgroup_row_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cg = root / "system.slice" / "docker-abc.scope"
            cg.mkdir(parents=True)
            (cg / "cpu.stat").write_text("usage_usec 5000\nuser_usec 3000\nsystem_usec 2000\nnr_periods 10\nnr_throttled 2\nthrottled_usec 77\n")
            (cg / "cpu.pressure").write_text("some avg10=2.00 avg60=1 avg300=0 total=500\nfull avg10=0 avg60=0 avg300=0 total=0\n")
            (cg / "memory.pressure").write_text("some avg10=0.00 avg60=0 avg300=0 total=0\n")
            (cg / "memory.current").write_text("1048576\n")
            (cg / "memory.max").write_text("3221225472\n")
            (cg / "memory.stat").write_text("anon 900000\nfile 100000\n")
            (cg / "memory.events").write_text("low 0\noom 1\noom_kill 1\n")
            (cg / "pids.current").write_text("12\n")
            old = sampler.CGROUP
            sampler.CGROUP = root
            try:
                found = sampler.container_cgroup("abc")
                self.assertEqual(found, cg)
                self.assertIsNone(sampler.container_cgroup("missing"))
                row = sampler.cgroup_row(found)
            finally:
                sampler.CGROUP = old
            self.assertEqual((row["usage_usec"], row["nr_throttled"], row["oom_kill"]), (5000, 2, 1))
            self.assertEqual((row["cpu_some_avg10"], row["memory_current"], row["memory_max"]), (2.0, "1048576", "3221225472"))
            self.assertEqual((row["mem_anon"], row["pids_current"]), (900000, "12"))


@unittest.skipUnless(Path("/proc/stat").exists() and sys.platform.startswith("linux"), "needs Linux /proc")
class LiveTests(unittest.TestCase):
    def test_lg_mode_start_stop_overhead(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = [sys.executable, str(HERE / "sampler.py")]
            self.assertEqual(subprocess.run([*sp, "start", "t1", "--mode", "lg", "--dir", tmp], capture_output=True).returncode, 0)
            time.sleep(4.5)
            self.assertEqual(subprocess.run([*sp, "stop", "t1", "--dir", tmp], capture_output=True).returncode, 0)
            rows = list(csv.DictReader(open(Path(tmp) / "t1" / "host.csv")))
            self.assertGreaterEqual(len(rows), 3)
            ts = [int(r["ts_ms"]) for r in rows]
            self.assertTrue(all(0.5 < (b - a) / 1000 < 1.6 for a, b in zip(ts, ts[1:])), "about 1 Hz")
            for col in ("cpu_steal", "mem_available_kb", "net_rx_bytes", "psi_cpu_some_total", "sampler_cpu_s"):
                self.assertIn(col, rows[0])
            span = (ts[-1] - ts[0]) / 1000
            used = float(rows[-1]["sampler_cpu_s"]) - float(rows[0]["sampler_cpu_s"])
            self.assertLess(100 * used / span, 2.0, "sampler overhead must stay well under 1-2 % of one CPU")
            self.assertTrue((Path(tmp) / "t1" / "done").exists())


if __name__ == "__main__":
    unittest.main()
