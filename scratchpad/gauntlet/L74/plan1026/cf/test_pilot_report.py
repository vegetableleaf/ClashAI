"""pilot_report.py: the budget model (expected samples through the gap / probability rule, the water-filling split) and a whole
report on a synthetic dump.   research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/plan1026/cf/test_pilot_report.py"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_report as PR                                                  # noqa: E402


class TestBudget(unittest.TestCase):
    def test_expected_samples_gap_and_p(self):
        ticks = [list(range(0, 1000, 10))]
        self.assertAlmostEqual(PR.expected_samples(ticks, 100, 1.0, reps=1), 10.0)       # 0, 100, ..., 900
        self.assertEqual(PR.expected_samples(ticks, 100, 0.0), 0.0)
        self.assertEqual(PR.expected_samples([], 100, 0.5), 0.0)
        lo, hi = PR.expected_samples(ticks, 100, 0.05, reps=200), PR.expected_samples(ticks, 100, 0.3, reps=200)
        self.assertTrue(0 < lo < hi <= 10)
        # a single eligible decision per match: samples per match = p
        self.assertAlmostEqual(PR.expected_samples([[50]] * 200, 100, 0.25, reps=50), 0.25, delta=0.02)

    def test_budget_split_water_fills(self):
        cost = {"a": 100.0, "b": 100.0, "c": 100.0}
        cap = {"a": 1.0, "b": 100.0, "c": 100.0}                                     # a can only use 100 ticks
        sp = PR.budget_split(cost, cap, 1000.0, {"a": 1.0, "b": 1.0, "c": 1.0})
        self.assertAlmostEqual(sp["a"], 100.0)
        self.assertAlmostEqual(sp["b"], 450.0)
        self.assertAlmostEqual(sp["c"], 450.0)
        sp = PR.budget_split(cost, cap, 150.0, {"a": 1.0, "b": 1.0, "c": 0.5})       # no cap binds: shares 1 : 1 : .5
        self.assertAlmostEqual(sum(sp.values()), 150.0)
        self.assertAlmostEqual(sp["c"], 30.0)
        self.assertEqual(PR.budget_split({"a": 0.0}, {"a": 1.0}, 10.0, {"a": 1.0}), {"a": 0.0})   # nothing to buy


def _sample(rng, trig, tick, signal):
    # two candidates, K = 2 continuations: q = signal * [1, -1] + noise
    qs = [[float(signal * s + 0.05 * rng.standard_normal()) for _ in range(2)] for s in (0.5, -0.5)]
    cands = [{"kind": "chosen", "q": qs[0], "end": [600, 600], "terminal": [False, False], "q_end": None},
             {"kind": "wait", "q": qs[1], "end": [600, 600], "terminal": [False, False], "q_end": None}]
    return {"row": 1, "tick": tick, "trigger": trig, "audit": False, "to_end": False, "cands": cands, "fork_ticks": 2400,
            "wall_s": 1.0}


class TestReport(unittest.TestCase):
    def test_whole_report(self):
        rng = np.random.default_rng(0)
        rows = []
        for m in range(40):
            ticks = list(range(100, 5000, 10))
            samples = [_sample(rng, "rocket", t, 0.2) for t in (300, 900)]
            rows.append({"update": 3 + m % 3, "outcome": "win", "end_tick": 6000, "wall_s": 100.0,
                         "cf": {"samples": samples, "wall_s": 2.0, "triggers": {"rocket": 2}, "fired": {"rocket": 2}, "capped": {},
                                "decisions": 500, "fork_ticks": 4800, "k": 2, "cond": {"rocket": len(ticks)},
                                "cond_ticks": {"rocket": ticks, "random": list(range(0, 6000, 10))}}})
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "dump.jsonl"
            f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                PR.main([str(f), "--budget", "1.0"])
        out = json.loads(buf.getvalue())
        self.assertEqual(out["matches"], 40)
        t = out["triggers"]["rocket"]
        self.assertGreater(t["snr"], 1.0)                                             # a strong planted signal
        self.assertEqual(t["fork_ticks_per_sample"], 2400.0)
        b = out["budget"]
        self.assertTrue(all(0.0 <= p <= 1.0 for p in b["recommended_cf_p"].values()))
        self.assertGreater(b["recommended_cf_p"]["rocket"], 0.0)
        self.assertLessEqual(b["predicted_fork_ticks_per_match_tick"], 1.05)
        self.assertGreater(b["predicted_fork_ticks_per_match_tick"], 0.5)             # the budget is (nearly) used


if __name__ == "__main__":
    unittest.main()
