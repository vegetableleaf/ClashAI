"""pipeline.batched_rollout: the worker-side decide (threads + one cell wave through a stub) returns exactly what the
actor path's decide returns on the same heads and RNGs (sample_decide_batch for a group, styled_decisions per row), and
every decide of a round shares ONE cell wave. Engine-free; the end-to-end identity on real matches is
scratchpad/gauntlet/L74/speed/SPEED.md section d (harness.py ref vs batched + compare.py)."""
import types

import numpy as np
import torch

from pipeline import adaptive_opponents as AO
from pipeline import batched_rollout as BR
from pipeline import e1_eval as E

D, B = 16, 12


class Cell:
    """A cell head stand-in: logits = g @ W[slot]."""

    def __init__(self):
        self.W = torch.randn(E.N_SLOTS, D, E.N_CELLS, generator=torch.Generator().manual_seed(0))

    def cell_logits(self, enc, slot):
        return torch.einsum("bd,bdc->bc", enc["g"], self.W[slot.long()])


def heads(seed=1):
    r = np.random.default_rng(seed)
    gate = r.normal(0.5, 1.0, B).astype(np.float32)
    card = r.normal(0, 1, (B, E.N_SLOTS)).astype(np.float32)
    return (gate, card, np.zeros((B, 4), np.float32), 1 / (1 + np.exp(-gate.astype(np.float64))),
            np.ones((B, E.N_SLOTS), bool), r.normal(0, 1, (B, D)).astype(np.float32))


def sides(cfg, seed=7):
    out = []
    for r in range(B):
        allowed = np.zeros(E.N_SLOTS, bool)
        allowed[[r % 8, (r + 3) % 8, (r + 5) % 8]] = True
        s = types.SimpleNamespace(cfg=cfg, rng_behave=np.random.default_rng(seed + r), side=0, tag=f"t{r}", n_dec=0,
                                  _cur=(0, None, types.SimpleNamespace(units=[], my_elixir=6.0)),
                                  deck=types.SimpleNamespace(card_ids=list(range(1, 9))))
        s.pre = (lambda hand, a=allowed, st=(r % 5 == 0): (6.0, a, st))
        out.append(s)
    return out


def direct(model, cfg, out, ss):
    gate, card, ch, p, hand, g = out
    pre = [s.pre(hand[r]) for r, s in enumerate(ss)]
    allowed, stalled = np.stack([x[1] for x in pre]), np.array([x[2] for x in pre])
    h = {"gate": torch.from_numpy(gate), "card": torch.from_numpy(card), "card_hand": torch.from_numpy(ch)}
    if "_opp_style" in cfg:
        return AO.styled_decisions(model, {"g": torch.from_numpy(g)}, h, list(p), allowed, stalled, ss)
    return E.sample_decide_batch(model, {"g": torch.from_numpy(g)}, h, list(p), allowed, stalled, ss, cfg)


def batched(model, cfg, out, ss, key):
    calls = []

    def serve(reqs):
        calls.append(len(reqs))
        g = out[5]
        return [model.cell_logits({"g": torch.from_numpy(g[rows])}, torch.from_numpy(slot)).numpy()
                for _, rows, slot in reqs]
    res = BR.decide_groups({key: ss}, {key: out}, BR.Waves(), serve)
    return res[key][1], calls


def same(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.keys() == y.keys()
        for k in x:
            assert (np.array_equal(x[k], y[k]) if isinstance(x[k], np.ndarray) else x[k] == y[k]), (k, x[k], y[k])


def test_sample_group_identical_one_wave():
    m, cfg = Cell(), {"tau": 0.35, "T": 0.5, "policy": "sample", "device": "cpu"}
    out = heads()
    want = direct(m, cfg, out, sides(cfg))
    got, calls = batched(m, cfg, out, sides(cfg), (0, False))
    same(want, got)
    assert sum(d["play"] for d in want) >= 3
    assert calls == [1]                          # one group = one task = one cell request in one wave


def test_styled_rows_identical_one_wave():
    m = Cell()
    cfg = {"tau": 0.35, "T": 0.5, "policy": "sample", "device": "cpu",
           "_opp_style": {"bank": 0.0, "lane_bias": 0.3, "spell_delay": 2}}
    out = heads(3)
    want = direct(m, cfg, out, sides(cfg, 11))
    got, calls = batched(m, cfg, out, sides(cfg, 11), (1, True))
    same(want, got)
    n_play = sum(d["play"] for d in want)
    assert n_play >= 3 and calls == [n_play]     # per-row decodes, all their cell calls answered in ONE wave


def test_waves_reraise():
    def bad():
        raise KeyError("x")
    try:
        BR.Waves().run([bad, lambda: 1], lambda reqs: [])
    except KeyError:
        return
    raise AssertionError("a task's exception must reach the caller")
