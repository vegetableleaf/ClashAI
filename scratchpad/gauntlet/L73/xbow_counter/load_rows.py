"""Stage A: pull all icebow-deck (deck_id 90) IL rows (all splits) from gen_dataset_v31_public.npz into rows.pkl. CPU, read-only."""
import ctypes, json, pickle, zipfile, time, sys
import numpy as np
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
NPZ = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v31_public.npz"
T0 = time.time()
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
meta = json.loads(str(z["meta"]))
sel = np.flatnonzero(z["deck_id"] == 90)
print("rows", len(sel), flush=True)
R = {"sel": sel, "CV": meta["card_vocab"], "tags": z["tags"]}
for k in ["rep", "side", "tick", "split", "y_gate", "y_card", "y_cell", "y_xy", "hand_card", "opp_cycle", "sc"]:
    a = take(zf, k, sel)
    if k == "sc": a = a[:, [3, 5]].copy()
    R[k] = a; print(k, a.shape, round(time.time() - T0), flush=True)
pickle.dump(R, open(HERE + "rows.pkl", "wb"))
print("saved")
