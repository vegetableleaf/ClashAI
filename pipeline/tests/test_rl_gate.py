"""Offline tests for pipeline/rl_gate.py, synthetic matches.jsonl fixtures only (no engine, no GPU).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_rl_gate -v
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline import rl_gate as G


def write_matches(d: Path, records: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with (d / "matches.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def rec(tag: str, k: int, outcome: str, *, after_script: bool = False, won_after_script: bool = False,
        ghost_delivered: int = 5, ghost_refused: int = 0, ghost_undelivered: int = 0,
        plays_per_min: float = 8.0) -> dict:
    return {"tag": tag, "k": k, "outcome": outcome, "after_script": after_script,
            "won_after_script": won_after_script, "ghost_delivered": ghost_delivered,
            "ghost_refused": ghost_refused, "ghost_undelivered": ghost_undelivered,
            "plays_per_min": plays_per_min}


class TestRlGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_gate_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_identical_runs_fail(self):
        # 60 tags, init and cand byte-for-byte the same outcomes -> delta 0, CI contains 0, not a pass.
        recs = [rec(f"t{i:03d}", 0, "win" if i < 24 else "loss") for i in range(60)]
        write_matches(self.tmp / "init", recs)
        write_matches(self.tmp / "cand", recs)
        r = G.gate(self.tmp / "init", self.tmp / "cand")
        self.assertEqual(r["n_entries"], 60)
        self.assertAlmostEqual(r["delta_pp"], 0.0)
        self.assertLessEqual(r["delta_ci95_pp"]["lo"], 0.0)
        self.assertGreaterEqual(r["delta_ci95_pp"]["hi"], 0.0)
        self.assertEqual(r["verdict"], "FAIL")

    def test_clear_candidate_passes(self):
        # 60 tags, init 40% win, cand +20 pp (12 tags flip loss->win), all pre-script, matched plays/min.
        init = [rec(f"t{i:03d}", 0, "win" if i < 24 else "loss") for i in range(60)]
        cand = [rec(f"t{i:03d}", 0, "win" if i < 36 else "loss") for i in range(60)]
        write_matches(self.tmp / "init", init)
        write_matches(self.tmp / "cand", cand)
        r = G.gate(self.tmp / "init", self.tmp / "cand")
        self.assertAlmostEqual(r["delta_pp"], 20.0)
        self.assertGreater(r["delta_ci95_pp"]["lo"], 0.0)
        self.assertEqual(r["verdict"], "PASS")

    def test_wins_only_after_script_fails_before_script_criterion(self):
        # cand's extra wins are all after_script True -> the before-script subset shows no gain.
        init = [rec(f"t{i:03d}", 0, "win" if i < 24 else "loss") for i in range(60)]
        cand = []
        for i in range(60):
            if i < 36:
                cand.append(rec(f"t{i:03d}", 0, "win", after_script=True, won_after_script=True))
            else:
                cand.append(rec(f"t{i:03d}", 0, "loss"))
        write_matches(self.tmp / "init", init)
        write_matches(self.tmp / "cand", cand)
        r = G.gate(self.tmp / "init", self.tmp / "cand")
        self.assertLessEqual(r["before_script_delta_pp"], 0.0)
        self.assertFalse(r["criteria"]["before_script_delta_gt_0"])
        self.assertEqual(r["verdict"], "FAIL")

    def test_few_tags_insufficient(self):
        recs = [rec(f"t{i:03d}", 0, "win" if i < 5 else "loss") for i in range(10)]
        write_matches(self.tmp / "init", recs)
        write_matches(self.tmp / "cand", recs)
        r = G.gate(self.tmp / "init", self.tmp / "cand")
        self.assertEqual(r["n_entries"], 10)
        self.assertEqual(r["verdict"], "INSUFFICIENT")

    def test_missing_record_reported_unpaired(self):
        init = [rec(f"t{i:03d}", 0, "win") for i in range(25)]
        cand = [rec(f"t{i:03d}", 0, "win") for i in range(24)]          # t024 missing from cand
        write_matches(self.tmp / "init", init)
        write_matches(self.tmp / "cand", cand)
        r = G.gate(self.tmp / "init", self.tmp / "cand")
        self.assertEqual(r["n_pairs"], 24)
        self.assertIn("t024:0", r["unpaired"]["init_only"])
        self.assertEqual(r["unpaired"]["cand_only"], [])


if __name__ == "__main__":
    unittest.main()
