"""Skew 10-25 (scratchpad/gauntlet/L74/memory/skew/): the memory adapter's no-offset form (model_gen MemoryEncoder
``zero_empty``).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_zero_empty.py -q

The S3 v1 adapter (train_memory, coupling ``out`` weight AND bias trainable) learned a memory-INDEPENDENT offset: its output
for an EMPTY memory has L2 18.2 in the 1,896-d global vector. It lowers the gate on every state (SIM, the memory model's own
states: mean gate p 0.31 -> 0.19 with an empty memory) and the memory model fed an EMPTY memory loses as much as with its
real memory (E4 paired: 37.8% / 35.1% vs CLXIII 78.4%). zero_empty: out(rep) - out(rep of an empty memory) = W (rep -
rep_empty), so an empty memory adds exactly 0 whatever the weights: the memory model with an empty memory IS its base."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'pipeline' / 'model_gen.py').is_file())
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import match_memory as MM                                  # noqa: E402
from pipeline import model_gen as MG                                     # noqa: E402

DATA = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
CKPT = REPO / "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"


def _live(enc, seed=0):
    """Nonzero coupling (weight AND bias: what S3 trains) so the encoder moves outputs."""
    g = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for p in enc.parameters():
            p.copy_(torch.randn(p.shape, generator=g) * 0.1)
    return enc


def _inputs(B=4, E=6, d_c=8, version="v1"):
    """B memory rows: row 0 EMPTY (no event, zero summary, answer 0), the others random events."""
    g = torch.Generator().manual_seed(1)
    ev = torch.randn(B, E, MM.F, generator=g)
    mask = torch.ones(B, E, dtype=torch.bool)
    summ = torch.randn(B, MM.N_SUM[version], generator=g)
    ev[0], mask[0], summ[0] = 0, False, 0
    card = torch.randn(B, E, d_c, generator=g)
    pad = torch.randn(1, d_c, generator=g)                       # the model's card_id(0)
    ans = torch.randn(B, d_c, generator=g)
    ans[0] = pad[0]
    return ev, mask, card, summ, ans, pad


def _enc(zero_empty, version="v1"):
    torch.manual_seed(0)
    return _live(MG.MemoryEncoder(8, 32, MM.F, MM.N_SUM[version], d=16, layers=1, heads=2, zero_empty=zero_empty)).eval()


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_empty_memory_adds_zero(version):
    ev, mask, card, summ, ans, pad = _inputs(version=version)
    with torch.no_grad():
        old = _enc(False, version)(ev, mask, card, summ, ans, pad)
        new = _enc(True, version)(ev, mask, card, summ, ans, pad)
    assert float(old[0].abs().max()) > 1e-3                      # the S3 failure mode: a live coupling offsets EVERY row
    assert float(new[0].abs().max()) < 1e-6                      # zero_empty: an empty memory adds nothing
    assert float(new[1:].abs().max()) > 1e-3                     # a real memory still moves the output
    # = the old form with its bias shifted by -out(empty) (skew/make_delta.py, the no-retrain conversion of a checkpoint)
    shifted = _enc(False, version)
    with torch.no_grad():
        shifted.out.bias -= old[0]
        assert torch.allclose(shifted(ev, mask, card, summ, ans, pad), new, atol=1e-5)


def test_flag_round_trip():
    net = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=12, feature_version=5).eval()
    net.add_memory(zero_empty=True)
    sd = net.state_dict()
    assert "mem.zero_empty" in sd
    plain = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=12, feature_version=5).eval()
    plain.load_state_dict(sd)                                    # by content (checkpoint without a pre-built encoder)
    assert hasattr(plain.mem, "zero_empty")
    pre = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=12, feature_version=5).eval()
    pre.add_memory()                                             # load_model(memory="v1") pre-builds the encoder
    pre.load_state_dict(sd)
    assert hasattr(pre.mem, "zero_empty")
    old = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=12, feature_version=5).eval()
    old.add_memory()
    assert "mem.zero_empty" not in old.state_dict()              # absent flag = the existing form, same keys


@pytest.mark.skipif(not (DATA.exists() and CKPT.exists()), reason="the fv5 pro set / CLXIII not on this host")
def test_clxiii_with_live_zero_empty_memory_is_clxiii_on_an_empty_memory():
    """Model level, real CLXIII + real pro rows: a LIVE zero_empty encoder with an empty memory = CLXIII (gate / card /
    cell / value); the same live encoder without zero_empty does not (the S3 v1 failure mode)."""
    from pipeline.train_gen import GenRows
    from pipeline.train_memory import npz_head
    torch.set_num_threads(2)
    arrs, _ = npz_head(DATA, 64)
    idx = np.arange(64)
    base = MG.load_model(CKPT, torch.device("cpu"))[0].eval()
    rows = GenRows(arrs, idx, torch.device("cpu"))
    b0 = rows.batch(idx)
    rows.memory = "empty"
    be = rows.batch(idx)
    out = {}
    for name, ze in (("old", False), ("new", True)):
        m = MG.load_model(CKPT, torch.device("cpu"), memory="v1")[0].eval()
        if ze:
            m.mem.register_buffer("zero_empty", torch.ones(()))
        _live(m.mem)
        with torch.no_grad():
            out[name] = m(be)
    with torch.no_grad():
        ref = base(b0)
    for k in ("gate", "card", "value"):
        scale = max(1.0, float(ref[k].abs().max()))
        assert float((out["new"][k] - ref[k]).abs().max()) < 1e-5 * scale, k
    assert float((out["old"]["gate"] - ref["gate"]).abs().max()) > 1e-3
