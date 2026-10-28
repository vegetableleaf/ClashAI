"""P2-OPP1 identity fingerprint: existing GenModel / train_gen behaviour with the opponent options OFF.

    icebow/.venv/Scripts/python.exe -m pipeline.tests.opp_identity --write   # once, at the pre-OPP1 HEAD (8010d5a)
    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_opp_model.py   # compares against the file

Fingerprint = sha256 of (a) the seeded init state dict of GenModel at fv 1 / 3 / 5 / 6 (+ fv5 memory v1), (b) its eval
forward on fixed toy rows, (c) train_gen.losses parts + every gradient after one backward, (d) CLXIII (8d328a43) loaded by
load_model and run on the fv5 toy batch (skipped when the file is absent).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("opp_identity_8010d5a.json")
CLXIII = REPO / "icebow/data/models/ICEBOW/succ48_o_s91_u0075_grafted.pt"


def _h(xs) -> str:
    h = hashlib.sha256()
    for x in xs:
        if isinstance(x, torch.Tensor):
            t = x.detach().cpu().contiguous()
            h.update(str((t.dtype, tuple(t.shape))).encode()); h.update(t.numpy().tobytes())
        else:
            h.update(str(x).encode())
    return h.hexdigest()


def _batch(fv: int, n_cards: int = 124):
    from pipeline.eval_gen import GenRows
    from pipeline.tests.test_model_gen import toy
    a = toy(n=6, seed=3)["gen"]
    if fv >= 3:
        rng = np.random.default_rng(5)
        a.update(unit_form=rng.integers(0, 3, len(a["tok"])).astype(np.int8),
                 opp_past=rng.uniform(0, 1, (6, 3, 5)).astype(np.float32))
        a["opp_past"][..., 0] = rng.integers(0, 9, (6, 3))
        a["opp_past"][..., 1] = rng.integers(0, 3, (6, 3))
    if fv >= 4:
        rng = np.random.default_rng(6)
        a.update(opp_cycle=rng.uniform(0, 1, (6, 8, 4)).astype(np.float32),
                 projectiles=rng.uniform(0, 1, (6, 64, 8)).astype(np.float32),
                 effects=rng.uniform(0, 1, (6, 32, 6)).astype(np.float32),
                 own_ability=rng.uniform(0, 1, (6, 8, 7)).astype(np.float32))
        for k, m in (("opp_cycle", 8), ("projectiles", 64), ("effects", 32), ("own_ability", 8)):
            a[k][..., 0] = np.where(rng.random((6, m)) < 0.3, rng.integers(1, 9, (6, m)), 0)
        a["opp_cycle"][..., 1] = rng.integers(0, 3, (6, 8))
    return GenRows(a, np.arange(6), "cpu").batch(np.arange(6))


def fingerprint() -> dict:
    from pipeline.model_gen import GenModel, load_model
    from pipeline.train_gen import losses
    torch.set_num_threads(1)
    out = {}
    for fv, mem in ((1, None), (3, None), (5, None), (6, None), (5, "v1")):
        name = f"fv{fv}" + (f"_mem{mem}" if mem else "")
        torch.manual_seed(0)
        m = GenModel(d=32, layers=1, heads=2, d_c=16, n_cards=124, feature_version=fv)
        if mem:
            m.add_memory(version=mem)
        sd = m.state_dict()
        out[name + ".init"] = _h([k for k in sd] + list(sd.values()))
        b = _batch(fv)
        if mem:
            from pipeline.match_memory import empty_rows
            b.update({k: torch.from_numpy(v) for k, v in empty_rows(6, mem).items()})
        m.eval()
        with torch.no_grad():
            o = m(b, card=b["card"], form=b["form"])
        out[name + ".fwd"] = _h([k for k in sorted(o)] + [o[k] for k in sorted(o)])
        m.train()
        torch.manual_seed(1)
        loss, parts = losses(m, b, mirror=True, grid="lattice")
        loss.backward()
        out[name + ".loss"] = _h([json.dumps(parts, sort_keys=True), loss]
                                 + [p.grad if p.grad is not None else "none" for p in m.parameters()])
    if CLXIII.exists():
        m, st = load_model(CLXIII, "cpu")
        m.eval()
        b = _batch(5)
        with torch.no_grad():
            o = m(b, card=b["card"], form=b["form"])
        out["clxiii.fwd"] = _h([k for k in sorted(o)] + [o[k] for k in sorted(o)])
    return out


if __name__ == "__main__":
    fp = fingerprint()
    if "--write" in sys.argv:
        FIXTURE.write_text(json.dumps(fp, indent=1) + "\n")
    print(json.dumps(fp, indent=1))
