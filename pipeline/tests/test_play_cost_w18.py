"""L74 W18 (10-22): the opt-in crown term ``play_cost`` (pipeline/reward_terms.py; the SIM opponent's tempo, opp_model/DIAG_12.md).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_play_cost_w18.py

Covers: absent = the pre-change module (PRE = a9d28a9): the config hash of rl_royale.yaml and the W18 R1 arm, every other term's
row_terms output and batch_stats unchanged; on: -w on the row that decided each ACCEPTED play (refused plays and plays on
dropped rows free), the match cap, its bound, crown_cfg validation and a distinct hash."""
from __future__ import annotations

import subprocess
import sys
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import reward_terms as RT                                   # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_reward_terms_1020 import lead_match, tornado_match  # noqa: E402

PRE = "a9d28a9"
YAMLS = (REPO / "pipeline/rl_royale.yaml", REPO / "scratchpad/gauntlet/L74/opp_model/cfg/oppW18R1_redirect_s74.yaml")
BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.5}


def _pre(rel, name):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__ = str(REPO / rel)
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def plays(*xs):
    return [{"tick": t, "accepted": a, "card": "knight"} for t, a in xs]


class TestOff(unittest.TestCase):
    def test_hash_unchanged(self):
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_w18")
        for y in YAMLS:
            cfg = RL.load_config(y, [], False)
            self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg), y.name)

    def test_other_terms_unchanged(self):
        P = _pre("pipeline/reward_terms.py", "reward_terms_pre_w18")
        ticks = np.array([100, 110, 115, 120, 130, 140, 150, 160])
        pl = [{"tick": 115, "accepted": True, "card": "Tornado", "slot": 0}, {"tick": 130, "accepted": True, "card": "Knight", "slot": 1}]
        for crown in (lead_match(), tornado_match(True)):
            for p in ({"lead_protect": True, "lead_protect_w": .2}, {"princess_redirect": "penalty", "princess_redirect_w": .2},
                      {"tornado_king_penalty": True, "tornado_king_w": .01}):
                a, b = RT.row_terms(crown, pl, ticks, p), P.row_terms(crown, pl, ticks, p)
                np.testing.assert_array_equal(a.pop("r"), b.pop("r"))
                self.assertEqual(a, b)
                self.assertNotIn("play_cost", a)
                self.assertEqual(RT.bound(p), P.bound(p))
        self.assertIsNone(RL.crown_cfg({**BASE}))


class TestOn(unittest.TestCase):
    P = {"play_cost": True, "play_cost_w": .005}
    CROWN = {"lost": [], "falls": [], "tornados": [], "rockets": [], "end": None}

    def test_rows(self):
        ticks = np.array([100, 110, 120, 130])
        out = RT.row_terms(self.CROWN, plays((100, True), (110, False), (130, True), (125, True)), ticks, self.P)
        np.testing.assert_allclose(out["r"], [-.005, 0.0, 0.0, -.005])    # refused 110 and row-less 125 are free
        self.assertAlmostEqual(out["play_cost"], -.01)

    def test_cap(self):
        ticks = np.arange(0, 2000, 10)
        out = RT.row_terms(self.CROWN, plays(*((int(t), True) for t in ticks)), ticks, {"play_cost": True, "play_cost_w": .01})
        self.assertAlmostEqual(-out["r"].sum(), RT.PLAY_COST_MATCH_CAP)
        self.assertAlmostEqual(out["play_cost"], -RT.PLAY_COST_MATCH_CAP)
        self.assertAlmostEqual(RT.bound({"play_cost": True}), RT.PLAY_COST_MATCH_CAP)

    def test_config(self):
        self.assertEqual(RL.crown_cfg({**BASE, "play_cost": True}), {"play_cost": True, "play_cost_w": .005})
        for bad in ({"play_cost": "yes"}, {"play_cost_w": .01}, {"play_cost": True, "play_cost_w": -1}):
            with self.assertRaises(SystemExit, msg=bad):
                RL.crown_cfg({**BASE, **bad})
        cfg = RL.load_config(YAMLS[1], [], False)
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "play_cost": True}))
        self.assertEqual(RL.config_sha({**cfg, "play_cost": True}), RL.config_sha({**cfg, "play_cost": True, "play_cost_w": .005}))
        st = RT.batch_stats([], [RT.row_terms(self.CROWN, plays((100, True)), np.array([100]), self.P)])
        self.assertAlmostEqual(st["play_cost_reward_per_match"], -.005)


if __name__ == "__main__":
    unittest.main()
