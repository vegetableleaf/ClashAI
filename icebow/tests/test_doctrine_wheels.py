"""Doctrine training wheels for the DEFENDERS, and the buffer fix that has to ship with them
(user request, 2026-08-19: "add every component of the icebow doctrine to the training wheels").

WHAT WAS ALREADY WHEELED before this: x_bow lane/lock/depth, tesla centre-pull, rocket
weaker-tower/pump/intercept (all unconditional, predating the flag), plus the 08-19 spell wheels
(log corridor, tornado king-activation, any spell -> nearest enemy). The gap was the pure
defenders -- knight, skeletons, ice_wizard -- which is where this deck's defence lives.

THE PREREQUISITE, and the reason it is tested here rather than separately: train_rl stored the
action the POLICY chose while env.step executed a doctrine-corrected CELL. With wheels on nearly
every card that gap becomes the norm and it teaches backwards -- the model's own bad cell is
credited with the corrected cell's reward, so it learns the mistake was right and the wheel can
never come off. Q-learning is off-policy; the EXECUTED action is what belongs in the buffer.

The real method is exercised against a stub shaped like the live env, because nothing can build a
LiveMatchEnv in a test (it needs a window and a detector) -- the same hole that let a tuple weight
reach a live match earlier tonight.
"""
from __future__ import annotations

import ast
import io
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.actions import ActionSpace          # noqa: E402
from clashrl.config import Config                # noqa: E402
from clashrl.env import LiveMatchEnv             # noqa: E402
from clashrl.reward import _anchors              # noqa: E402


class _Vision:
    def __init__(self, keys):
        self.deck_keys = list(keys)


class _Det:
    def __init__(self, base, cx, gy, team):
        self.base, self.cx, self.gy, self.team = base, cx, gy, team


