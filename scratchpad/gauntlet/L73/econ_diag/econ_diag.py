"""Elixir-economy diagnosis on R1e u0155 (L73; loader copied from L71 rocket_diag). CPU only, read-only on pipeline/, no training, no sim.

Rows: gen_dataset_v31_public.npz, VALIDATION split (split==1), icebow-deck pro rows (deck_id 90 = ice-wizard knight rocket
skeletons tesla the-log tornado x-bow, the base-key set of the icebow deck; evo/hero forms share the id).
Teacher-forced exactly like e1_eval.live_decide: P(play)=sigmoid(gate); card = argmax over AFFORDABLE hand slots of the
card logits (afford = int(elixir the row shows) >= card cost); cell = argmax of that card's cell logits.
Never uses opponent hidden state: every model input is the dataset's public v4 feature set (GenRows.batch).

run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L71/rocket_diag/rocket_diag.py
out: results.json next to this file.
"""
from __future__ import annotations

import ctypes
import json
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
torch.set_num_threads(4)
try:  # below-normal priority (laptop is shared)
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass

from pipeline.eval_gen import GenRows, load_model                      # noqa: E402  (imported as-is)
from pipeline.opp_elixir_count import card_cost                         # noqa: E402

NPZ = REPO / "icebow/data/pipeline/gen_dataset_v31_public.npz"
CKPT = REPO / "icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt"
LABELS = REPO / ".foreman/codex_autopilot/runs/public_labels_full_reconstructed/labels.jsonl"
DECK_ID = 90
TAUS = (0.27, 0.35)
GX, GY = 36, 64
B_BOOT = 1000
RNG = np.random.default_rng(0)
# opp K, L, R princess/king centres in MY frame (me at bottom), tiles; obs_contract.py:28-34. Rocket radius 2.0 tiles.
TOWERS = np.array([[9.0, 3.0], [3.5, 6.5], [14.5, 6.5]])
ROCKET_R = 2.0
CX = np.tile(np.arange(GX), GY)
CY = np.repeat(np.arange(GY), GX)
TX, TY = CX / 2.0, CY / 2.0
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ===================================================================================== streaming npz reader
def take(zf: zipfile.ZipFile, name: str, idx: np.ndarray) -> np.ndarray:
    """rows ``idx`` (sorted unique) of ``name.npy`` inside the compressed npz, streamed (never holds the full array)."""
    idx = np.asarray(idx)
    with zf.open(name + ".npy") as f:
        ver = np.lib.format.read_magic(f)
        shape, _, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0) else np.lib.format.read_array_header_2_0(f))
        rb = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
        out = np.empty((len(idx),) + tuple(shape[1:]), dt)
        step = max(1, (96 << 20) // max(rb, 1))
        o = 0
        for lo in range(0, shape[0], step):
            n = min(step, shape[0] - lo)
            buf = bytearray()
            while len(buf) < n * rb:
                c = f.read(n * rb - len(buf))
                if not c:
                    raise EOFError(name)
                buf += c
            a, b = np.searchsorted(idx, [lo, lo + n])
            if b > a:
                out[o:o + b - a] = np.frombuffer(buf, dt).reshape((n,) + tuple(shape[1:]))[idx[a:b] - lo]
                o += b - a
    assert o == len(idx), (name, o, len(idx))
    return out


def boot(v, rep, B=B_BOOT):
    """mean + replay-cluster bootstrap 95% CI -> [mean, lo, hi]."""
    v = np.asarray(v, float)
    if len(v) == 0:
        return [None, None, None]
    u, inv = np.unique(rep, return_inverse=True)
    s, c = np.bincount(inv, v, len(u)), np.bincount(inv, minlength=len(u)).astype(float)
    ix = RNG.integers(0, len(u), (B, len(u)))
    m = s[ix].sum(1) / np.maximum(c[ix].sum(1), 1)
    return [float(v.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def auc(y, s):
    u, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    cs = np.cumsum(cnt)
    r = ((cs - cnt + 1 + cs) / 2.0)[inv]
    n1 = int(y.sum()); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


# ===================================================================================== load rows
zf = zipfile.ZipFile(NPZ)
z = np.load(NPZ, allow_pickle=False)
meta = json.loads(str(z["meta"]))
CV = meta["card_vocab"]
RK, XB = CV.index("rocket"), CV.index("x-bow")
deck_id, split, y_gate, y_card = z["deck_id"], z["split"], z["y_gate"], z["y_card"]
sel = np.flatnonzero((deck_id == DECK_ID) & (split == 1))
n = len(sel)
log("val icebow-deck rows", n, "plays", int((y_gate[sel] == 1).sum()))
COST = np.zeros(len(CV))
for i, c in enumerate(CV):
    if i:
        COST[i] = card_cost(c.replace("-", "_")) or 0.0
keys = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card",
        "y_hand_pos", "y_xy", "y_wait_card", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle",
        "projectiles", "effects", "own_ability", "y_cell"]
sub = {}
for k in keys:
    sub[k] = take(zf, k, sel)
    log("loaded", k, sub[k].shape)
off = z["off"]
lens = off[sel + 1] - off[sel]
gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
sub["tok"] = take(zf, "tok", gather)
sub["unit_form"] = take(zf, "unit_form", gather)
sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
tags = z["tags"]
# pro X-Bow rows, ALL splits of the icebow deck (pro-rate stats only, no model): sc, cell, rep
xb_all = np.flatnonzero((deck_id == DECK_ID) & (y_gate == 1) & (y_card == XB))
xb_all_sc = take(zf, "sc", xb_all)
xb_all_cell, xb_all_rep, xb_all_split = z["y_cell"][xb_all].astype(int), z["rep"][xb_all], split[xb_all]
log("pro xbow all splits", len(xb_all))

# ===================================================================================== model forward
model, st = load_model(CKPT, torch.device("cpu"))
model.eval()
FV = int(st["args"].get("feature_version", 1))
rows = GenRows(sub, np.arange(n), torch.device("cpu"))
gate_logit = np.zeros(n, np.float32)
card_logit = np.zeros((n, 4), np.float32)
need_cell = np.flatnonzero((sub["y_gate"] == 1) & np.isin(sub["y_card"], [RK, XB]))
cell_row = {int(r): j for j, r in enumerate(need_cell)}
cell_p = np.zeros((len(need_cell), GX * GY), np.float32)
with torch.no_grad():
    for s in range(0, n, 256):
        ids = np.arange(s, min(s + 256, n))
        b = rows.batch(ids)
        enc = model.encode_gen(b)
        h = model.heads_gen(enc, b)
        gate_logit[ids] = h["gate"].float().numpy()
        card_logit[ids] = h["card"].float().numpy()
        loc = [i for i, r in enumerate(ids) if int(r) in cell_row]
        if loc:
            li = torch.tensor(loc)
            c = model.cell_logits_gen({k: v[li] for k, v in enc.items()}, b["card"][li], b["form"][li])
            cell_p[[cell_row[int(ids[i])] for i in loc]] = torch.softmax(c.float(), -1).numpy()
        if (s // 256) % 20 == 0:
            log("forward", s, "/", n)
log("forward done; ckpt feature_version", FV)

# ===================================================================================== per-row decision quantities
sc, hand, ycard, ygate, rep, tick, side = sub["sc"], sub["hand_card"].astype(int), sub["y_card"].astype(int), sub["y_gate"], sub["rep"], sub["tick"], sub["side"]
p_play = 1 / (1 + np.exp(-gate_logit.astype(np.float64)))
el_int = np.floor(sc[:, 3] * 10 + 1e-3)
inhand = hand > 0
afford = inhand & (COST[hand] <= el_int[:, None] + 1e-6)
any_aff = afford.any(1)
lg = card_logit.astype(np.float64)
lg_aff = np.where(afford, lg, -np.inf)


def softmax_rows(a):
    m = np.where(np.isfinite(a).any(1, keepdims=True), a.max(1, keepdims=True), 0.0)
    e = np.exp(np.where(np.isfinite(a), a - m, -np.inf))
    return e / np.maximum(e.sum(1, keepdims=True), 1e-300)


P_hand = softmax_rows(np.where(inhand, lg, -np.inf))        # over all hand cards
P_aff = softmax_rows(lg_aff)                                 # over affordable hand cards (what live_decide sees)
isR = hand == RK
r_in_hand = isR.any(1)
r_aff = (isR & afford).any(1)
PR_hand = (P_hand * isR).sum(1)
PR_aff = (P_aff * isR).sum(1)
am_aff = lg_aff.argmax(1)

# ===================================================================================== L73 economy questions
# Owner 2026-10-06: late-game collapse into cheap-card cycling. Hypotheses: (H1) the gate fires more often than pros;
# (H2) when the model's preferred card (argmax over ALL hand cards) is unaffordable, live_decide substitutes the best
# AFFORDABLE card instead of waiting, keeping elixir low so X-Bow / Rocket (6) never come.
ph = np.where(tick < 2400, "1x", np.where(tick < 3600, "2x", "OT"))
pro_play = ygate == 1
am_hand = np.where(inhand, lg, -np.inf).argmax(1)
top_aff = afford[np.arange(n), am_hand]
cost_aff = COST[hand[np.arange(n), am_aff]]
res = {"ckpt": str(CKPT.relative_to(REPO)), "rows": int(n)}
for tau in TAUS:
    mp = (p_play > tau) & any_aff
    sub_ = mp & ~top_aff
    for P in ("1x", "2x", "OT", "all"):
        m = np.ones(n, bool) if P == "all" else (ph == P)
        k = f"tau{tau}_{P}"
        res[k] = {
            "rows": int(m.sum()),
            "pro_play_rate": boot(pro_play[m], rep[m]),
            "model_play_rate": boot(mp[m], rep[m]),
            "model_play_when_pro_waited": boot(mp[m & ~pro_play], rep[m & ~pro_play]),
            "substitution_share_of_model_plays": boot(sub_[m & mp], rep[m & mp]),
            "model_play_cost_mean": boot(cost_aff[m & mp], rep[m & mp]),
            "pro_play_cost_mean": boot(COST[ycard[m & pro_play]], rep[m & pro_play]),
            "model_cheap_share(<=3)": boot(cost_aff[m & mp] <= 3, rep[m & mp]),
            "pro_cheap_share(<=3)": boot(COST[ycard[m & pro_play]] <= 3, rep[m & pro_play]),
            "unaffordable_top_cards": dict(Counter(CV[c] for c in hand[np.arange(n), am_hand][m & sub_]).most_common(6)),
            "wait_for_top_play_rate": boot((mp & top_aff)[m], rep[m]),
            "wait_for_top_cost_mean": boot(cost_aff[m & mp & top_aff], rep[m & mp & top_aff]),
        }
# tau that matches the pro play rate on these rows (overall and per phase)
for P in ("1x", "2x", "OT", "all"):
    m = np.ones(n, bool) if P == "all" else (ph == P)
    target = pro_play[m].mean()
    pp = np.where(any_aff[m], p_play[m], 0.0)
    res[f"tau_matching_pro_rate_{P}"] = float(np.quantile(pp, 1 - target))
(OUT / "results.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    if isinstance(v, dict):
        print(k, {kk: (vv if not isinstance(vv, list) else [round(x, 3) if x is not None else None for x in vv]) for kk, vv in v.items()})
    else:
        print(k, v)
