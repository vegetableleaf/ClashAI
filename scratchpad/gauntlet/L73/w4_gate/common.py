"""Shared: streaming npz row loader + GenRows for selected rows of gen_dataset_v32_fv5 (copied from L73/rocket_lead/model_forward_rk.py)."""
import json, os, sys, zipfile
import numpy as np
# (copied from the chip_rocket worker; the caller puts ITS repo root on sys.path)
ROOT = os.environ.get("W4_DATA_ROOT", "C:/Users/benpe/ClashBot")   # VM: ~/ClashBot
NPZ = ROOT + "/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
KEYS = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card", "y_hand_pos", "y_xy",
        "y_wait_card", "y_wait_dt", "y_crowns", "tick", "side", "rep", "split", "deck_id", "opp_past", "opp_cycle", "projectiles", "effects", "own_ability", "y_cell"]
CK = {"live": ROOT + "/icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt",
      "R1e": ROOT + "/icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt",
      "gen_v32": ROOT + "/icebow/data/pipeline/gen_v32_s0/gen_s0.pt"}


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


def load_rows(sel):
    """sel: sorted global row ids -> sub dict usable by GenRows(sub, arange(n), dev)."""
    sel = np.asarray(sel)
    zf = zipfile.ZipFile(NPZ); z = np.load(NPZ, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    sub = {k: take(zf, k, sel) for k in KEYS}
    off = z["off"]; lens = off[sel + 1] - off[sel]
    gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
    sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather)
    sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    return sub, meta
