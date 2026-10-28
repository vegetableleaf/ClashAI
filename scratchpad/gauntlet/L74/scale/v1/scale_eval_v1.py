"""Curve v1 / P4-10M held-out eval: scale_eval.py's per-head NLL + top-1 (same definitions, same code path) on the mix_v1
row groups, for ANY generalist checkpoint (load_model: fv5 / fv6, memory, its own card_vocab).
usage: scale_eval_v1.py CODE_DIR CKPT DATA OUT_JSON [--mode all|nolat|latonly] [--memory-tables MIX_memory.npz]
                        [--groups g1,g2,...]
Groups (mix_v1 rows; src 0 = v32, 1 = HF):
  heldout_v32   split 3 (v32's val) minus curve v0's 30k selection sample = curve v0's heldout_clean, row for row
  heldout_hf    a fixed seed-1 300k sample of HF held-out (split 1) minus the trainer's 30k selection sample
  v3val         v32's v3val rows (S1's instrument)
  train_v32     curve v0's exact 100k train subset (seed 123 over v32 train rows)
  train_hf      a seed-123 100k sample of HF train rows
  ice_v32 / ice_hf   held-out rows (as above, all of them) whose deciding side plays the icebow deck (the 8 cards of
                     pipeline/decks/icebow.yaml, any forms)
A checkpoint whose card_vocab differs from the data's (CLXIII) gets every card id remapped by name (dataset_gen
checkpoint_gid); a card it lacks -> 0 (pad), counted per group in ``unmapped_rows``.
Memory models get their memory inputs from --memory-tables (rows without a table: an empty memory).
"""
import argparse
import hashlib
import json
import sys
import time
import warnings

import numpy as np
import torch
import torch.nn.functional as Fn

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
ap.add_argument("code"); ap.add_argument("ckpt"); ap.add_argument("data"); ap.add_argument("out_json")
ap.add_argument("--mode", default="all", choices=("all", "nolat", "latonly"))
ap.add_argument("--memory-tables", default=None)
ap.add_argument("--groups", default="heldout_v32,heldout_hf,v3val,train_v32,train_hf,ice_v32,ice_hf")
a = ap.parse_args()
sys.path.insert(0, a.code)
from pipeline.dataset import load as load_ds                     # noqa: E402
from pipeline.dataset_gen import checkpoint_gid, load_memory_tables   # noqa: E402
from pipeline.eval_gen import GenRows, val_rows                  # noqa: E402
from pipeline.model_gen import load_model, mem_version           # noqa: E402
from pipeline.model_v3 import cell_label, cell_index, tile_of_cell, GRID_X, GRID_Y   # noqa: E402

ICEBOW = ("tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons")
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
t0 = time.time()
arrs, meta = load_ds(a.data)
vocab = meta["card_vocab"]
model, st = load_model(a.ckpt, dev)
model.eval()
n_params = sum(p.numel() for p in model.parameters())
grid = st["args"].get("grid", "lattice")
mver = mem_version(model)

# ---- vocab remap (data ids -> model ids) ----
lut = None
if st["card_vocab"] != vocab:
    g = checkpoint_gid(st["card_vocab"])
    lut_np = np.array([g.get(k, 0) if i else 0 for i, k in enumerate(vocab)], np.int64)
    lut = torch.as_tensor(lut_np, device=dev)
    missing_ids = np.array([i for i, k in enumerate(vocab) if i and k not in g])
