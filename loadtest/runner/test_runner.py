"""Unit tests for the runner logic (python3 -m unittest discover loadtest/runner)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import campaign  # noqa: E402
import runlevel  # noqa: E402
import search  # noqa: E402


def fake_level(limit: int, flaky_confirm_below: int = 0, calls=None):
    """A server that passes up to `limit` VUs. Confirmation runs fail while vus > flaky_confirm_below
    (when set), modelling an unstable boundary."""
    def level(vus, measure, tag, fresh, raw):
        if calls is not None:
            calls.append((vus, measure, tag, fresh, raw))
        ok = vus <= limit
        if flaky_confirm_below and tag.startswith("confirm") and vus > flaky_confirm_below:
            ok = False
        return {"verdict": "PASS" if ok else "FAIL"}
    return level


class SearchTests(unittest.TestCase):
    def test_finds_limit_within_tolerance_and_confirms(self):
        calls = []
        r = search.search(fake_level(137, calls=calls), start=10, cap=5000)
        self.assertEqual(r["status"], "OK")
        self.assertLessEqual(r["vu_star"], 137)
        self.assertGreaterEqual(r["vu_star"], 137 - max(5, int(137 * 0.05)))
        confirms = [x for x in calls if x[2].startswith("confirm")]
        self.assertEqual(len(confirms), 3)
        self.assertTrue(all(x[1] == 300 and x[3] and x[4] for x in confirms), "confirmations: 300 s, fresh, raw")
        self.assertTrue(all(x[1] == 120 and not x[3] and not x[4] for x in calls if x[2] == "search"))

    def test_exponential_phase_doubles(self):
        calls = []
        search.search(fake_level(40, calls=calls), start=10, cap=5000)
        searched = [x[0] for x in calls if x[2] == "search"]
        self.assertEqual(searched[:3], [10, 20, 40][:3])
        self.assertIn(80, searched)  # first failure at 80, then binary search inside (40, 80)

    def test_cap_reached(self):
        r = search.search(fake_level(10**9), start=10, cap=100)
        self.assertEqual((r["status"], r["vu_star"]), ("CAPPED", 100))

    def test_below_minimum(self):
        r = search.search(fake_level(0), start=10, cap=1000)
        self.assertEqual((r["status"], r["vu_star"]), ("BELOW-MINIMUM", 0))

    def test_unit_resolution_near_zero(self):
        # tolerance is max(5 VUs, 5 %): a limit of 3 may resolve to 2 or 3, never above the limit
        r = search.search(fake_level(3), start=10, cap=1000)
        self.assertIn(r["vu_star"], (2, 3))

    def test_confirmation_failure_lowers_candidate(self):
        # exponential growth reaches the 1000 cap; confirmations only pass up to 960 VUs.
        # round 1 fails at 1000, round 2 passes at 950 (-5 %)
        r = search.search(fake_level(1000, flaky_confirm_below=960), start=100, cap=1000)
        self.assertEqual((r["status"], r["vu_star"]), ("OK", 950))

    def test_unstable(self):
        r = search.search(fake_level(1000, flaky_confirm_below=1), start=100, cap=1000)
        self.assertEqual(r["status"], "UNSTABLE")

    def test_loadgen_bound_is_retried_once_then_stops(self):
        seen = []

        def level(vus, measure, tag, fresh, raw):
            seen.append(vus)
            if vus >= 80:
                return {"verdict": "LG-BOUND"}
            return {"verdict": "PASS"}

        r = search.search(level, start=10, cap=1000)
        self.assertEqual(r["status"], "LIMITED-BY-LOADGEN")
        self.assertEqual(r["vu_star"], 40)
        self.assertEqual(seen.count(80), 2, "LG-bound level must be re-run exactly once")

    def test_loadgen_bound_recovers_on_retry(self):
        state = {"n": 0}

        def level(vus, measure, tag, fresh, raw):
            if vus == 20 and state["n"] == 0:
                state["n"] += 1
                return {"verdict": "LG-BOUND"}
            return {"verdict": "PASS" if vus <= 30 else "FAIL"}

        r = search.search(level, start=10, cap=1000)
        self.assertEqual(r["status"], "OK")

    def test_error_verdict_is_not_a_server_failure(self):
        r = search.search(lambda *a: {"verdict": "ERROR"}, start=10, cap=100)
        self.assertEqual(r["status"], "LIMITED-BY-LOADGEN")

    def test_cooldown_between_levels(self):
        slept = []
        search.search(fake_level(20), start=10, cap=1000, cooldown_s=30, sleep=slept.append)
        self.assertTrue(slept and all(s == 30 for s in slept))


class ClassifyTests(unittest.TestCase):
    def test_verdicts(self):
        ok = {"cpu_pct": 30.0, "steal_pct": 0.0}
        self.assertEqual(runlevel.classify(0, ok, None), "PASS")
        self.assertEqual(runlevel.classify(99, ok, {"used_pct": 40.0}), "FAIL")
        self.assertEqual(runlevel.classify(99, {"cpu_pct": 91.0, "steal_pct": 0.0}, None), "LG-BOUND")
        self.assertEqual(runlevel.classify(99, {"cpu_pct": 10.0, "steal_pct": 9.0}, None), "LG-BOUND")
        self.assertEqual(runlevel.classify(99, ok, {"used_pct": 90.0}), "LG-BOUND")
        self.assertEqual(runlevel.classify(99, None, None), "FAIL")
        self.assertEqual(runlevel.classify(107, ok, None), "ERROR")
        self.assertEqual(runlevel.classify(0, {"cpu_pct": 99.0, "steal_pct": 0.0}, None), "PASS")


class CampaignTests(unittest.TestCase):
    def test_order_is_seeded_and_complete(self):
        a = campaign.shuffled(list(range(6)), 42)
        b = campaign.shuffled(list(range(6)), 42)
        c = campaign.shuffled(list(range(6)), 43)
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), list(range(6)))
        self.assertNotEqual(a, c)

    def test_matrix_parsing(self):
        self.assertEqual(campaign.parse_matrix("S1-T0,s2-t1"), [("s1", "T0"), ("s2", "T1")])
        with self.assertRaises(SystemExit):
            campaign.parse_matrix("S9-T0")
        with self.assertRaises(SystemExit):
            campaign.parse_matrix("S1")

    def test_plan_covers_every_stack_per_cell(self):
        plan = campaign.plan(campaign.parse_matrix("S1-T0,S1-T1"), list(campaign.c.STACKS), seed=7)
        self.assertEqual(len(plan), 12)
        for cell in (("s1", "T0"), ("s1", "T1")):
            self.assertEqual(sorted(s for sc, th, s in plan if (sc, th) == cell), sorted(campaign.c.STACKS))


if __name__ == "__main__":
    unittest.main()
