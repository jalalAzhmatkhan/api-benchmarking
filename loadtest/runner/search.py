#!/usr/bin/env python3
"""Find VU* for one (stack, scenario, think): the highest VU count that passes the SLO.

  python3 loadtest/runner/search.py --stack go-gin --scenario s1 --think T0 --out results/c1/go-gin/s1-T0

Algorithm (k6 plan §6): exponential growth until the first FAIL → binary search to within
max(5 VUs, 5 %) → 3 confirmation runs (300 s, fresh stack, raw data) → on a confirmation failure
lower the candidate by 5 % and confirm again (max 3 rounds, else UNSTABLE).
A level that fails only because the load generator was saturated (LG-BOUND) or errored is re-run
once; if it repeats the search stops with LIMITED-BY-LOADGEN. Re-running resumes from levels.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

import common as c

LevelFn = Callable[[int, int, str, bool, bool], dict]  # (vus, measure_s, tag, fresh, raw) -> {"verdict": ...}

PASS, FAIL = "PASS", "FAIL"


class Stop(Exception):
    """The search cannot continue (load generator limit)."""

    def __init__(self, last_pass: int):
        super().__init__("limited by the load generator")
        self.last_pass = last_pass


def search(level: LevelFn, *, start: int, cap: int, search_measure: int = 120, confirm_measure: int = 300,
           confirm_reps: int = 3, max_rounds: int = 3, tol_pct: float = 0.05, tol_min: int = 5,
           cooldown_s: float = 0, sleep=time.sleep, log=lambda m: None) -> dict:
    levels: list[dict] = []

    def run(vus: int, measure: int, tag: str, fresh: bool = False, raw: bool = False) -> dict:
        res: dict = {}
        for attempt in (1, 2):  # a saturated generator or an error gets one retry
            res = level(vus, measure, tag, fresh, raw)
            levels.append({"vus": vus, "tag": tag, "attempt": attempt, "verdict": res["verdict"]})
            if cooldown_s:
                sleep(cooldown_s)
            if res["verdict"] in (PASS, FAIL):
                return res
            log(f"{vus} VUs: {res['verdict']} (not a server verdict), attempt {attempt}")
        raise Stop(last_pass=0)

    def outcome(status: str, vu_star: int) -> dict:
        return {"status": status, "vu_star": vu_star, "levels": levels}

    cap = max(1, cap)
    last_pass, first_fail = 0, None
    try:
        # Phase A: exponential growth
        v = min(start, cap)
        while True:
            if run(v, search_measure, "search")["verdict"] == PASS:
                last_pass = v
                if v >= cap:
                    break
                v = min(v * 2, cap)
            else:
                first_fail = v
                break
        capped = first_fail is None

        # Phase B: binary search between last_pass and first_fail
        while first_fail is not None:
            tol = 1 if last_pass == 0 else max(tol_min, int(last_pass * tol_pct))
            if first_fail - last_pass <= tol:
                break
            mid = (last_pass + first_fail) // 2
            if run(mid, search_measure, "search")["verdict"] == PASS:
                last_pass = mid
            else:
                first_fail = mid

        if last_pass == 0:
            return outcome("BELOW-MINIMUM", 0)

        # Phase C: confirmation
        candidate = last_pass
        for rnd in range(1, max_rounds + 1):
            if all(run(candidate, confirm_measure, f"confirm{rnd}-{i}", fresh=True, raw=True)["verdict"] == PASS
                   for i in range(1, confirm_reps + 1)):
                return outcome("CAPPED" if capped and candidate == last_pass else "OK", candidate)
            log(f"confirmation round {rnd} failed at {candidate} VUs")
            candidate = int(candidate * 0.95)
            if candidate < 1:
                break
        return outcome("UNSTABLE", max(candidate, 0))
    except Stop as stop:
        return outcome("LIMITED-BY-LOADGEN", max(last_pass, stop.last_pass))


# ---- CLI plumbing: resumable level runner --------------------------------------------------
def make_level_fn(args, out_dir: Path) -> LevelFn:
    import runlevel

    journal = out_dir / "levels.jsonl"
    done: dict[tuple, dict] = {}
    if journal.is_file():
        for line in journal.read_text().splitlines():
            r = json.loads(line)
            if r["verdict"] in (PASS, FAIL):
                done[(r["vus"], r["measure_s"], r["tag"])] = r

    def level(vus: int, measure: int, tag: str, fresh: bool, raw: bool) -> dict:
        key = (vus, measure, tag)
        if key in done:
            c.log(f"resume: {vus} VUs [{tag}] already done → {done[key]['verdict']}")
            return done[key]
        res = runlevel.run_level(
            stack=args.stack, scenario=args.scenario, think=args.think, vus=vus, measure_s=measure,
            warmup_s=args.warmup, out_dir=out_dir / "levels" / f"{vus:06d}-{tag}-{int(time.time())}",
            raw=raw, fresh=fresh)
        res["tag"] = tag
        with open(journal, "a") as f:
            f.write(json.dumps(res) + "\n")
        if res["verdict"] in (PASS, FAIL):
            done[key] = res
        return res

    return level


def main(argv=None) -> int:
    c.load_sut_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack", required=True, choices=c.STACKS)
    ap.add_argument("--scenario", required=True, choices=sorted(c.SCENARIOS))
    ap.add_argument("--think", default="T0", choices=c.THINKS)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--start", type=int, help="first level (default 10 for T0, 50 for T1)")
    ap.add_argument("--cap", type=int, help="maximum VUs (default from load-generator memory)")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--search-measure", type=int, default=120)
    ap.add_argument("--confirm-measure", type=int, default=300)
    ap.add_argument("--reps", type=int, default=3, help="confirmation repetitions")
    ap.add_argument("--cooldown", type=float, default=30, help="seconds between levels")
    a = ap.parse_args(argv)

    start = a.start or (50 if a.think == "T1" else 10)
    cap = a.cap
    if cap is None:
        mem = c.mem_info()  # about 3 MB per VU, 85 % of RAM usable (deployment plan §3)
        cap = int(0.85 * mem["total_mb"] / float(os.environ.get("MB_PER_VU", "3"))) if mem else 5000
    a.out.mkdir(parents=True, exist_ok=True)
    c.log(f"search {a.stack} {a.scenario}-{a.think}: start={start} cap={cap}")

    result = search(make_level_fn(a, a.out), start=start, cap=cap, search_measure=a.search_measure,
                    confirm_measure=a.confirm_measure, confirm_reps=a.reps, cooldown_s=a.cooldown, log=c.log)
    result.update(stack=a.stack, scenario=a.scenario, think=a.think, finished=c.now_iso(), git_sha=c.git_sha())
    c.write_json(a.out / "result.json", result)
    c.log(f"VU* = {result['vu_star']} ({result['status']})")
    print("VU_STAR " + json.dumps({k: result[k] for k in ("stack", "scenario", "think", "status", "vu_star")}))
    return 0 if result["status"] in ("OK", "CAPPED") else 3


if __name__ == "__main__":
    sys.exit(main())
