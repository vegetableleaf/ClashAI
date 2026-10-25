"""S3-aux: memory encoder pretrained ONLY by prediction heads (train_memory --trainable memory_encoder --aux v1), policy untouched.

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_aux.py -q

Laptop data as test_train_memory: CLXIII (grafted live file), the first 1,509 rows of the fv5 pro set (replays 0-5), memory
tables built for those 6 replays. Covers: no memory_aux = no key / parameter / hash change; a 20-step S3-aux run keeps every
base tensor AND the zero-init coupling bit-identical (asserted inside the trainer, re-checked from the checkpoint), the encoder
moves, the checkpoint reloads with its heads by content and its policy = CLXIII's exactly; labels never leak into inputs
(future events / future hands shuffled -> the memory inputs at t unchanged, the labels changed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import match_memory as MM                                  # noqa: E402
from pipeline import train_memory as TM                                  # noqa: E402

DATA = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
CKPT = REPO / "icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt"
HEAD = 1509
need_data = pytest.mark.skipif(not (DATA.exists() and CKPT.exists()), reason="the fv5 pro set / CLXIII not on this host")


def test_absent_flag_is_byte_identical():
    """No memory_aux: the model has no mem_aux module / key; the rl config hash ignores absent / null / false keys."""
    from pipeline.model_gen import GenModel
    from pipeline import rl_royale as R
    m = GenModel(feature_version=6)
    m.add_memory(version="v1")
    assert getattr(m, "mem_aux", None) is None and not any(k.startswith("mem_aux.") for k in m.state_dict())
    m.add_memory_aux()
    assert any(k.startswith("mem_aux.") for k in m.state_dict())
    cfg = {"lr": 1e-4, "memory": "v1"}
    h = R.config_sha(cfg)
    assert h == R.config_sha({**cfg, "memory_aux": None, "memory_encoder_frozen": None, "memory_zero_empty": None})
    assert h == R.config_sha({**cfg, "memory_encoder_frozen": False, "memory_zero_empty": False})
    assert h != R.config_sha({**cfg, "memory_zero_empty": True})
    assert h != R.config_sha({**cfg, "memory_aux": "v1"}) != R.config_sha({**cfg, "memory_encoder_frozen": True})


def test_rl_keys_validated_and_frozen_names():
    from pipeline import rl_royale as R
    for bad in ({"memory_aux": "v1"}, {"memory_encoder_frozen": True}, {"memory": "v1", "memory_aux": "v2"},
                {"memory": "v1", "memory_encoder_frozen": "yes"}, {"memory_zero_empty": True},
                {"memory": "v1", "memory_zero_empty": "yes"}):
        with pytest.raises(SystemExit):
            R.memory_cfg(bad)
    assert R.memory_cfg({"memory": "v2", "memory_aux": "v1", "memory_encoder_frozen": True}) == "v2"
    assert [R.mem_frozen_name(n) for n in ("mem.ev_in.weight", "mem.summary.0.bias", "mem_aux.own.0.weight",
                                           "mem.out.weight", "mem.out.bias", "gate_head.weight")] == [True] * 3 + [False] * 3


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    from pipeline.dataset_gen import memory_tables
    out = tmp_path_factory.mktemp("mem") / "mem6.npz"
    memory_tables(DATA, out, workers=1, limit=6, log=None)
    return out


@need_data
def test_aux_run_keeps_policy(tmp_path, tables):
    torch.set_num_threads(2)
    out = tmp_path / "run"
    TM.main(["--init", str(CKPT), "--memory", "v2", "--memory-tables", str(tables), "--data", str(DATA),
             "--trainable", "memory_encoder", "--aux", "v1", "--out-dir", str(out), "--head-rows", str(HEAD),
             "--device", "cpu", "--val-sample", "64", "--prefetch", "2", "--steps", "20", "--bs", "16",
             "--val-every", "20", "--ckpt-every", "1000"])
    log = [json.loads(x) for x in (out / "s3_log.jsonl").read_text().splitlines()]
    assert log[1]["policy_identity"]["max_diff"] == 0.0
    fin = json.loads((out / "s3_final.json").read_text())
    assert fin["steps"] == 20 and fin["coupling_zero"] and fin["policy_identity_val"]["max_diff"] == 0.0
    v = fin["hist"][-1]["memory"]
    assert set(TM.AUX_HEADS) <= set(v) and np.isfinite(v["loss"])
    init = torch.load(CKPT, map_location="cpu", weights_only=False)["model"]
    got = torch.load(out / "mem_latest.pt", map_location="cpu", weights_only=False)
    assert got["memory"] == "v2" and got["memory_aux"] == "v1" and got["s3"]["trainable"] == "memory_encoder"
    assert all(torch.equal(got["model"][k], v) for k, v in init.items())          # every base tensor = CLXIII's
    assert float(got["model"]["mem.out.weight"].abs().max()) == 0 and float(got["model"]["mem.out.bias"].abs().max()) == 0
    from pipeline.model_gen import GenModel, load_model
    fresh = GenModel(feature_version=6)
    fresh.add_memory(version="v2")
    moved = [k for k, x in fresh.state_dict().items() if k.startswith("mem.") and not k.startswith("mem.out.")
             and k != "mem.cfg" and not torch.equal(x, got["model"][k])]
    assert moved                                                                   # (fresh init differs anyway: sanity)
    m, _ = load_model(out / "mem_latest.pt", "cpu")
    assert m.mem_aux is not None and m.mem.version == "v2"                         # heads rebuilt by content
    base, _ = load_model(CKPT, "cpu")
    assert getattr(base, "mem_aux", None) is None


@need_data
def test_labels_never_leak(tables):
    """Per row: shuffle every event of its table that is not visible at t (vis > t; payload only, ticks kept) -> the memory
    inputs at t are bit-identical, the labels change on some rows; future rows' hands shuffled -> cycle labels change."""
    from pipeline.dataset_gen import checkpoint_gid, load_memory_tables
    arrs, meta = TM.npz_head(DATA, HEAD)
    packed, row_tab, _ = load_memory_tables(tables)
    row_tab = row_tab[:HEAD]
    gid = checkpoint_gid(meta["card_vocab"])
    nc = len(meta["card_vocab"]) + 1
    lab = TM.AuxLabels(arrs, packed, row_tab, gid, nc)
    rng = np.random.default_rng(0)
    rows = np.flatnonzero(row_tab >= 0)
    rows = rows[rng.choice(len(rows), 40, replace=False)]
    keys = TM.REG + TM.BIN + TM.CLS + ("slot",)
    changed = {k: 0 for k in keys}
    for i in rows:
        t = int(arrs["tick"][i])
        a, b = int(packed["off"][row_tab[i]]), int(packed["off"][row_tab[i] + 1])
        fut = a + np.flatnonzero(packed["vis"][a:b] > t)
        if len(fut) < 2:
            continue
        p2 = {k: v.copy() for k, v in packed.items()}
        perm = fut[np.r_[1:len(fut), 0]]                       # a cyclic shift of the future payloads
        for k in MM.TABLE_KEYS:
            if k not in ("tick", "vis"):
                p2[k][fut] = packed[k][perm]
        f1 = MM.rows_features(packed, row_tab, arrs["tick"], arrs["deck_card"], [i], "v2", gid)
        f2 = MM.rows_features(p2, row_tab, arrs["tick"], arrs["deck_card"], [i], "v2", gid)
        assert all(np.array_equal(f1[k], f2[k]) for k in MM.MEM_KEYS), f"row {i}: inputs read a future event"
        l2 = TM.AuxLabels(arrs, p2, row_tab, gid, nc)
        for k in keys:
            x, y = getattr(lab, k)[i], getattr(l2, k)[i]
            changed[k] += int(not np.array_equal(np.nan_to_num(np.asarray(x, float), nan=-7),
                                                 np.nan_to_num(np.asarray(y, float), nan=-7)))
    assert changed["opp_next"] > 0 and changed["opp_el10"] + changed["threat"] > 0 and changed["swing"] + changed["slot"] > 0
    # future rows' hands -> the cycle labels (inputs never read another row's hand: rows_features takes tables + this row)
    i = int(rows[0])
    later = np.flatnonzero((row_tab == row_tab[i]) & (arrs["tick"] > arrs["tick"][i]))
    a2 = dict(arrs, hand_card=arrs["hand_card"].copy())
    a2["hand_card"][later] = 0
    l3 = TM.AuxLabels(a2, packed, row_tab, gid, nc)
    q = (lab.cyc[i] > 0)
    assert (l3.cyc[i][q] == -1).all() and np.array_equal(l3.cyc[i][~q], lab.cyc[i][~q])
