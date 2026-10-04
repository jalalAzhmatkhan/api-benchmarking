#!/usr/bin/env python3
"""Run ONE k6 level (one VU count) and write verdict.txt, result.json, summary.json, meta.json.

  python3 loadtest/runner/runlevel.py --stack go-gin --scenario s1 --think T0 --vus 100 --out results/x

Steps: [restart stack (--fresh)] → reset DB → [start sampler] → k6 → [stop sampler] → verdict.
Verdicts: PASS | FAIL | LG-BOUND (k6 failed while the load generator was saturated: not the
server's fault) | ERROR (k6 could not run). The last stdout line is `RESULT {json}`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import common as c

SAMPLER_PY = c.REPO_DIR / "monitoring" / "sampler.py"
sys.path.insert(0, str(c.REPO_DIR / "analysis"))
NON_SERVER = ("INVALID", "LG-BOUND", "NETWORK-BOUND")  # attribution verdicts that are not the server's fault

LG_CPU_LIMIT = 80.0   # monitoring plan §4 rule 2
LG_MEM_LIMIT = 85.0
LG_STEAL_LIMIT = 5.0


def classify(k6_exit: int, lg: dict | None, mem: dict | None) -> str:
    if k6_exit == 0:
        return "PASS"
    if k6_exit == 99:  # thresholds crossed (SLO, failed request or failed check)
        saturated = bool(
            (lg and (lg["cpu_pct"] > LG_CPU_LIMIT or lg["steal_pct"] > LG_STEAL_LIMIT))
            or (mem and mem["used_pct"] > LG_MEM_LIMIT)
        )
        return "LG-BOUND" if saturated else "FAIL"
    return "ERROR"


def start_samplers(run_id: str, out_dir: Path) -> None:
    """LG sampler locally (out_dir/sampler-lg), SUT sampler over ssh (/var/lib/bench/runs/sut-<run_id>)."""
    subprocess.run([sys.executable, str(SAMPLER_PY), "start", "sampler-lg", "--mode", "lg", "--dir", str(out_dir)],
                   check=True, capture_output=True)
    c.sut(c.hook("SUT_SAMPLER_START", "python3 {bench}/monitoring/sampler.py start {sid} --mode sut", sid=f"sut-{run_id}"))


def stop_samplers(run_id: str, out_dir: Path) -> None:
    subprocess.run([sys.executable, str(SAMPLER_PY), "stop", "sampler-lg", "--dir", str(out_dir)], capture_output=True)
    sid = f"sut-{run_id}"
    c.sut(c.hook("SUT_SAMPLER_STOP", "python3 {bench}/monitoring/sampler.py stop {sid}", sid=sid), check=False)
    if c.dry_sut():
        return
    dest = out_dir / "sampler-sut"
    dest.mkdir(parents=True, exist_ok=True)
    remote = subprocess.Popen(["ssh", "-o", "BatchMode=yes", "sut", f"tar -C /var/lib/bench/runs/{sid} -cf - ."],
                              stdout=subprocess.PIPE)
    subprocess.run(["tar", "-xf", "-", "-C", str(dest)], stdin=remote.stdout, check=False)
    remote.wait()
    c.sut(f"rm -rf /var/lib/bench/runs/{sid}", check=False)


def run_level(*, stack: str, scenario: str, think: str, vus: int, measure_s: int, out_dir: Path,
              warmup_s: int = 60, raw: bool = False, fresh: bool = False, k6: str | None = None,
              base_url: str | None = None) -> dict:
    k6 = k6 or os.environ.get("K6", "k6")
    base_url = base_url or os.environ.get("BASE_URL", "http://127.0.0.1:8080")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{stack}-{scenario}-{think}-{vus}-{c.now_iso()}".replace(":", "")

    if fresh:
        c.log(f"restarting {stack} on the SUT")
        c.sut(c.hook("SUT_RESTART_CMD", "{bench}/deploy/stack.sh restart {stack}", stack=stack))
    c.sut(c.hook("SUT_RESET_CMD", "DB_CONTAINER=bench-postgres {bench}/db/reset.sh"))
    sampler = os.environ.get("SAMPLER", "0") == "1"
    if sampler:
        start_samplers(run_id, out_dir)

    cmd = [k6, "run", "--quiet", "--no-color"]
    if raw:
        cmd += ["--out", f"csv={out_dir / 'raw.csv.gz'}"]
    for k, v in {
        "BASE_URL": base_url, "VUS": vus, "THINK": think, "WARMUP_S": warmup_s, "MEASURE_S": measure_s,
        "SCENARIO_NAME": scenario, "SUMMARY_PATH": out_dir / "summary.json", "RESULT_PATH": out_dir / "result.json",
    }.items():
        cmd += ["-e", f"{k}={v}"]
    cmd.append(str(c.LOADTEST_DIR / "scenarios" / c.SCENARIOS[scenario]))

    c.log(f"k6: {stack} {scenario} {think} vus={vus} warmup={warmup_s}s measure={measure_s}s")
    offset = c.sut_clock_offset_ms()
    cpu0 = c.cpu_snapshot()
    started = c.now_iso()
    k6_started_ms = int(time.time() * 1000)
    with open(out_dir / "k6.log", "w") as log_file:
        k6_exit = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT).returncode
    k6_finished_ms = int(time.time() * 1000)
    lg = c.cpu_usage(cpu0, c.cpu_snapshot())
    mem = c.mem_info()

    if sampler:
        stop_samplers(run_id, out_dir)

    verdict = classify(k6_exit, lg, mem)
    result = c.read_json(out_dir / "result.json", {})
    summary = {
        "stack": stack, "scenario": scenario, "think": think, "vus": vus, "measure_s": measure_s,
        "warmup_s": warmup_s, "verdict": verdict, "k6_exit": k6_exit,
        "p50": result.get("p50"), "p95": result.get("p95"), "p99": result.get("p99"),
        "rps": result.get("rps_measure"), "iterations_per_s": result.get("iterations_per_s"),
        "failed_rate": result.get("failed_rate"), "checks_rate": result.get("checks_rate"),
        "lg": lg, "lg_mem": mem,
    }
    (out_dir / "verdict.txt").write_text(verdict + "\n")
    c.write_json(out_dir / "meta.json", {
        **summary, "run_id": run_id, "started": started, "finished": c.now_iso(), "base_url": base_url,
        "k6_version": c.k6_version(k6), "git_sha": c.git_sha(), "sut_clock_offset_ms": offset,
        "raw": raw, "fresh": fresh, "sampler": sampler,
        "k6_started_ms": k6_started_ms, "k6_finished_ms": k6_finished_ms,
    })
    if sampler:
        import attribute
        attr = attribute.analyze(out_dir, pool=int(os.environ.get("DB_POOL_SIZE", "10")))
        summary["bound"] = attr["verdict"]
        m = attr.get("metrics", {})
        summary["api_cpu_ms_per_req"] = (m.get("api") or {}).get("cpu_ms_per_request")
        summary["db_cpu_ms_per_req"] = (m.get("db") or {}).get("cpu_ms_per_request")
        if verdict == "FAIL" and attr["verdict"] in NON_SERVER:
            verdict = summary["verdict"] = attr["verdict"]  # re-run / stop: not a server verdict
            (out_dir / "verdict.txt").write_text(verdict + chr(10))
            meta = c.read_json(out_dir / "meta.json", {})
            meta.update(verdict=verdict, bound=attr["verdict"])
            c.write_json(out_dir / "meta.json", meta)
    summary["dir"] = str(out_dir)
    c.log(f"verdict {verdict} (k6 exit {k6_exit}) p50={summary['p50']} p95={summary['p95']} p99={summary['p99']}"
          + (f" bound={summary['bound']}" if sampler else ""))
    return summary


def main(argv=None) -> int:
    c.load_sut_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack", required=True, choices=c.STACKS)
    ap.add_argument("--scenario", required=True, choices=sorted(c.SCENARIOS))
    ap.add_argument("--think", default="T0", choices=c.THINKS)
    ap.add_argument("--vus", required=True, type=int)
    ap.add_argument("--measure", type=int, default=120, help="measure phase, seconds")
    ap.add_argument("--warmup", type=int, default=60, help="warm-up, seconds")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--raw", action="store_true", help="also write raw.csv.gz (confirmation runs)")
    ap.add_argument("--fresh", action="store_true", help="restart the stack on the SUT first")
    a = ap.parse_args(argv)
    res = run_level(stack=a.stack, scenario=a.scenario, think=a.think, vus=a.vus, measure_s=a.measure,
                    out_dir=a.out, warmup_s=a.warmup, raw=a.raw, fresh=a.fresh)
    print("RESULT " + json.dumps(res))
    return 0 if res["verdict"] in ("PASS", "FAIL") else 2


if __name__ == "__main__":
    sys.exit(main())
