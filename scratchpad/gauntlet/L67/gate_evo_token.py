"""L67i: does an UNTRAINED EVO class token collapse the gate? The last live-only input, and it is in my deck.

Measured: all 42 `_evo` detector classes have ZERO tokens in the 1,434,428 training unit rows, while their
base forms are everywhere (knight 155,582 / tesla 111,590). The corpus is built from pro replays through the
engine, which names bodies by their base card; the live DETECTOR emits the evo class. So the icebow deck's own
Evo Knight and Evo Tesla arrive as class ids whose embeddings were never trained -- and they are on the board
intermittently, which is the shape of the observed collapse (p=0.00 stretches interleaved with p=0.95 plays).

Test: take real VAL rows and rewrite ONE unit's class id to an evo id, against a control that rewrites it to a
DIFFERENT TRAINED class. If the evo id alone crushes p while the trained swap does not, the live freeze is an
untrained-embedding problem, fixable at the contract boundary by folding `_evo` to its base class.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", type=Path, required=True)
ap.add_argument("--data", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--rows", type=int, default=6000)
a = ap.parse_args()

import torch
from pipeline import vocab
from pipeline.dataset import load as load_ds
from pipeline.model_v3 import S1Model, hand_mask_from_sc
from pipeline.train_s1 import Rows

arrs, _ = load_ds(a.data)
idx = np.flatnonzero(arrs["split"] == 1)
idx = np.sort(np.random.default_rng(0).choice(idx, min(a.rows, len(idx)), replace=False))
dev = torch.device("cpu")
st = torch.load(a.ckpt, map_location=dev)
args = dict(st.get("args", {}) or {})
model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
model.load_state_dict(st["model"]); model.eval()

def score(mut_tok):
    mut = dict(arrs); mut["tok"] = mut_tok
    rows = Rows(mut, idx, dev); ps = []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            b = rows.batch(idx[s0:s0 + 512])
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            ps.append(torch.sigmoid(model.heads(enc, hand_mask_from_sc(b["sc"]))["gate"]).cpu().numpy())
    return np.concatenate(ps).astype(float)

off = arrs["off"]
first = np.array([off[i] for i in idx])          # first unit row of each selected state
has = np.array([off[i + 1] > off[i] for i in idx])
print(f"rows with at least one unit: {int(has.sum())} / {len(idx)}", flush=True)

variants = {"clean": None,
            "1 unit -> knight_evo (UNTRAINED)": vocab.unit_id("knight_evo"),
            "1 unit -> tesla_evo (UNTRAINED)": vocab.unit_id("tesla_evo"),
            "1 unit -> knight (trained control)": vocab.unit_id("knight"),
            "1 unit -> mega_knight (trained control)": vocab.unit_id("mega_knight")}
out = []
for name, cid in variants.items():
    tok = arrs["tok"].copy()
    if cid is not None:
        tok[first[has], 0] = float(cid)
    p = score(tok)
    rec = {"variant": name, "class_id": (None if cid is None else int(cid)),
           "mean_p": round(float(p.mean()), 4), "median_p": round(float(np.median(p)), 4),
           "frac_under_0.005": round(float((p < 0.005).mean()), 4)}
    out.append(rec); print(json.dumps(rec), flush=True)
a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
