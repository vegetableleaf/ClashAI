"""S1b fast paths equal the originals: batched_rollout.LazyRefine (cell-only features computed for the requested rows)
vs GenPolicy on the real CLXIII checkpoint, and fast_obs.extract_units / sim_cue_rows vs sim_unit_state.extract /
e1_eval.sim_cue_rows on a real RoyaleSim battle. Each skips when its checkpoint / runtime is absent."""
from pathlib import Path

import numpy as np
import pytest
import torch

REPO = Path(__file__).resolve().parents[2]
CK = REPO / "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"
BATCH = REPO / "scratchpad/gauntlet/L74/speed/results/live_batch1.pt"


def _rows(n=24):
    """n gen rows from one real live row: unit xy jittered per row, so every row's cell features differ."""
    b = {k: v[0].numpy() for k, v in torch.load(BATCH).items()}
    r = np.random.default_rng(0)
    out = []
    for i in range(n):
        x = {k: v.copy() for k, v in b.items()}
        x["tok"][:, 4:6] = np.clip(x["tok"][:, 4:6] + r.normal(0, 0.05, (len(x["tok"]), 2)), 0, 1).astype(np.float32)
        x["sc"] = (x["sc"] + r.normal(0, 0.01, x["sc"].shape)).astype(np.float32)
        x["hand_slot"] = np.arange(4, dtype=np.int64)
        x["slot_card"] = np.concatenate([x["hand_card"], x["deck_card"][:4], [0]]).astype(np.int64)
        x["slot_form"] = np.concatenate([x["hand_form"], x["deck_form"][:4], [3]]).astype(np.int64)
        out.append(x)
    return out


@pytest.mark.skipif(not (CK.is_file() and BATCH.is_file()), reason="CLXIII checkpoint / live batch fixture absent")
def test_lazy_refine_equals_genpolicy():
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    pol, _ = E.load_policy(CK, "cpu")
    assert pol.model.cell_refine is not None and pol.model.tower_refine.use_cell
    rows = _rows()
    enc, heads, p, hand = pol.forward_batch(rows, "cpu")
    lz = BR.LazyRefine(pol)
    enc2, heads2, p2, hand2 = lz.forward_batch(rows, "cpu")
    assert "cell_feat" not in enc2 and "tower_cell_feat" not in enc2
    assert pol.model.cell_refine is not None and pol.model.tower_refine.use_cell     # restored after the forward
    for k in ("gate", "card"):
        assert torch.allclose(heads[k], heads2[k], atol=1e-6, rtol=0)
    assert np.array_equal(hand, hand2) and np.allclose(p, p2, atol=1e-7)
    idx = torch.tensor([1, 5, 6, 17])
    slot = torch.tensor([0, 2, 3, 1])
    with torch.no_grad():
        want = pol.cell_logits({k: v[idx] for k, v in enc.items()}, slot)
        got = lz.cell_logits({k: v[idx] for k, v in enc2.items()}, slot)
        full = pol.cell_logits(enc, torch.zeros(len(rows), dtype=torch.long))
    assert torch.allclose(want, got, atol=1e-5, rtol=0), float((want - got).abs().max())
    assert want.argmax(-1).tolist() == got.argmax(-1).tolist()
    assert full.shape[0] == len(rows)


def _battle():
    pytest.importorskip("royalesim")
    from pipeline.royale_runtime import activate
    try:
        activate()
    except Exception as exc:                                  # noqa: BLE001 -- wrong / absent runtime: skip
        pytest.skip(f"runtime: {exc}")
    from pipeline.e1_eval import ICEBOW_ENGINE_DECK
    from pipeline.royale_env import RoyaleSelfPlayEnv
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=True)
    env.reset(list(ICEBOW_ENGINE_DECK), list(ICEBOW_ENGINE_DECK), 5)
    return env


def test_extract_units_equals_extract():
    from pipeline import fast_obs as F
    from pipeline import sim_unit_state as SU
    env = _battle()
    plays = {220: (0, 2, 6000, 20000), 260: (1, 1, 12000, 22000), 400: (0, 7, 9000, 18000), 520: (1, 2, 8000, 20000)}
    m1, m2, n = {}, {}, 0
    for t in range(200, 900, 20):
        env._advance_to(t)
        if t in plays:
            s, i, x, y = plays[t]
            env.eng.act(side=s, deck_index=i, x=x, y=y)
        a = SU.extract(env.core._battle, m1, hit_window_ms=100)["units"]
        b = F.extract_units(env.core._battle, m2, hit_window_ms=100)
        assert a == b and m1 == m2, t
        n += len(a)
    assert n > 6 * 35                                         # bodies beyond the six towers were compared


def test_memo_update_equals_extract_memo():
    from pipeline import fast_obs as F
    from pipeline import sim_unit_state as SU
    import json
    import sys
    env = _battle()
    env._advance_to(300)
    env.eng.act(side=0, deck_index=0, x=9000, y=16000)      # a spell / body with buffs on the board
    m1, m2 = {}, {}
    for t in range(320, 700, 20):
        env._advance_to(t)
        SU.extract(env.core._battle, m1, hit_window_ms=100)
        F._memo_update(env.core._battle, m2, json.loads(env.core._battle.state_json()), SU._tbl(sys.modules["royalesim"]))
        assert m1 == m2, t


@pytest.mark.skipif(not (CK.is_file() and BATCH.is_file()), reason="CLXIII checkpoint / live batch fixture absent")
def test_merged_forward_equals_separate():
    """batched_rollout.Merged: two same-architecture policies (random small GenModels, CLXIII's vocab) in ONE vmapped
    call == each policy's own forward_batch; uneven row counts (padding dropped); cell logits from the merged enc."""
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.model_gen import GenModel
    st = torch.load(CK, map_location="cpu")
    pols = []
    for seed in (0, 1):
        torch.manual_seed(seed)
        m = GenModel(d=32, layers=1, heads=4, d_c=int(st["d_c"]), n_cards=len(st["card_vocab"]),
                     feature_version=int(st["args"]["feature_version"])).eval()
        pols.append(E.GenPolicy(m, st["card_vocab"]))
    assert BR.merge_key(pols[0]) == BR.merge_key(pols[1]) is not None
    rows = _rows(12)
    parts = [rows[:5], rows[5:]]
    got = BR.Merged(pols, "cpu").forward([1, 0], parts[::-1], "cpu")      # member order != list order on purpose
    for pol, rr, (enc, heads, p, hand) in zip(pols[::-1], parts[::-1], got):
        enc0, heads0, p0, hand0 = pol.forward_batch(rr, "cpu")
        nz = torch.nan_to_num
        assert torch.allclose(nz(heads["card"]), nz(heads0["card"]), atol=1e-5)
        assert torch.allclose(heads["gate"], heads0["gate"], atol=1e-5) and np.array_equal(hand, hand0)
        slot = torch.zeros(len(rr), dtype=torch.long)
        with torch.no_grad():
            assert torch.allclose(pol.cell_logits(enc, slot), pol.cell_logits(enc0, slot), atol=1e-4)
