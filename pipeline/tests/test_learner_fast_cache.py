"""LEARNER-SCALE ``mem_row_cache`` (rl_royale.MemRowCache / gen_rows): the MEM_KEYS rows served from the per-update cache are
byte-identical to e1_eval.gen_batch's per-call rebuild, for any order / overlap of row requests; no cache = gen_batch.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_learner_fast_cache.py

Fixture: test_match_memory's rich synthetic matches packed into one table set (the same construction as its
test_pack_and_rows_features), wrapped in a collated-batch-shaped B; a stub model with a v1 memory.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                          # noqa: E402
from pipeline import match_memory as M                                     # noqa: E402
from pipeline import rl_royale as RL                                       # noqa: E402
from pipeline.tests.test_match_memory import DECK, GID, rich_match         # noqa: E402

N = 60


def _batch():
    mms = [M.build(*rich_match(500 + s)) for s in range(3)]
    packed = M.pack([m.table(GID) for m in mms])
    deck = np.array([GID.get(M.card_key(c), 0) for c in DECK])
    rng = np.random.default_rng(1)
    B = {k: torch.arange(N) for k in E.GEN_ROW_KEYS}                       # gen_batch only indexes these
    B["deck_card"] = torch.from_numpy(np.tile(deck, (N, 1)))
    B["sc"] = torch.zeros(N, 3)
    B["A"] = torch.zeros(N)
    B.update({f"mem_tab_{k}": v for k, v in packed.items()})
    B["mem_row_tab"] = rng.integers(0, 3, N)
    B["mem_row_t"] = rng.integers(0, 4200, N)
    model = SimpleNamespace(feature_version=1, mem=SimpleNamespace(version="v1", gid=None))
    return B, model


def _same(a, b):
    assert a.keys() == b.keys()
    for k in a:
        assert a[k].dtype == b[k].dtype and torch.equal(a[k], b[k]), k


def test_cache_equals_gen_batch_any_order():
    B, model = _batch()
    Bc = dict(B, _mem_cache=RL.MemRowCache(N))
    rng = np.random.default_rng(2)
    for _ in range(12):                                                    # overlapping, unsorted, repeated rows
        idx = torch.from_numpy(rng.choice(N, int(rng.integers(1, 25)), replace=bool(rng.integers(0, 2))))
        _same(RL.gen_rows(model, Bc, idx), E.gen_batch(model, B, idx))
    assert Bc["_mem_cache"].have.sum() > 0


def test_no_cache_is_gen_batch_and_subset_drops_it():
    B, model = _batch()
    idx = torch.arange(0, N, 3)
    _same(RL.gen_rows(model, B, idx), E.gen_batch(model, B, idx))
    Bc = dict(B, _mem_cache=RL.MemRowCache(N))
    assert "_mem_cache" not in RL.row_subset(Bc, torch.arange(10))


def test_other_memory_version_falls_back():
    B, model = _batch()
    Bc = dict(B, _mem_cache=RL.MemRowCache(N))
    RL.gen_rows(model, Bc, torch.arange(5))
    other = SimpleNamespace(feature_version=1, mem=SimpleNamespace(version="v1", gid={"x": 1}))
    calls = []
    real = E.gen_batch
    E.gen_batch = lambda *a: calls.append(1) or real(*a)
    try:
        RL.gen_rows(other, Bc, torch.arange(5))
    finally:
        E.gen_batch = real
    assert calls == [1]
