#!/usr/bin/env python3
"""Run a benchmark campaign: for every matrix cell and stack, find VU* with search.py.

  python3 loadtest/runner/campaign.py --name c1 --matrix S1-T0,S1-T1,S2-T0 --seed 20261004 [--stacks go-gin,rust-axum]

Matrix cell = <scenario>-<think>, e.g. S1-T0. Stack order inside each cell is shuffled with the seed
(randomized order, research §4). One stack runs at a time: it is started before and stopped after its
search on the SUT. Resumable: a stack whose result.json exists is skipped.
Run it inside tmux on K6_SERVER.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import common as c


def shuffled(items: list, seed: int) -> list:
    out = list(items)
    random.Random(seed).shuffle(out)
    return out


def parse_matrix(text: str) -> list[tuple[str, str]]:
    cells = []
    for raw in text.split(","):
        parts = raw.strip().lower().split("-")
        if len(parts) != 2 or parts[0] not in c.SCENARIOS or parts[1].upper() not in c.THINKS:
            raise SystemExit(f"bad matrix cell {raw!r}: expected <S1|S2|S3>-<T0|T1>")
        cells.append((parts[0], parts[1].upper()))
    return cells


def plan(cells: list[tuple[str, str]], stacks: list[str], seed: int) -> list[tuple[str, str, str]]:
    """(scenario, think, stack) in execution order: cells in the given order, stacks shuffled per cell."""
    out = []
    for i, (scenario, think) in enumerate(cells):
        for stack in shuffled(stacks, seed + i):
            out.append((scenario, think, stack))
    return out


def main(argv=None) -> int:
    c.load_sut_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="campaign id, e.g. c1 (results/<name>/...)")
    ap.add_argument("--matrix", default="S1-T0,S1-T1,S2-T0")
    ap.add_argument("--stacks", default=",".join(c.STACKS))
    ap.add_argument("--seed", type=int, required=True, help="seed for the randomized stack order (record it!)")
    ap.add_argument("--results", type=Path, default=c.REPO_DIR / "results")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    a = ap.parse_args(argv)

    stacks = [s.strip() for s in a.stacks.split(",") if s.strip()]
    unknown = [s for s in stacks if s not in c.STACKS]
    if unknown:
        raise SystemExit(f"unknown stacks: {unknown}")
    runs = plan(parse_matrix(a.matrix), stacks, a.seed)
    for n, (scenario, think, stack) in enumerate(runs, 1):
        print(f"{n:2d}. {scenario}-{think}  {stack}")
    if a.dry_run:
        return 0

    import search

    base = a.results / a.name
    c.write_json(base / "campaign.json", {"name": a.name, "matrix": a.matrix, "stacks": stacks, "seed": a.seed,
                                          "order": runs, "started": c.now_iso(), "git_sha": c.git_sha()})
    failed = 0
    for n, (scenario, think, stack) in enumerate(runs, 1):
        out = base / stack / f"{scenario}-{think}"
        if (out / "result.json").is_file():
            c.log(f"[{n}/{len(runs)}] {stack} {scenario}-{think}: already done, skipping")
            continue
        c.log(f"[{n}/{len(runs)}] {stack} {scenario}-{think}")
        c.sut(c.hook("SUT_STACK_START", "{bench}/deploy/stack.sh up {stack}", stack=stack))
        try:
            rc = search.main(["--stack", stack, "--scenario", scenario, "--think", think,
                              "--out", str(out), "--reps", str(a.reps)])
        finally:
            c.sut(c.hook("SUT_STACK_STOP", "{bench}/deploy/stack.sh down {stack}", stack=stack), check=False)
        failed += rc != 0
    c.log(f"campaign {a.name} finished, {failed} search(es) not OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
