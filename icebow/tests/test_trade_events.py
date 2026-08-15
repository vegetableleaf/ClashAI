"""Live elixir-trade v3: the attributed event ledger (2026-08-14). Drives the pure logic of
LiveMatchEnv._trade_events_live on a stub (the live env needs a capture device), covering the
four cases the aggregate potential could not distinguish: an attributed kill, a tower kill far
from our units, one-frame detector flicker, and our own loss."""
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                      # noqa: E402
from clashrl.env import LiveMatchEnv    # noqa: E402


class _Det:
    def __init__(self, team, base, cx, gy):
        self.team, self.base, self.cx, self.gy = team, base, cx, gy


class _Db:
    def elixir(self, base):
        return {"knight": 3, "pekka": 7, "skeletons": 1}.get(base, 0)


def _stub():
    e = types.SimpleNamespace()
    e._detector = object()
    e._last_dets_age = 0.0
    e._last_mass = 0.5
    e.quiet_frac = 0.02
    e._db = _Db()
    e.trade_kill_r = 4.0
    e.trade_match_r = 2.5
    e.value_norm = 10.0
    e.trade_cap = 1.0
    e.w_elixir_trade = 1.0
    e.phi_max_age = 0.6
    e._tr_prev_enemy = []
    e._tr_prev_mine = []
    e._tr_pend_en = []
    e._tr_pend_own = []
    e._trade_events_live = types.MethodType(LiveMatchEnv._trade_events_live, e)
    return e


def _step(e, dets):
    e._last_dets_all = dets
    return e._trade_events_live()


class TradeEventTests(unittest.TestCase):
    def test_attributed_kill_credits(self):
        e = _stub()
        own = _Det("mine", "knight", 0.50, 0.60)
        foe = _Det("enemy", "pekka", 0.52, 0.62)          # ~1.3 tiles from our knight
        _step(e, [own, foe])                              # snapshot
        _step(e, [own])                                   # pekka gone -> pending
        r = _step(e, [own])                               # still gone -> resolved near our unit
        self.assertAlmostEqual(r, 0.7, delta=1e-6, msg="7-elixir kill near our knight = +0.7")

    def test_tower_kill_far_from_units_pays_nothing(self):
        e = _stub()
        own = _Det("mine", "knight", 0.20, 0.60)
        foe = _Det("enemy", "pekka", 0.80, 0.75)          # far right, dies to the tower alone
        _step(e, [own, foe])
        _step(e, [own])
        r = _step(e, [own])
        self.assertEqual(r, 0.0, "no unit of ours nearby -> the tower's kill is not credited")

    def test_flicker_cancels(self):
        e = _stub()
        own = _Det("mine", "knight", 0.50, 0.60)
        foe = _Det("enemy", "pekka", 0.52, 0.62)
        _step(e, [own, foe])
        _step(e, [own])                                   # dropped for ONE frame...
        r = _step(e, [own, _Det("enemy", "pekka", 0.53, 0.63)])   # ...and it is back
        self.assertEqual(r, 0.0, "a one-frame track drop is flicker, not a kill")

    def test_own_loss_debits(self):
        e = _stub()
        own = _Det("mine", "knight", 0.50, 0.60)
        _step(e, [own])
        e._last_mass = 0.0                                # quiet board: the empty frames are real
        _step(e, [])                                      # knight gone -> pending
        r = _step(e, [])                                  # still gone -> resolved
        self.assertAlmostEqual(r, -0.3, delta=1e-6, msg="our dead knight = -0.3, whoever killed it")

    def test_blind_frames_hold(self):
        e = _stub()
        own = _Det("mine", "knight", 0.50, 0.60)
        foe = _Det("enemy", "pekka", 0.52, 0.62)
        _step(e, [own, foe])
        e._last_mass = 0.5
        r = _step(e, [])                                  # detector blind on an ACTIVE board
        self.assertEqual(r, 0.0)
        self.assertEqual(e._tr_prev_enemy[0][0], "pekka", "snapshots held through the blind frame")


if __name__ == "__main__":
    unittest.main(verbosity=1)
