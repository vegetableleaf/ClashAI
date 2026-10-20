"""L74 W7 (10-20): the opt-in crown term ``princess_take`` (pipeline/reward_terms.py; the SIM opponent's crown-aware
objective, opp_model/OPP_MODEL.md section 7).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_princess_take_1020.py

Covers: absent = the pre-change module (PRE = 0bcc4c5, the last commit before W7): the config hash of rl_royale.yaml, the
L16 recipe and the W7 C1 arm; crown_cfg None; every W6 term's row_terms output and batch_stats byte-identical; on: +w on
the last kept row at or before each ENEMY princess fall in play (own falls and the tiebreak tower never pay), its bound,
validation and a distinct hash."""
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

PRE = "0bcc4c5"
YAMLS = (REPO / "pipeline/rl_royale.yaml", REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml",
         REPO / "scratchpad/gauntlet/L74/opp_model/cfg/oppC1_icemix_s74.yaml")
BASE = {"advantage": "gae", "league": True, "critic_warmup_updates": 5, "shaping_critic_scale": 1.5}
TICKS = np.array([100, 115, 135, 145, 155])


def _pre_rt():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/reward_terms.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("reward_terms_pre_w7")
    mod.__file__ = str(REPO / "pipeline" / "reward_terms.py")
    exec(compile(src.stdout, "reward_terms_pre_w7", "exec"), mod.__dict__)
    return mod


def falls(*fs):
    return {"lost": [], "tornados": [], "rockets": [], "end": None,
            "falls": [{"tick": t, "who": w, "before": [0, 0]} for t, w in fs]}


class TestAbsentIdentical(unittest.TestCase):
    def test_hash_and_crown_cfg(self):
        P = _pre_rt()
        for path in YAMLS:
            cfg = RL.load_config(path, [], False)
            self.assertIsNone(RL.crown_cfg(cfg), path.name)
            h = RL.config_sha(cfg)
            saved = RL.RT
            try:
                RL.RT = P
                self.assertEqual(RL.config_sha(cfg), h, path.name)       # the pre-W7 module's hash
            finally:
                RL.RT = saved
            for off in (None, False):
                self.assertEqual(RL.config_sha({**cfg, "princess_take": off}), h)

    def test_w6_terms_unchanged(self):
        P = _pre_rt()
        plays = [{"tick": 85, "land_tick": 111, "card": "Tornado", "accepted": True}]
        ticks = np.array([85, 95, 125])
        for p in ({}, {"lead_protect": True, "lead_protect_w": 0.2},
                  {"princess_redirect": "penalty", "princess_redirect_w": 0.2},
                  {"princess_redirect": "potential", "princess_redirect_w": 0.2},
                  {"tornado_king_penalty": True, "tornado_king_w": 0.01}):
            for c, tk, pl in ((lead_match(), TICKS, []), (tornado_match(down=True), ticks, plays)):
                a, b = RT.row_terms(c, pl, tk, p), P.row_terms(c, pl, tk, p)
                self.assertEqual(set(a), set(b), p)
                np.testing.assert_array_equal(a["r"], b["r"])
                self.assertEqual({k: v for k, v in a.items() if k not in ("r", "phi")},
                                 {k: v for k, v in b.items() if k not in ("r", "phi")})
                self.assertEqual(RT.bound(p), P.bound(p))
                s = [RT.match_summary(c)]
                self.assertEqual(RT.batch_stats(s, [a]), P.batch_stats(s, [b]))


class TestTake(unittest.TestCase):
    P = {"princess_take": True, "princess_take_w": 0.2}

    def test_rows(self):
        # foe falls at 130 (last kept row <= 130: 115) and 150 (row 145) pay; the own fall at 140 pays nothing;
        # a foe fall at the tiebreak (>= 5990) pays nothing; a fall before the first kept row has no row
        r = RT.row_terms(falls((130, "foe"), (140, "own"), (150, "foe"), (5995, "foe"), (90, "foe")), [], TICKS, self.P)
        np.testing.assert_allclose(r["r"], [0.0, 0.2, 0.0, 0.2, 0.0])
        self.assertAlmostEqual(r["take"], 0.4)
        self.assertEqual(r["lead"], 0.0)
        own = RT.row_terms(falls((130, "own"), (150, "own")), [], TICKS, self.P)
        self.assertFalse(own["r"].any())
        self.assertEqual(own["take"], 0.0)

    def test_with_lead_protect(self):
        p = {**self.P, "lead_protect": True, "lead_protect_w": 0.2}
        c = lead_match()                       # we take their L at 130 (row 115), then our L falls at 150 while 1-0 (row 145)
        r = RT.row_terms(c, [], TICKS, p)
        np.testing.assert_allclose(r["r"], [0.0, 0.2, 0.0, -0.2, 0.0])

    def test_bound_cfg_hash(self):
        self.assertAlmostEqual(RT.bound(self.P), 0.4)
        self.assertEqual(RL.crown_cfg({**BASE, "princess_take": True}), self.P)
        RL.adv_cfg({**BASE, "princess_take": True})                       # 1 + 0.4 <= 1.5
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**BASE, "princess_take": True, "shaping_critic_scale": 1.3})
        for bad in ({"princess_take": "yes"}, {"princess_take_w": 0.3}, {"princess_take": True, "princess_take_w": -1}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.crown_cfg({**BASE, **bad})
        cfg = RL.load_config(YAMLS[2], [], False)
        h, on = RL.config_sha(cfg), RL.config_sha({**cfg, "princess_take": True})
        self.assertNotEqual(on, h)
        self.assertEqual(RL.config_sha({**cfg, "princess_take": True, "princess_take_w": 0.2}), on)
        self.assertNotEqual(RL.config_sha({**cfg, "princess_take": True, "princess_take_w": 0.4}), on)

    def test_batch_stats(self):
        c = falls((130, "foe"))
        on = RT.batch_stats([RT.match_summary(c)], [RT.row_terms(c, [], TICKS, self.P)])
        self.assertAlmostEqual(on["take_reward_per_match"], 0.2)
        off = RT.batch_stats([RT.match_summary(c)], [RT.row_terms(c, [], TICKS, {})])
        self.assertNotIn("take_reward_per_match", off)


if __name__ == "__main__":
    unittest.main()
