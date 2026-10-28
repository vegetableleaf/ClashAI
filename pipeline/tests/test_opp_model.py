"""P2-OPP1 opponent model options (plan1026 Pillar 2): timing head, deck encoder, context tokens, ability head, joint
memory, and the legacy-identity guarantee.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_opp_model.py
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest
import torch

from pipeline.model_gen import SLOT_TICKS, DeckEncoder, GenModel, load_model, slot_nll
from pipeline.tests import opp_identity
from pipeline.tests.test_model_gen import toy


def test_legacy_identity_fingerprint():
    """Options OFF = the 8010d5a GenModel / train_gen bit for bit (init, forward, loss + every gradient, CLXIII)."""
    want = json.loads(opp_identity.FIXTURE.read_text())
    got = opp_identity.fingerprint()
    if "clxiii.fwd" not in got:
        want.pop("clxiii.fwd", None)
    assert got == want


# ------------------------------------------------------------------------------------------------ timing likelihood
def _direct_loglik(h, p_tick, event_slot, event_tick):
    """log P(first play at slot k, tick j) = sum_{s<k} log(1 - h_s) + log h_k + log p_k(j); no event = censored."""
    if event_slot is None:
        return sum(math.log(1 - x) for x in h)
    return (sum(math.log(1 - x) for x in h[:event_slot]) + math.log(h[event_slot])
            + math.log(p_tick[event_slot][event_tick]))


def test_slot_nll_is_the_exact_survival_likelihood():
    g = torch.Generator().manual_seed(0)
    K = 12
    logit = torch.randn(K, generator=g, dtype=torch.float64)
    tl = torch.randn(K, SLOT_TICKS, generator=g, dtype=torch.float64)
    h = torch.sigmoid(logit).tolist()
    pt = torch.softmax(tl, -1).tolist()
    for k, j in ((0, 0), (5, 7), (11, 9), (None, None)):
        ev = torch.zeros(K, dtype=torch.float64)
        tick = torch.zeros(K, dtype=torch.long)
        n = K
        if k is not None:
            ev[k], tick[k], n = 1, j, k + 1      # slots after the play belong to the next gap
        nll = slot_nll(logit[:n], tl[:n], ev[:n], tick[:n]).sum().item()
        assert nll == pytest.approx(-_direct_loglik(h[:n] if k is not None else h, pt, k, j), abs=1e-12)


def test_slot_nll_wait_subsampling_with_weight_is_unbiased():
    """No-play slots kept with probability 1/8 and weight 8: the expected weighted NLL = the full NLL (exactly)."""
    g = torch.Generator().manual_seed(1)
    K = 40
    logit = torch.randn(K, generator=g, dtype=torch.float64)
    tl = torch.randn(K, SLOT_TICKS, generator=g, dtype=torch.float64)
    ev = (torch.rand(K, generator=g) < 0.15).double()
    tick = torch.randint(0, SLOT_TICKS, (K,), generator=g)
    per = slot_nll(logit, tl, ev, tick)
    full = per.sum().item()
    keep_p = torch.where(ev > 0, 1.0, 1 / 8).double()
    expected = (per * keep_p * (1 / keep_p)).sum().item()      # E[sum_kept w * nll] = sum p * w * nll
    assert expected == pytest.approx(full, rel=1e-12)


def test_timing_head_recovers_a_known_hazard():
    """Toy: slots with a feature x, P(play) = sigmoid(1.5 x - 2), tick ~ fixed pmf; fit by slot_nll -> the truth."""
    rng = np.random.default_rng(0)
    n = 40000
    x = torch.tensor(rng.normal(size=n), dtype=torch.float32)
    h = torch.sigmoid(1.5 * x - 2)
    ev = torch.tensor(rng.random(n) < h.numpy(), dtype=torch.float32)
    pmf = np.array([4, 1, 1, 1, 1, 1, 1, 1, 1, 0.5]); pmf /= pmf.sum()
    tick = torch.tensor(rng.choice(SLOT_TICKS, size=n, p=pmf))
    torch.manual_seed(0)
    head = torch.nn.Linear(1, 1 + SLOT_TICKS)
    opt = torch.optim.Adam(head.parameters(), lr=0.05)
    for _ in range(400):
        o = head(x[:, None])
        loss = slot_nll(o[:, 0], o[:, 1:], ev, tick).mean()
        opt.zero_grad(); loss.backward(); opt.step()
    assert float(head.weight[0, 0]) == pytest.approx(1.5, abs=0.1)
    assert float(head.bias[0]) == pytest.approx(-2.0, abs=0.1)
    fit = torch.softmax(head.bias[1:].detach(), -1).numpy()       # x-slopes of the tick logits ~ 0
    assert np.abs(fit - pmf).max() < 0.02


# ------------------------------------------------------------------------------------------------ deck encoder
def _deck(B=5, seed=0):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(B, 8, 16, generator=g), torch.ones(B, 8, dtype=torch.bool)


def test_deck_encoder_is_invariant_to_deck_order_and_finite_when_empty():
    torch.manual_seed(0)
    enc = DeckEncoder(16, n_decks=10).eval()
    x, m = _deck()
    m[0, 5:] = False
    ids = torch.tensor([3, 0, 7, 10, 1])
    a = enc(x, m, ids)
    perm = torch.tensor([6, 2, 0, 7, 4, 1, 3, 5])
    b = enc(x[:, perm], m[:, perm], ids)
    assert torch.allclose(a, b, atol=1e-5)
    empty = enc(x, torch.zeros_like(m), ids)
    assert torch.isfinite(empty).all()
    # id 0 = unknown: the same card set with an unknown id differs from a known id only by the id embedding
    k = enc(x, m, ids) - enc(x, m, torch.zeros_like(ids))
    assert torch.allclose(k, enc.deck_id(ids) - enc.deck_id(torch.zeros_like(ids)), atol=1e-6)


def test_deck_id_dropout_only_in_training():
    torch.manual_seed(0)
    enc = DeckEncoder(16, n_decks=10)
    x, m = _deck(B=4000)
    ids = torch.full((4000,), 4)
    enc.eval()
    assert torch.equal(enc(x, m, ids), enc(x, m, ids))
    enc.train()
    base = enc(x, m, torch.zeros_like(ids))
    dropped = torch.isclose(enc(x, m, ids), base, atol=1e-6).all(-1).float().mean().item()
    assert 0.17 < dropped < 0.23                               # 20% id dropout


# ------------------------------------------------------------------------------------------------ GenModel options
def _opp_rows(n=64, seed=0, fv=5):
    a = toy(n=n, seed=seed)["gen"]
    rng = np.random.default_rng(seed + 10)
    if fv >= 3:
        a.update(unit_form=np.zeros(len(a["tok"]), np.int8), opp_past=np.zeros((n, 3, 5), np.float32))
    if fv >= 4:
        a.update(opp_cycle=np.zeros((n, 8, 4), np.float32), projectiles=np.zeros((n, 64, 8), np.float32),
                 effects=np.zeros((n, 32, 6), np.float32), own_ability=np.zeros((n, 8, 7), np.float32))
    play = a["y_gate"] == 1
    a.update(row_w=np.where(play, 1.0, 8.0).astype(np.float32), card_ok=(rng.random(n) < 0.8).astype(np.int8),
             slot_ok=(rng.random(n) < 0.7).astype(np.int8), slot_ev=(rng.random(n) < 0.2).astype(np.int8),
             slot_tick=rng.integers(0, 10, n).astype(np.int8), ab_ok=(rng.random(n) < 0.5).astype(np.int8),
             ab_ev=(rng.random(n) < 0.1).astype(np.int8), ab_tick=rng.integers(0, 10, n).astype(np.int8),
             deck_gid=rng.integers(0, 6, n).astype(np.int32), ctx_band=rng.integers(0, 4, n).astype(np.int8),
             ctx_mode=rng.integers(0, 3, n).astype(np.int8), ctx_era=np.ones(n, np.int8))
    return a


OPTS = dict(timing=True, ability=True, deck_enc=True, n_decks=5, ctx_tokens={"band": 3, "mode": 2, "era": 2})


def test_opp_model_heads_losses_and_checkpoint_roundtrip(tmp_path):
    from pipeline.train_gen import GenRows, losses
    torch.manual_seed(0)
    m = GenModel(d=32, layers=1, d_c=16, n_cards=124, feature_version=5, **OPTS)   # heads 4: load_model builds 4
    assert not hasattr(m, "gate_head")
    a = _opp_rows()
    b = GenRows(a, np.arange(64), "cpu").batch(np.arange(64))
    m.eval()
    with torch.no_grad():
        o = m(b, card=b["card"], form=b["form"])
    assert "gate" not in o and o["hazard"].shape == (64,) and o["tick"].shape == (64, SLOT_TICKS)
    assert o["ab_hazard"].shape == (64,) and o["ab_tick"].shape == (64, SLOT_TICKS)
    m.train()
    loss, parts = losses(m, b, mirror=True, grid="lattice")
    assert set(parts) == {"cell", "card", "wait", "timing", "ability", "value"} and math.isfinite(float(loss))
    loss.backward()
    for name in ("timing_head.weight", "ability_head.weight", "deck_enc.deck_id.weight", "ctx_band.weight",
                 "deck_enc.encoder.layers.0.linear1.weight"):
        assert dict(m.named_parameters())[name].grad.abs().sum() > 0, name
    p = tmp_path / "opp.pt"
    torch.save(dict(gen=True, args=dict(d=32, layers=1, feature_version=5), d_c=16, card_vocab=list(range(124)),
                    model=m.state_dict(), opp=m.opp), p)
    m2, _ = load_model(p, "cpu")
    m.eval(); m2.eval()
    with torch.no_grad():
        o1, o2 = m(b, card=b["card"], form=b["form"]), m2(b, card=b["card"], form=b["form"])
    assert set(o1) == set(o2) and all(torch.equal(o1[k], o2[k]) for k in o1)


def test_card_label_masked_on_hand_inferred_rows():
    from pipeline.train_gen import GenRows, losses
    torch.manual_seed(0)
    m = GenModel(d=32, layers=1, heads=2, d_c=16, n_cards=124, feature_version=5, timing=True)
    a = _opp_rows()
    a["card_ok"][:] = 0
    b = GenRows(a, np.arange(64), "cpu").batch(np.arange(64))
    _, parts = losses(m, b, mirror=False, grid="lattice")
    assert parts["card"] == 0.0 and parts["cell"] > 0


def test_joint_memory_is_not_a_zero_adapter():
    torch.manual_seed(0)
    m = GenModel(d=32, layers=1, heads=2, d_c=16, n_cards=124, feature_version=5, timing=True)
    m.add_memory(version="v1", zero_empty=True, zero_init=False)
    assert m.mem.out.weight.abs().sum() > 0 and hasattr(m.mem, "zero_empty")
    m0 = GenModel(d=32, layers=1, heads=2, d_c=16, n_cards=124, feature_version=5)
    m0.add_memory(version="v1")
    assert m0.mem.out.weight.abs().sum() == 0                 # the legacy default is unchanged


# ------------------------------------------------------------------------------------------------ trainer
def _write_npz(path, a, row_builder):
    meta = {"kind": "generalist", "feature_version": 5, "grid": "lattice", "card_vocab": [f"c{i}" for i in range(124)],
            "row_builder": row_builder}
    a = dict(a, split=np.where(np.arange(len(a["y_gate"])) % 4 == 0, 1, 0).astype(np.int8))
    np.savez(path, meta=json.dumps(meta), **a)


def test_main_opp_trains_writes_curve_and_refuses_stride_rows(tmp_path):
    from pipeline import train_gen as TG
    a = _opp_rows(n=96)
    good, bad = tmp_path / "slot.npz", tmp_path / "stride.npz"
    _write_npz(good, a, {"wait_stride": 10, "play_window": 0})
    _write_npz(bad, a, {"wait_stride": 40, "play_window": 20})
    common = ["--seed", "0", "--d", "32", "--layers", "1", "--d-c", "16", "--bs", "16", "--grid", "lattice",
              "--opp-timing", "--opp-ability", "--opp-deck-enc", "--opp-ctx", "band=3,mode=2,era=2",
              "--max-steps", "5", "--eval-every", "2", "--eval-rows", "20"]
    with pytest.raises(ValueError, match="SLOT rows"):
        TG.main(["--data", str(bad), "--out-dir", str(tmp_path / "x")] + common)
    assert TG.main(["--data", str(good), "--out-dir", str(tmp_path / "r"), "--tag", "t"] + common) == 0
    curve = [json.loads(x) for x in (tmp_path / "r" / "curve_t_s0.jsonl").read_text().splitlines()]
    assert [c["step"] for c in curve] == [0, 2, 4, 5] and all(math.isfinite(c["total"]) for c in curve)
    import zipfile
    zipfile.ZipFile(good).extractall(tmp_path / "dir")                 # extracted-npz directory: same curve
    assert TG.main(["--data", str(tmp_path / "dir"), "--out-dir", str(tmp_path / "rd"), "--tag", "t"] + common) == 0
    curve_d = [json.loads(x) for x in (tmp_path / "rd" / "curve_t_s0.jsonl").read_text().splitlines()]
    # CPU training is not bit-reproducible run to run here (two npz runs differ ~1e-7 relative): approx
    assert [c["total"] for c in curve_d] == pytest.approx([c["total"] for c in curve], rel=1e-5)
    m, st = load_model(tmp_path / "r" / "opp_t_s0.pt", "cpu")
    assert st["opp"]["timing"] and st["opp"]["n_decks"] == 5 and m.opp == st["opp"]
    # fine-tune from it (same options) runs; another option set is refused
    assert TG.main(["--data", str(good), "--out-dir", str(tmp_path / "f"), "--init", str(tmp_path / "r" / "opp_t_s0.pt"),
                    "--lr", "1e-5"] + common) == 0
    with pytest.raises(ValueError, match="differ"):
        TG.main(["--data", str(good), "--out-dir", str(tmp_path / "g"), "--init", str(tmp_path / "r" / "opp_t_s0.pt")]
                + [c for c in common if c != "--opp-ability"])
