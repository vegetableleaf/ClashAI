"""A3' (``reward_shaping.phi_trade2``, mode ``trade2``): Phi = w clip(b_e[phase] dE + b_t[phase] dT, +-cap).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_shaping_a3p.py

Pure python on synthetic raw() states; no engine. Sign, clip / bound, phase constants (pinned = the fit file), foe
king weight 0, terminal handling (telescoping), and that the existing modes are untouched (byte-identical Phi; trade2
stays out of STATE_PHI_MODES, so the trainer refuses it until its wiring ticket).
"""
from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import reward_shaping as RS                                 # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_shaping_step3 import (CARDS, KNIGHT, WITCH, P, ent, mirror, sstate,  # noqa: E402
                                               tstate)

W, CAP = P["shaping_t2_w"], P["shaping_t2_cap"]


def state(ents=(), e0=5.0, e1=5.0, own=(1, 1, 1), foe=(1, 1, 1), tick=1000):
    st = sstate(ents, e0, e1, tick=tick)
    st["episode"] = tstate(own, foe, tick=tick)["episode"]
    return st


def phi(st, est=5.0, side=0, **kw):
    return float(RS.phi_trade2(RS.trade2_record(st, side, CARDS, est), {**P, **kw})[0])


class TestTrade2(unittest.TestCase):
    def test_record_is_trade_row_plus_towers_and_tick(self):
        st = state([ent(1, WITCH, 9000, 20000, hp=400)], e0=3.0, own=(1, .5, 0), foe=(.8, 1, .25), tick=2500)
        r = RS.trade2_record(st, 0, CARDS, 6.0)
        self.assertEqual(len(r), 11)
        self.assertEqual(r[:4], RS.trade_record(st, 0, CARDS, 6.0))
        self.assertEqual(r[4:10], RS.tower_score_record(st, 0)[:6])
        self.assertEqual(r[10], 2500.0)
        with self.assertRaises(ValueError):                                # public counter only, never truth
            RS.trade2_record(st, 0, CARDS, None)

    def test_sign_tower_and_trade(self):
        base = phi(state(tick=3000))
        self.assertEqual(base, 0.0)                                        # the start state: Phi = 0
        self.assertGreater(phi(state(foe=(1, .6, 1), tick=3000)), base)    # their princess damaged -> up
        self.assertGreater(phi(state(foe=(1, 0, 1), tick=3000)), phi(state(foe=(1, .6, 1), tick=3000)))
        self.assertLess(phi(state(own=(1, .6, 1), tick=3000)), base)       # mine damaged -> down
        self.assertLess(phi(state(own=(.9, 1, 1), tick=3000)), base)       # my king counts (x KING_PER_PRINCESS)
        # a favourable trade: 4 elixir (Fireball) removes their 5-elixir Witch -> +1 elixir margin
        before = state([ent(1, WITCH, 9000, 20000)], e0=5.0, tick=3000)
        after = state([], e0=1.0, tick=3000)
        self.assertAlmostEqual(phi(after) - phi(before), W * RS.TRADE2_B[1][0] * 1.0)
        # a play is neutral when it lands
        placed = state([ent(0, KNIGHT, 3000, 9000), ent(1, WITCH, 9000, 20000)], e0=2.0, tick=3000)
        self.assertAlmostEqual(phi(placed), phi(before))

    def test_foe_king_weight_zero(self):
        self.assertEqual(phi(state(foe=(.3, 1, 1), tick=3000)), phi(state(tick=3000)))

    def test_clip_and_bound(self):
        self.assertAlmostEqual(phi(state(own=(1, 0, 0), tick=5000)), -RS.phi_bound("trade2", P))
        self.assertAlmostEqual(phi(state(foe=(1, 0, 0), e0=10.0, tick=5000), est=0.0), RS.phi_bound("trade2", P))
        self.assertAlmostEqual(RS.phi_bound("trade2", P), W * CAP)
        self.assertLessEqual(RS.phi_bound("trade2", P), 0.5)
        rng = np.random.default_rng(0)
        rows = np.c_[rng.uniform(0, 40, (5000, 4)), rng.uniform(0, 1, (5000, 6)), rng.uniform(0, 7000, 5000)]
        self.assertLessEqual(float(np.abs(RS.state_phi("trade2", rows, P)).max()), W * CAP + 1e-12)

    def test_side_symmetry_kings_full(self):
        st = state([ent(0, KNIGHT, 3000, 9000), ent(1, WITCH, 9000, 20000, hp=400)], e0=2.0, e1=7.0,
                   own=(1, .4, 1), foe=(1, 1, .7), tick=4000)
        self.assertAlmostEqual(phi(st, 7.0, side=0), -phi(st, 2.0, side=1))       # exact counters: zero-sum
        self.assertAlmostEqual(phi(st, 7.0, side=0), phi(mirror(st), 7.0, side=1))  # the other seat, same board

    def test_phase_constants(self):
        """b by phase at the tick boundaries, and the pinned numbers = the fit file's printed coefficients."""
        row = (lambda tick: [6, 0, 5, 0, 1, 1, 1, 1, 1, 1, tick])        # dE = +1, dT = 0 -> Phi = w b_e
        for tick, ph in ((0, 0), (2399, 0), (2400, 1), (3599, 1), (3600, 2), (7000, 2)):
            self.assertAlmostEqual(float(RS.phi_trade2([row(tick)], P)[0]), W * RS.TRADE2_B[ph][0])
        fit = (REPO / "scratchpad/gauntlet/L74/reward/RHO_FIT_R1_A3P.txt").read_text(encoding="utf-8")
        got = [tuple(float(x) for x in m) for m in
               re.findall(r"b_elixir \+([\d.]+) .*? b_tower \+([\d.]+)", fit)]
        self.assertEqual(got, [tuple(b) for b in RS.TRADE2_B])

    def test_terminal_and_telescoping(self):
        """Phi = 0 after the last kept row: sum F = -Phi(s0) at gamma 1, the per-row-gamma discounted sum too, and the
        last step's F = -Phi(s_{T-1})."""
        rng = np.random.default_rng(1)
        rows = np.c_[rng.uniform(0, 15, (80, 4)), rng.uniform(0, 1, (80, 6)), np.sort(rng.uniform(0, 7000, 80))]
        ph = RS.state_phi("trade2", rows, P)
        out = RS.shaping_from_parts(ph.tolist(), [0.0] * len(ph), 1.0, (1.0, 0.0))
        self.assertAlmostEqual(sum(out["F"]), -ph[0], places=12)
        self.assertEqual(out["phi"][-1], 0.0)
        self.assertAlmostEqual(out["F"][-1], -ph[-1], places=12)
        g = rng.uniform(0.99, 1.0, len(ph))
        F = RS.shaping_from_parts(ph.tolist(), [0.0] * len(ph), g, (1.0, 0.0))["F"]
        self.assertAlmostEqual(float((np.r_[1.0, np.cumprod(g[:-1])] * F).sum()), -ph[0], places=12)

    def test_state_record_dispatch(self):
        env = SimpleNamespace(core=SimpleNamespace(cards=lambda: [
            SimpleNamespace(card_id=0, elixir=3, count=1, hitpoints=1766, card_kind="TROOP")]))
        st = state([ent(1, KNIGHT, 3000, 25000)], e0=4.0, foe=(1, .5, 1), tick=3000)
        mem = {"opp_est": 6.0}
        self.assertEqual(RS.state_record("trade2", st, 0, env, mem), RS.trade2_record(st, 0, mem["cards"], 6.0))


