"""L73 rl_diag Q3: how much of RL's change (R1e u0155 vs its base gen_v3.1c) survives greedy decoding?
Teacher-forced on VALIDATION icebow-deck pro rows (gen_dataset_v31_public.npz, split==1, deck_id 90). CPU, 4 threads, below-normal.
Loader = L73/econ_diag/econ_diag.py (take / GenRows / load_model), both models in one batch loop.

Decoders (both from the code, not assumed):
  greedy (live / e1_eval.live_decide): play iff sigmoid(gate) > tau (0.35 live) and a card is affordable; card = argmax over
         AFFORDABLE hand slots; cell = argmax of that card's cell logits.
  sampled (RL rollouts, rl_royale.policy_terms): P(play) = sigmoid((gate - logit(0.27)) / 0.5); card = softmax(logits / 0.5)
         over affordable; cell = softmax(cell / 0.5).
Action space compared at the 5-way level {wait, hand slot 0..3}; cell separately (pro card teacher-forced, and the common
greedy card when both models play the same card).
run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/rl_diag/q3_softdiff.py  -> q3_results.json
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[v] = "4"
import ctypes, json, sys, time, zipfile
from pathlib import Path
import numpy as np
import torch

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
torch.set_num_threads(4)
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.eval_gen import GenRows, load_model          # noqa: E402
from pipeline.opp_elixir_count import card_cost             # noqa: E402

NPZ = REPO / "icebow/data/pipeline/gen_dataset_v31_public.npz"
CK = {"r1e": REPO / "icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt",
      "base": REPO / "icebow/data/pipeline/gen_v31c_s0/gen_s0.pt"}
TAU_LIVE, TAU_RL, T_RL = 0.35, 0.27, 0.5
RNG = np.random.default_rng(0)
T0 = time.time()
def log(*a): print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def take(zf, name, idx):
    idx = np.asarray(idx)
    with zf.open(name + ".npy") as f:
        ver = np.lib.format.read_magic(f)
        shape, _, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0) else np.lib.format.read_array_header_2_0(f))
        rb = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
        out = np.empty((len(idx),) + tuple(shape[1:]), dt); step = max(1, (96 << 20) // max(rb, 1)); o = 0
        for lo in range(0, shape[0], step):
            n = min(step, shape[0] - lo); buf = bytearray()
            while len(buf) < n * rb:
                c = f.read(n * rb - len(buf))
                if not c: raise EOFError(name)
                buf += c
            a, b = np.searchsorted(idx, [lo, lo + n])
            if b > a:
                out[o:o + b - a] = np.frombuffer(buf, dt).reshape((n,) + tuple(shape[1:]))[idx[a:b] - lo]; o += b - a
    assert o == len(idx)
    return out


def boot(v, rep, B=1000):
    v = np.asarray(v, float)
    if len(v) == 0: return [None, None, None]
    u, inv = np.unique(rep, return_inverse=True)
    s, c = np.bincount(inv, v, len(u)), np.bincount(inv, minlength=len(u)).astype(float)
    ix = RNG.integers(0, len(u), (B, len(u))); m = s[ix].sum(1) / np.maximum(c[ix].sum(1), 1)
    return [float(v.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def softmax_masked(lg, mask, T=1.0):
    a = np.where(mask, lg / T, -np.inf)
    m = np.where(mask.any(1, keepdims=True), a.max(1, keepdims=True), 0.0)
    e = np.exp(np.where(mask, a - m, -np.inf)); return e / np.maximum(e.sum(1, keepdims=True), 1e-300)


def logit(p): return np.log(p) - np.log1p(-p)


# ------------------------------------------------------------------ rows
zf = zipfile.ZipFile(NPZ); z = np.load(NPZ, allow_pickle=False)
CV = json.loads(str(z["meta"]))["card_vocab"]; RK, XB = CV.index("rocket"), CV.index("x-bow")
sel = np.flatnonzero((z["deck_id"] == 90) & (z["split"] == 1)); n = len(sel); log("val icebow rows", n)
COST = np.zeros(len(CV))
for i, c in enumerate(CV):
    if i: COST[i] = card_cost(c.replace("-", "_")) or 0.0
keys = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card", "y_hand_pos", "y_xy",
        "y_wait_card", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability", "y_cell"]
sub = {k: take(zf, k, sel) for k in keys}
off = z["off"]; lens = off[sel + 1] - off[sel]
gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather)
sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
log("rows loaded")
hand, hform, sc = sub["hand_card"].astype(int), sub["hand_form"].astype(int), sub["sc"]
el_int = np.floor(sc[:, 3] * 10 + 1e-3)
afford = (hand > 0) & (COST[hand] <= el_int[:, None] + 1e-6); any_aff = afford.any(1)
pro_play = sub["y_gate"] == 1; rep, tick = sub["rep"], sub["tick"]

M = {k: load_model(p, torch.device("cpu"))[0].eval() for k, p in CK.items()}
rows = GenRows(sub, np.arange(n), torch.device("cpu"))
gate = {k: np.zeros(n) for k in M}; card = {k: np.zeros((n, 4)) for k in M}
# cell stats: pro card teacher-forced on pro-played rows; common greedy card on rows where both greedy-play the same card
cellP = {"tv1": np.full(n, np.nan), "tv05": np.full(n, np.nan), "flip": np.full(n, np.nan)}
cellG = {"tv1": np.full(n, np.nan), "flip": np.full(n, np.nan)}


def cell_stats(encs, li, crd, frm):
    lg = {k: M[k].cell_logits_gen({kk: v[li] for kk, v in encs[k].items()}, crd, frm).double() for k in M}
    p1 = {k: torch.softmax(lg[k], -1) for k in M}; p05 = {k: torch.softmax(lg[k] / T_RL, -1) for k in M}
    tv1 = 0.5 * (p1["r1e"] - p1["base"]).abs().sum(1); tv05 = 0.5 * (p05["r1e"] - p05["base"]).abs().sum(1)
    flip = (lg["r1e"].argmax(1) != lg["base"].argmax(1)).double()
    return tv1.numpy(), tv05.numpy(), flip.numpy()


with torch.no_grad():
    for s in range(0, n, 256):
        ids = np.arange(s, min(s + 256, n)); b = rows.batch(ids)
        encs, hs = {}, {}
        for k, m in M.items():
            encs[k] = m.encode_gen(b); hs[k] = m.heads_gen(encs[k], b)
            gate[k][ids] = hs[k]["gate"].double().numpy(); card[k][ids] = hs[k]["card"].double().numpy()
        loc = np.flatnonzero(pro_play[ids])
        if len(loc):
            li = torch.tensor(loc); tv1, tv05, fl = cell_stats(encs, li, b["card"][li], b["form"][li])
            cellP["tv1"][ids[loc]], cellP["tv05"][ids[loc]], cellP["flip"][ids[loc]] = tv1, tv05, fl
        # greedy: both play the same card -> compare the cell argmax for that card
        pa = {k: (1 / (1 + np.exp(-gate[k][ids])) > TAU_LIVE) & any_aff[ids] for k in M}
        ca = {k: np.where(afford[ids], card[k][ids], -np.inf).argmax(1) for k in M}
        loc = np.flatnonzero(pa["r1e"] & pa["base"] & (ca["r1e"] == ca["base"]))
        if len(loc):
            slot = ca["r1e"][loc]; li = torch.tensor(loc)
            crd = torch.tensor(hand[ids[loc], slot]); frm = torch.tensor(hform[ids[loc], slot])
            tv1, _, fl = cell_stats(encs, li, crd, frm)
            cellG["tv1"][ids[loc]], cellG["flip"][ids[loc]] = tv1, fl
        if (s // 256) % 20 == 0: log("fwd", s, "/", n)
log("forward done")

# ------------------------------------------------------------------ decision quantities
R = {"rows": int(n), "ckpts": {k: str(v.relative_to(REPO)) for k, v in CK.items()}}
pp = {k: 1 / (1 + np.exp(-gate[k])) for k in M}                                     # model P(play)
pb = {k: 1 / (1 + np.exp(-(gate[k] - logit(TAU_RL)) / T_RL)) for k in M}             # RL behaviour P(play)
for k in M: pb[k] = np.where(any_aff, pb[k], 0.0)
g_live = {k: (pp[k] > TAU_LIVE) & any_aff for k in M}
g_rl = {k: (pp[k] > TAU_RL) & any_aff for k in M}
c1 = {k: softmax_masked(card[k], afford) for k in M}; c05 = {k: softmax_masked(card[k], afford, T_RL) for k in M}
am = {k: np.where(afford, card[k], -np.inf).argmax(1) for k in M}
# 5-way {wait, slot0..3}
def five_soft(k): return np.column_stack([1 - pb[k], pb[k][:, None] * np.where(any_aff[:, None], c05[k], 0.0)])
def five_greedy(k, g):
    o = np.zeros((n, 5)); o[np.arange(n), np.where(g[k], 1 + am[k], 0)] = 1; return o
tv_soft = 0.5 * np.abs(five_soft("r1e") - five_soft("base")).sum(1)
flip_live = (five_greedy("r1e", g_live) != five_greedy("base", g_live)).any(1)
flip_rl = (five_greedy("r1e", g_rl) != five_greedy("base", g_rl)).any(1)
ph = np.where(tick < 2400, "1x", np.where(tick < 3600, "2x", "OT"))
dpp = pp["r1e"] - pp["base"]; dpb = pb["r1e"] - pb["base"]
tvc1 = 0.5 * np.abs(c1["r1e"] - c1["base"]).sum(1); tvc05 = 0.5 * np.abs(c05["r1e"] - c05["base"]).sum(1)
both_live = g_live["r1e"] & g_live["base"]
isR = hand == RK; r_aff = (isR & afford).any(1)
pR = {k: (c1[k] * isR).sum(1) for k in M}; pR05 = {k: (c05[k] * isR).sum(1) for k in M}
for P in ("all", "1x", "2x", "OT"):
    m = np.ones(n, bool) if P == "all" else ph == P
    d = {"rows": int(m.sum()), "pro_play_rate": boot(pro_play[m], rep[m])}
    for k in M:
        d[f"{k}_mean_P(play)"] = boot(pp[k][m], rep[m]); d[f"{k}_sampled_play_rate(T.5,tau.27)"] = boot(pb[k][m], rep[m])
        d[f"{k}_greedy_play_rate(tau.35)"] = boot(g_live[k][m], rep[m]); d[f"{k}_greedy_play_rate(tau.27)"] = boot(g_rl[k][m], rep[m])
    d["dP(play) mean r1e-base"] = boot(dpp[m], rep[m]); d["|dP(play)| mean"] = boot(np.abs(dpp[m]), rep[m])
    d["|dP(play)| p50/p90/p99"] = [float(np.percentile(np.abs(dpp[m]), q)) for q in (50, 90, 99)]
    d["share |dP(play)|>0.02/0.05/0.10"] = [float((np.abs(dpp[m]) > x).mean()) for x in (0.02, 0.05, 0.10)]
    d["sampled |dP_b| mean"] = boot(np.abs(dpb[m]), rep[m]); d["sampled dP_b mean r1e-base"] = boot(dpb[m], rep[m])
    d["greedy gate flip rate tau.35"] = boot((g_live["r1e"] != g_live["base"])[m], rep[m])
    d["greedy gate flips tau.35: r1e plays/base waits, r1e waits/base plays"] = [int((g_live["r1e"] & ~g_live["base"] & m).sum()), int((~g_live["r1e"] & g_live["base"] & m).sum())]
    ma = m & any_aff
    d["card TV T=1 mean (affordable)"] = boot(tvc1[ma], rep[ma]); d["card TV T=0.5 mean"] = boot(tvc05[ma], rep[ma])
    d["share card TV(T=1)>0.05/0.10/0.20"] = [float((tvc1[ma] > x).mean()) for x in (0.05, 0.10, 0.20)]
    d["card argmax flip rate (affordable rows)"] = boot((am["r1e"] != am["base"])[ma], rep[ma])
    d["card argmax flip rate (both greedy-play)"] = boot((am["r1e"] != am["base"])[m & both_live], rep[m & both_live])
    d["5-way sampled TV mean (T.5,tau.27)"] = boot(tv_soft[m], rep[m])
    d["share 5-way sampled TV>0.02/0.05/0.10"] = [float((tv_soft[m] > x).mean()) for x in (0.02, 0.05, 0.10)]
    d["5-way greedy action flip rate tau.35"] = boot(flip_live[m], rep[m]); d["5-way greedy action flip rate tau.27"] = boot(flip_rl[m], rep[m])
    for x in (0.05, 0.10):
        big = m & (tv_soft > x)
        d[f"greedy flip rate tau.35 among rows with sampled TV>{x}"] = boot(flip_live[big], rep[big])
    mp = m & pro_play & np.isfinite(cellP["tv1"])
    d["cell TV T=1 (pro card)"] = boot(cellP["tv1"][mp], rep[mp]); d["cell TV T=0.5 (pro card)"] = boot(cellP["tv05"][mp], rep[mp])
    d["cell argmax flip (pro card)"] = boot(cellP["flip"][mp], rep[mp])
    mg = m & np.isfinite(cellG["flip"])
    d["cell argmax flip (both greedy-play same card)"] = boot(cellG["flip"][mg], rep[mg]); d["rows both greedy-play same card"] = int(mg.sum())
    full = flip_live.copy(); full[mg] |= cellG["flip"][mg] > 0     # 5-way flip OR same card but different cell
    d["full greedy action flip (gate|card|cell) tau.35"] = boot(full[m], rep[m])
    mr = m & r_aff
    d["rocket: rows affordable"] = int(mr.sum())
    for k in M:
        d[f"{k} P(rocket|play) T=1"] = boot(pR[k][mr], rep[mr]); d[f"{k} P(rocket|play) T=0.5"] = boot(pR05[k][mr], rep[mr])
        d[f"{k} greedy rocket plays per 1000 rows"] = boot(1000 * (g_live[k] & isR[np.arange(n), am[k]])[m], rep[m])
        d[f"{k} sampled rocket plays per 1000 rows"] = boot(1000 * (pb[k] * pR05[k])[m], rep[m])
    d["rocket greedy choice flips (rows rocket affordable & both play)"] = int((mr & both_live & (isR[np.arange(n), am["r1e"]] != isR[np.arange(n), am["base"]])).sum())
    R[P] = d
(HERE / "q3_results.json").write_text(json.dumps(R, indent=1))
for P in ("all", "1x", "2x", "OT"):
    print(f"== {P}")
    for k, v in R[P].items():
        print(f"  {k:62s}", [round(x, 4) if isinstance(x, float) else x for x in v] if isinstance(v, list) else v)
log("saved", HERE / "q3_results.json")
