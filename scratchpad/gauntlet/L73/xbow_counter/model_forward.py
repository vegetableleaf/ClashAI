"""Teacher-forced R1e u0155 on VALIDATION icebow-deck rows (loader/inference copied from L73/econ_diag). CPU, 4 threads, below-normal priority.
Per row: p_play, P(card = X-Bow | affordable hand), argmax-affordable card is X-Bow, and for X-Bow-affordable rows the placement
distribution mass inside the offensive reach of each alive-tower subset + the argmax cell. Public inputs only (GenRows.batch)."""
import ctypes, json, sys, time, zipfile, pickle, itertools
import numpy as np, torch
sys.path.insert(0, "C:/Users/benpe/ClashBot")
torch.set_num_threads(4)
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
from pathlib import Path
from pipeline.eval_gen import GenRows, load_model
from pipeline.opp_elixir_count import card_cost
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
    return out
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
NPZ = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v31_public.npz"
CKPT = "C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt"
GX, GY = 36, 64; T0 = time.time()
def log(*a): print(f"[{time.time()-T0:6.0f}s]", *a, flush=True)
zf = zipfile.ZipFile(NPZ); z = np.load(NPZ, allow_pickle=False)
meta = json.loads(str(z["meta"])); CV = meta["card_vocab"]; XB = CV.index("x-bow")
deck_id, split = z["deck_id"], z["split"]
sel = np.flatnonzero((deck_id == 90) & (split == 1)); n = len(sel); log("val rows", n)
COST = np.zeros(len(CV))
for i, c in enumerate(CV):
    if i: COST[i] = card_cost(c.replace("-", "_")) or 0.0
keys = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card", "y_hand_pos", "y_xy",
        "y_wait_card", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability", "y_cell"]
sub = {k: take(zf, k, sel) for k in keys}
off = z["off"]; lens = off[sel + 1] - off[sel]
gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather); sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
model, st = load_model(Path(CKPT), torch.device("cpu")); model.eval()
rows = GenRows(sub, np.arange(n), torch.device("cpu"))
hand, hform, sc = sub["hand_card"].astype(int), sub["hand_form"].astype(int), sub["sc"]
el_int = np.floor(sc[:, 3] * 10 + 1e-3)
afford = (hand > 0) & (COST[hand] <= el_int[:, None] + 1e-6)
xb_aff = ((hand == XB) & afford)
# offensive masks over the 2304 cells; own-frame centre x = 18 - cx/2, y = cy/2 (verified against 300 pro X-Bow placements)
c = np.arange(GX * GY); cx = 18.0 - (c % GX) / 2.0; cy = (c // GX) / 2.0
TW = {"K": (9.0, 3.0), "L": (3.5, 6.5), "R": (14.5, 6.5)}
inr = {k: (np.hypot(cx - x, cy - y) <= 13.0385) for k, (x, y) in TW.items()}
subsets = [s for r in (1, 2, 3) for s in itertools.combinations("KLR", r)]
masks = np.stack([np.any([inr[k] for k in s], 0) for s in subsets]).astype(np.float32)   # [7, 2304]
gate = np.zeros(n, np.float32); card_l = np.zeros((n, 4), np.float32)
offmass = np.full((n, len(subsets)), np.nan, np.float32); argx = np.full(n, -1, np.int32)
with torch.no_grad():
    for s in range(0, n, 256):
        ids = np.arange(s, min(s + 256, n)); b = rows.batch(ids); enc = model.encode_gen(b); h = model.heads_gen(enc, b)
        gate[ids] = h["gate"].float().numpy(); card_l[ids] = h["card"].float().numpy()
        loc = [i for i, r in enumerate(ids) if xb_aff[r].any()]
        if loc:
            li = torch.tensor(loc); slot = xb_aff[ids[loc]].argmax(1)
            form = torch.tensor(hform[ids[loc], slot]); card = torch.full((len(loc),), XB, dtype=torch.long)
            lg = model.cell_logits_gen({k: v[li] for k, v in enc.items()}, card, form)
            p = torch.softmax(lg.float(), -1).numpy()
            offmass[ids[loc]] = p @ masks.T; argx[ids[loc]] = p.argmax(1)
        if (s // 256) % 20 == 0: log("fwd", s, "/", n)
p_play = 1 / (1 + np.exp(-gate.astype(np.float64)))
lg = np.where(afford, card_l.astype(np.float64), -np.inf)
m = np.where(np.isfinite(lg).any(1, keepdims=True), lg.max(1, keepdims=True), 0.0)
e = np.exp(np.where(np.isfinite(lg), lg - m, -np.inf)); P_aff = e / np.maximum(e.sum(1, keepdims=True), 1e-300)
p_xb = (P_aff * (hand == XB)).sum(1); am = lg.argmax(1); am_is_xb = afford.any(1) & (hand[np.arange(n), am] == XB)
pickle.dump({"sel": sel, "p_play": p_play, "p_xb_given_play": p_xb, "argmax_is_xb": am_is_xb, "any_aff": afford.any(1), "xb_aff": xb_aff.any(1), "offmass": offmass,
             "subsets": ["".join(s) for s in subsets], "argcell": argx}, open(HERE + "model_rows.pkl", "wb"))
log("saved")
