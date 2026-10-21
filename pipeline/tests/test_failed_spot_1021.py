"""10-21: a lost tap's spot is avoided after FAIL_N failures for FAIL_BLOCK_TICKS (live_gen.GenPilot mixin methods)."""
import numpy as np
import torch

from pipeline import live_gen
from pipeline.live_gen import cell_xy


class _P:
    FAIL_N, FAIL_BLOCK_TICKS, FAIL_RADIUS = live_gen.GenPilot.FAIL_N, live_gen.GenPilot.FAIL_BLOCK_TICKS, \
        live_gen.GenPilot.FAIL_RADIUS
    note_unconfirmed = live_gen.GenPilot.note_unconfirmed
    _mask_failed = live_gen.GenPilot._mask_failed

    def __init__(self, grid):
        self.grid = grid


def _setup():
    p = _P("lattice")
    n = 36 * 64
    logits = torch.zeros(1, n)
    target = 5
    logits[0, target] = 10.0
    xy = cell_xy(target, p.grid)
    return p, logits, target, xy


def test_one_failure_does_not_block():
    p, logits, target, xy = _setup()
    p.note_unconfirmed("Knight", xy, 100)
    out = p._mask_failed({"game_tick": 110}, {"name": "Knight"}, logits)
    assert int(out.argmax()) == target


def test_two_failures_block_then_expire():
    p, logits, target, xy = _setup()
    p.note_unconfirmed("Knight", xy, 100)
    p.note_unconfirmed("Knight", xy, 140)
    d = {"name": "Knight"}
    out = p._mask_failed({"game_tick": 150}, d, logits)
    assert int(out.argmax()) != target and d.get("avoided_failed_spot")
    assert int(p._mask_failed({"tick": 140 + p.FAIL_BLOCK_TICKS + 1}, {"name": "Knight"}, logits).argmax()) == target


def test_other_card_unaffected():
    p, logits, target, xy = _setup()
    p.note_unconfirmed("Knight", xy, 100)
    p.note_unconfirmed("Knight", xy, 140)
    assert int(p._mask_failed({"game_tick": 150}, {"name": "Skeletons"}, logits).argmax()) == target


def test_no_failures_identity():
    p, logits, target, _ = _setup()
    assert torch.equal(p._mask_failed({"game_tick": 1}, {"name": "Knight"}, logits), logits)