CARD_LONG = ("hand_card", "next_card", "deck_card", "card")
CARD_OBJ = ("past", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability")


def remap(b):
    for k in CARD_LONG:
        b[k] = lut[b[k].long()]
    for k in CARD_OBJ:
        if k in b:
            v = b[k].clone()
            c = v[..., 0]
            v[..., 0] = torch.where(c > 0, lut[c.long().clamp(0, len(lut) - 1)].to(v.dtype), c)
            b[k] = v
    for k in ("mem_card", "mem_answer"):
        if k in b:
            b[k] = lut[b[k].long()]
    return b


# ---- row groups ----
split, src = arrs["split"], arrs["src"]
dk = arrs["deck_card"]
ice_ids = sorted(vocab.index(k) for k in ICEBOW)
is_ice = (np.sort(dk, 1) == np.array(ice_ids)[None, :]).all(1)
v32_val = np.where(split == 3)[0]
sel0 = np.sort(np.random.default_rng(0).choice(v32_val, size=30000, replace=False))      # curve v0's selection sample
if st.get("step") is not None:          # train_gen.main_opp: best-by-held-out on a seed-0 sample of eval_rows split-1 rows
    va1 = np.where(split == 1)[0]
    sel1 = np.sort(np.random.default_rng(0).choice(va1, size=min(int(st["args"]["eval_rows"]), len(va1)), replace=False))
else:                                   # train_gen.main: the epoch pick's fixed val_sample
    sel1 = val_rows(arrs, st["args"].get("val_sample") or 30000) if (split == 1).any() else np.zeros(0, np.int64)
hf_val = np.setdiff1d(np.where(split == 1)[0], sel1)
G = {}
want = a.groups.split(",")
if "heldout_v32" in want or "ice_v32" in want:
    G["heldout_v32"] = np.setdiff1d(v32_val, sel0)
    G["ice_v32"] = G["heldout_v32"][is_ice[G["heldout_v32"]]]
if "heldout_hf" in want or "ice_hf" in want:
    G["heldout_hf"] = np.sort(np.random.default_rng(1).choice(hf_val, size=min(300000, len(hf_val)), replace=False))
    G["ice_hf"] = hf_val[is_ice[hf_val]]
if "v3val" in want:
    G["v3val"] = np.where(arrs["v3val"] == 1)[0]
if "train_v32" in want:
    G["train_v32"] = np.sort(np.random.default_rng(123).choice(np.where((split == 0) & (src == 0))[0], 100000, replace=False))
if "train_hf" in want and ((split == 0) & (src == 1)).any():
    G["train_hf"] = np.sort(np.random.default_rng(123).choice(np.where((split == 0) & (src == 1))[0], 100000, replace=False))
G = {k: v for k, v in G.items() if k in want}

rows = GenRows(arrs, np.arange(0), dev)
if mver is not None:
    if a.memory_tables is None:
        raise SystemExit(f"{a.ckpt} has memory {mver}: pass --memory-tables")
    packed, row_tab, mmeta = load_memory_tables(a.memory_tables)
    if mmeta.get("card_vocab") not in (None, vocab):
        raise SystemExit("memory tables were built with another card vocab")
    rows.memory, rows.memory_version, rows.memory_gid = (packed, row_tab, arrs["tick"]), mver, checkpoint_gid(vocab)


def batch(ids):
    b = rows.batch(ids)
    return remap(b) if lut is not None else b


@torch.no_grad()
def nll(idx, bs=1024):
    s = dict(cell=0., card=0., wait=0., gate=0., value=0.); c = dict(play=0, wait=0, n=0)
    t1 = dict(cell_half=0, cell_tile=0, card=0, wait=0, gate_tp=0, gate_tn=0, value=0)
    nneg = npos = 0
    unm = 0
    for i in range(0, len(idx), bs):
        ids = idx[i:i + bs]; b = batch(ids)
        if lut is not None and len(missing_ids):
            raw = np.concatenate([arrs["hand_card"][ids], arrs["deck_card"][ids], arrs["opp_cycle"][ids][..., 0].astype(np.int64)], 1)
            unm += int(np.isin(raw, missing_ids).any(1).sum())
        o = model(b, card=b["card"], form=b["form"])
        play = b["gate"] > 0.5; wt = ~play
        if play.any():
            lg = o["cell"][play].float(); xy = b["xy"][play]; th = cell_label(xy, grid)
            s["cell"] += float(Fn.cross_entropy(lg, th, reduction="sum"))
            pred = lg.argmax(-1); t1["cell_half"] += int((pred == th).sum())
            p = lg.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            tt = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(th)
            t1["cell_tile"] += int((p.argmax(-1) == tt).sum())
            ok = b["slot"][play] >= 0
            cl = o["card"][play][ok].float(); tg = b["slot"][play][ok]
            s["card"] += float(Fn.cross_entropy(cl, tg, reduction="sum")); t1["card"] += int((cl.argmax(-1) == tg).sum())
            c["play"] += int(play.sum()); c["card_n"] = c.get("card_n", 0) + int(ok.sum())
        ok = wt & (b["wait"] >= 0)
        if ok.any():
            wl = o["wait"][ok].float(); wg = b["wait"][ok]
            s["wait"] += float(Fn.cross_entropy(wl, wg, reduction="sum")); t1["wait"] += int((wl.argmax(-1) == wg).sum()); c["wait"] += int(ok.sum())
        s["gate"] += float(Fn.binary_cross_entropy_with_logits(o["gate"].float(), b["gate"], reduction="sum"))
        gp = o["gate"] > 0; t1["gate_tp"] += int((gp & play).sum()); t1["gate_tn"] += int((~gp & wt).sum())
        npos += int(play.sum()); nneg += int(wt.sum())
        s["value"] += float(Fn.cross_entropy(o["value"].float(), b["value"], reduction="sum")); t1["value"] += int((o["value"].argmax(-1) == b["value"]).sum())
        c["n"] += len(ids)
    P = max(c["play"], 1); K = max(c.get("card_n", 0), 1); W = max(c["wait"], 1); N = max(c["n"], 1)
    return {"n": c["n"], "n_play": c["play"], "n_card": c.get("card_n", 0), "n_wait": c["wait"], "unmapped_rows": unm,
            "nll_cell": s["cell"] / P, "nll_card": s["card"] / K, "nll_wait": s["wait"] / W,
            "nll_gate": s["gate"] / N, "nll_value": s["value"] / N,
            "nll_total": s["cell"] / P + s["card"] / K + .5 * s["wait"] / W + s["gate"] / N + .5 * s["value"] / N,
            "top1_cell_half": t1["cell_half"] / P, "top1_cell_tile": t1["cell_tile"] / P, "top1_card": t1["card"] / K,
            "top1_wait": t1["wait"] / W, "gate_bal_acc": .5 * (t1["gate_tp"] / max(npos, 1) + t1["gate_tn"] / max(nneg, 1)),
            "gate_acc": (t1["gate_tp"] + t1["gate_tn"]) / N, "value_acc": t1["value"] / N}


if a.mode == "latonly":
    res = json.load(open(a.out_json))
else:
    res = {"ckpt": a.ckpt, "sha256": hashlib.sha256(open(a.ckpt, "rb").read()).hexdigest(), "n_params": n_params,
           "d": int(st["args"]["d"]), "layers": int(st["args"]["layers"]), "feature_version": model.feature_version,
           "memory": mver, "vocab_remapped": lut is not None, "epoch_selected": st.get("epoch"), "step": st.get("step"),
           "args": {k: st["args"].get(k) for k in ("seed", "epochs", "bs", "lr", "amp", "grid", "feature_version", "max_steps")},
           "n_rows": {k: int(len(v)) for k, v in G.items()}}
    for k, v in G.items():
        res[k] = nll(v)
        print(k, json.dumps({x: round(y, 4) if isinstance(y, float) else y for x, y in res[k].items()}), flush=True)


def lat(bs, amp, it):
    b = batch(G[next(iter(G))][:bs]); ts = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        for k in range(it + 20):
            torch.cuda.synchronize(); t = time.perf_counter()
            model(b, card=b["card"], form=b["form"]); torch.cuda.synchronize()
            if k >= 20:
                ts.append((time.perf_counter() - t) * 1e3)
    ts = np.array(ts)
    return {"p50_ms": float(np.percentile(ts, 50)), "p90_ms": float(np.percentile(ts, 90)), "p99_ms": float(np.percentile(ts, 99))}


if a.mode != "nolat" and dev.type == "cuda":
    res["latency_ms"] = {f"bs{bs}_{'bf16' if amp else 'fp32'}": lat(bs, amp, it)
                         for bs, it in ((1, 300), (1024, 40)) for amp in (False, True)}
    res["gpu"] = torch.cuda.get_device_name(0)
res["seconds"] = round(time.time() - t0)
json.dump(res, open(a.out_json, "w"), indent=1)
print(json.dumps({"n_params": n_params, "latency": res.get("latency_ms")}))
