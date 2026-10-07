"""Teacher-forced R1e u0155 on VALIDATION icebow rows where the PRO played the X-Bow (deck_id 90, split 1).
Card forced to X-Bow (hand slot form), as eval does. Saves full X-Bow cell logits + the gate p_play for those rows.
Loader/inference copied from L73/xbow_counter/model_forward.py; data and checkpoint read from the main checkout.
CPU only, 4 threads, below-normal priority (run via lowprio.py)."""
import json, sys, time, zipfile
from pathlib import Path
import numpy as np, torch
WT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WT))
torch.set_num_threads(4)
from pipeline.eval_gen import GenRows, load_model
HERE = Path(__file__).resolve().parent
NPZ = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v31_public.npz"
CKPT = "C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt"
OUT = "C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/xbow_logits.npz"
T0 = time.time()
def log(*a): print(f"[{time.time()-T0:6.0f}s]", *a, flush=True)


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


zf = zipfile.ZipFile(NPZ); z = np.load(NPZ, allow_pickle=False)
meta = json.loads(str(z["meta"])); CV = meta["card_vocab"]; XB = CV.index("x-bow")
val = np.flatnonzero((z["deck_id"] == 90) & (z["split"] == 1))
yg, yc = take(zf, "y_gate", val), take(zf, "y_card", val)
sel = val[(yg == 1) & (yc == XB)]; n = len(sel); log("val rows", len(val), "pro X-Bow rows", n)
keys = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card", "y_hand_pos", "y_xy",
        "y_wait_card", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability", "y_cell"]
sub = {k: take(zf, k, sel) for k in keys}
off = z["off"]; lens = off[sel + 1] - off[sel]
gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather); sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
model, _ = load_model(Path(CKPT), torch.device("cpu")); model.eval()
rows = GenRows(sub, np.arange(n), torch.device("cpu"))
hand, hform = sub["hand_card"].astype(int), sub["hand_form"].astype(int)
has = hand == XB
assert has.any(1).all(), "pro X-Bow row without X-Bow in hand"
slot = has.argmax(1)
gate = np.zeros(n, np.float32); logits = np.zeros((n, 2304), np.float32)
with torch.no_grad():
    for s in range(0, n, 256):
        ids = np.arange(s, min(s + 256, n)); b = rows.batch(ids); enc = model.encode_gen(b); h = model.heads_gen(enc, b)
        gate[ids] = h["gate"].float().numpy()
        form = torch.tensor(hform[ids, slot[ids]]); card = torch.full((len(ids),), XB, dtype=torch.long)
        logits[ids] = model.cell_logits_gen(enc, card, form).float().numpy()
        log("fwd", s, "/", n)
np.savez_compressed(OUT, sel=sel, logits=logits, p_play=1 / (1 + np.exp(-gate.astype(np.float64))),
                    y_cell=sub["y_cell"], tick=sub["tick"], rep=sub["rep"], side=sub["side"], el=np.floor(sub["sc"][:, 3] * 10 + 1e-3))
log("saved", OUT)
