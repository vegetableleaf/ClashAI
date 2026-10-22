"""W21 10-22 (L74/livetaps): the hero-button cell mask (GenPilot._mask_ui) and the per-match reset of the lost-spot blocks."""
from collections import deque

import numpy as np
import torch

from pipeline import live_gen
from pipeline.live_gen import cell_xy

N = 36 * 64


class _P:
    FAIL_N, FAIL_BLOCK_TICKS, FAIL_RADIUS = live_gen.GenPilot.FAIL_N, live_gen.GenPilot.FAIL_BLOCK_TICKS, \
        live_gen.GenPilot.FAIL_RADIUS
    note_unconfirmed = live_gen.GenPilot.note_unconfirmed
    _mask_failed = live_gen.GenPilot._mask_failed
    _mask_ui = live_gen.GenPilot._mask_ui
    reset_match = live_gen.GenPilot.reset_match
    ui_blocked = None

    def __init__(self):
        self.grid, self.past, self.history, self.frames, self.opp = "lattice", [], {}, deque(), None


def _logits(target=5):
    lg = torch.zeros(1, N)
    lg[0, target] = 10.0
    return lg


def test_ui_mask_off_is_identity():
    p, lg = _P(), _logits()
    d = {}
    assert torch.equal(p._mask_ui(d, lg), lg) and "ui_guard" not in d


def test_ui_mask_moves_a_covered_argmax():
    p, lg = _P(), _logits(5)
    p.ui_blocked = np.zeros(N, bool)
    p.ui_blocked[5] = True
    d = {}
    out = p._mask_ui(d, lg)
    assert int(out.argmax()) != 5 and d["ui_guard"] == cell_xy(5, "lattice")


def test_ui_mask_uncovered_argmax_kept_and_unflagged():
    p, lg = _P(), _logits(5)
    p.ui_blocked = np.zeros(N, bool)
    p.ui_blocked[7] = True
    d = {}
    assert int(p._mask_ui(d, lg).argmax()) == 5 and "ui_guard" not in d


def test_reset_match_clears_lost_spot_blocks():
    p, lg = _P(), _logits(5)
    xy = cell_xy(5, "lattice")
    p.note_unconfirmed("Rocket", xy, 6100)          # two losses in the drain of match k: blocked until tick 6500
    p.note_unconfirmed("Rocket", xy, 6140)
    assert int(p._mask_failed({"game_tick": 300}, {"name": "Rocket"}, lg).argmax()) != 5   # the old leak into match k + 1
    p.ui_blocked = np.ones(N, bool)
    p.reset_match()
    assert int(p._mask_failed({"game_tick": 300}, {"name": "Rocket"}, lg).argmax()) == 5 and p.ui_blocked is None