class TestAbsentModeIdentity(unittest.TestCase):
    def test_existing_modes_byte_identical(self):
        """sha256 of the existing modes' Phi on fixed random rows, recorded BEFORE trade2 was added (10-16)."""
        rng = np.random.default_rng(1)
        out = [RS.state_phi("solvency", rng.uniform(0, 30, (500, 5)), P),
               RS.state_phi("trade", rng.uniform(0, 20, (500, 4)), P),
               RS.state_phi("tower_score", np.c_[rng.uniform(0, 1, (500, 8)), rng.integers(0, 3, (500, 2)),
                                                 rng.uniform(0, 7000, 500)], P),
               np.array([RS.phi_bound(m, P) for m in ("solvency", "trade", "tower_score")])]
        self.assertEqual(hashlib.sha256(b"".join(o.tobytes() for o in out)).hexdigest(),
                         "486dbc7e6dd82f40a857454aa95ff4e6c0f2fdc98688172740d9f33b7309d9dc")

    def test_trainer_refuses_trade2_until_wired(self):
        self.assertEqual(RS.STATE_PHI_MODES, ("solvency", "tower_score", "trade"))
        with self.assertRaises(SystemExit):
            RL.adv_cfg({"advantage": "gae", "critic_warmup_updates": 5, "shaping": "trade2",
                        "opp_elixir": "counter"})


if __name__ == "__main__":
    unittest.main()