class _Stub:
    """Only the attributes _wheels_troop_aim actually reads."""

    DECK = ["tornado", "tesla", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight",
            "knight_evo", "the_log", "skeletons"]

    def __init__(self, tracks=(), dets=()):
        cfg = Config.load()
        self.cfg = cfg                      # the wheels read the real tower anchors from it
        self.actions = ActionSpace(cfg)
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.vision = _Vision(self.DECK)
        self.n_cards = len(self.DECK)
        self.training_wheels = True
        self._last_dets_all = list(dets)
        self._tracks = list(tracks)

    # the real method calls these two on self
    def _enemy_tracks_now(self):
        return self._tracks

    _base_of = LiveMatchEnv._base_of
    _my_xbow_live = LiveMatchEnv._my_xbow_live

    def cell_of(self, nx, ny):
        gx, gy = self.actions.coords_to_grid(nx, ny)
        return int(gy) * self.gw + int(gx)

    def coords_of(self, cell):
        return self.actions.cell_center(cell % self.gw, cell // self.gw)


def aim(stub, card, cell):
    return LiveMatchEnv._wheels_troop_aim(stub, _Stub.DECK.index(card), cell)


def cell_diag(stub, cell):
    """One grid cell, in board units, near `cell` -- the finest a placement can be expressed.
    Measured per deck: the two decks' board warps quantise the same point differently."""
    gx, gy = cell % stub.gw, cell // stub.gw
    x0, y0 = stub.actions.cell_center(gx, gy)
    x1, _ = stub.actions.cell_center(min(gx + 1, stub.gw - 1), gy)
    _, y1 = stub.actions.cell_center(gx, min(gy + 1, stub.gh - 1))
    return math.hypot(x1 - x0, y1 - y0)


def _scene():
    """A threat and a bow placed from THIS deck's own tower anchors, so the doctrine assertions
    below mean the same thing on a board with different calibration (hogeq's differs)."""
    cfg = Config.load()
    mine, enemy, _ = _anchors(cfg)
    princess_y = float(mine[0][1])
    king_y = float(mine[2][1]) if len(mine) >= 3 else princess_y + 0.10
    river_y = 0.5 * (float(enemy[0][1]) + princess_y)
    lane_x = float(mine[0][0])
    a = ActionSpace(cfg)
    row = 1.0 / int(a.gh)
    # the attacker is a third of the way from the river to our tower line: past the bridge, with
    # room BEHIND it for a body-block that is not already inside the king footprint.
    ty = river_y + (princess_y - river_y) / 3.0
    # the bow sits deeper still, and clear of the king so "behind the bow" stays deployable
    by = min(ty + 3 * row, king_y - 3 * row)
    return (lane_x, ty, 0, 0), _Det("x_bow", lane_x + 0.03, by, "mine")


THREAT, BOW = _scene()


class DefenderPlacementTests(unittest.TestCase):
    def test_skeletons_go_onto_the_attacker(self):
        s = _Stub(tracks=[THREAT])
        cell = aim(s, "skeletons", s.cell_of(0.80, THREAT[1] + 0.04))
        got = s.coords_of(cell)
        self.assertLessEqual(math.hypot(got[0] - THREAT[0], got[1] - THREAT[1]),
                             cell_diag(s, cell) * 1.2,
                             "skeletons were not placed on the attacker")

    def test_knight_bodyblocks_between_the_attacker_and_our_tower(self):
        """No bow out: the knight is a body-block, not a chase -- deeper than the attacker
        (our towers are at the HIGH-y end), not behind it."""
        s = _Stub(tracks=[THREAT])
        got = s.coords_of(aim(s, "knight", s.cell_of(0.80, THREAT[1] - 0.05)))
        self.assertGreater(got[1], THREAT[1], "the knight was placed behind the attacker")
        self.assertLess(abs(got[0] - THREAT[0]), 0.10, "the knight was placed out of the lane")

    def test_knight_guards_the_bow_when_one_is_out(self):
        """With a bow on the board the knight is its bodyguard: one row from the BOW, on the
        threat's side -- so the answer walking at the bow meets him first."""
        s = _Stub(tracks=[THREAT], dets=[BOW])
        got = s.coords_of(aim(s, "knight", s.cell_of(0.80, THREAT[1] - 0.05)))
        row = 1.0 / s.gh
        self.assertLess(abs(got[0] - BOW.cx), 0.06, "the knight left the bow's column")
        self.assertLess(got[1], BOW.gy, "the knight was not placed on the THREAT's side of the bow")
        self.assertLess(abs(got[1] - (BOW.gy - row)), 1.5 * row, "not one row in front of the bow")

    def test_ice_wizard_sits_behind_and_offset(self):
        """He is the multiplier, never the kill -- and he must not share a spell radius with the
        bow, so the placement is offset sideways as well as deeper."""
        s = _Stub(tracks=[THREAT], dets=[BOW])
        got = s.coords_of(aim(s, "ice_wizard", s.cell_of(0.20, THREAT[1] - 0.05)))
        self.assertGreater(got[1], BOW.gy, "the ice wizard was not placed BEHIND the bow")
        self.assertGreater(abs(got[0] - BOW.cx), 0.02, "he was stacked in the bow's own column")

    def test_a_quiet_board_is_left_to_the_model(self):
        """Nothing past the river = nothing to body-block; pre-placing is the model's call."""
        enemy_y = float(_anchors(Config.load())[1][0][1])
        s = _Stub(tracks=[(THREAT[0], enemy_y + 0.02, 0, 0)])     # still on THEIR side
        cell = s.cell_of(THREAT[0], THREAT[1])
        self.assertEqual(cell, aim(s, "knight", cell))

    def test_a_placement_that_is_already_doctrinal_is_not_moved(self):
        """The wheels exist to stop donations, not to freeze the cell head."""
        s = _Stub(tracks=[THREAT])
        cell = s.cell_of(THREAT[0], THREAT[1])
        self.assertEqual(cell, aim(s, "skeletons", cell))

    def test_cards_without_a_rule_are_untouched(self):
        """x_bow / tesla / rocket have their own assists further down step(); the troop wheels
        must not fight them."""
        s = _Stub(tracks=[THREAT])
        for card in ("x_bow", "tesla", "rocket", "the_log"):
            cell = s.cell_of(0.62, THREAT[1] - 0.05)
            self.assertEqual(cell, aim(s, card, cell), "%s was moved by the troop wheels" % card)

    def test_it_never_aims_into_our_own_king_tower(self):
        """A tap on the king footprint places NOTHING: the card is spent and the board is empty."""
        mine = _anchors(Config.load())[0]
        kx, ky = (mine[2] if len(mine) >= 3 else (0.495, 0.72))
        s = _Stub(tracks=[(kx, ky - 0.02, 0, 0)])          # a push right on top of our king
        for card in ("knight", "skeletons", "ice_wizard"):
            x, y = s.coords_of(aim(s, card, s.cell_of(0.10, THREAT[1])))
            self.assertFalse(abs(x - kx) < 0.06 and y > ky - 0.06,
                             "%s was aimed into the king footprint at (%.2f, %.2f)" % (card, x, y))
            self.assertLessEqual(y, ky + 0.01, "%s was placed behind the king" % card)


class ExecutedActionTests(unittest.TestCase):
    """The buffer must learn from the cell that was PLAYED, not the one the policy asked for."""

    def _src(self, name):
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", name)
        with io.open(p, encoding="utf-8") as fh:
            return fh.read()

    def test_step_records_the_executed_action_after_every_aim_assist(self):
        tree = ast.parse(self._src("env.py"))
        step = next((f for f in ast.walk(tree)
                     if isinstance(f, ast.FunctionDef) and f.name == "step"), None)
        self.assertIsNotNone(step, "live env.py has no step()")
        rec = [n for n in ast.walk(step)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Attribute) and t.attr == "_last_exec_action"
                       for t in n.targets)]
        self.assertTrue(rec, "step() no longer records the executed action")
        aims = [n.lineno for n in ast.walk(step)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("_wheels_troop_aim", "_wheels_spell_aim",
                                    "_aim_rocket_intercept", "_aim_weaker_tower")]
        self.assertTrue(aims, "the aim assists vanished from step()")
        self.assertGreater(rec[0].lineno, max(aims),
                           "the executed action is recorded BEFORE the assists rewrite the cell")

    def test_train_rl_stores_the_executed_action_in_the_replay_buffer(self):
        src = self._src("train_rl.py")
        self.assertIn("_last_exec_action", src,
                      "train_rl went back to storing the action the policy chose")
        line = next(ln for ln in src.splitlines() if ln.strip().startswith("raw = (obs, hand,"))
        self.assertIn("taken", line,
                      "the replay transition still stores the CHOSEN action: %s" % line.strip())


if __name__ == "__main__":
    unittest.main(verbosity=1)
