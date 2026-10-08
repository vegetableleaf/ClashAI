"""W4 step 1: run a checkpoint's gate over every icebow-deck (deck 90) row of gen_dataset_v32_fv5 and save per-row
context (tick, elixir, board emptiness, time since my / the opponent's last play) with p_gate.
  python extract.py --ckpt live --out rows_live.npz"""
import argparse, os, sys, time
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.abspath(os.path.join(HERE, "../../../..")))
from common import load_rows, CK, NPZ
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model

ap = argparse.ArgumentParser(); ap.add_argument("--ckpt", default="live"); ap.add_argument("--out", required=True)
ap.add_argument("--cache", default=os.path.join(HERE, "deck90.npz"))
A = ap.parse_args()
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
T0 = time.time()
if os.path.exists(A.cache):
    z = np.load(A.cache, allow_pickle=True); sub = {k: z[k] for k in z.files if k != "sel"}; sel = z["sel"]
else:
    d = np.load(NPZ)["deck_id"]; sel = np.flatnonzero(d == 90)
    sub, _ = load_rows(sel)
    np.savez(A.cache, sel=sel, **sub)
print("loaded", len(sel), round(time.time() - T0), "s", flush=True)
model, st = load_model(CK.get(A.ckpt, A.ckpt), dev); model.eval()
rows = GenRows(sub, np.arange(len(sel)), dev)
Z = np.empty(len(sel), np.float32)
with torch.no_grad():
    torch.set_num_threads(int(os.environ.get("W4_THREADS", "8")))
    for s in range(0, len(sel), 1024):
        ids = np.arange(s, min(s + 1024, len(sel)))
        Z[ids] = model(rows.batch(ids))["gate"].float().cpu().numpy()
tok, off = sub["tok"], sub["off"]
enemy = (tok[:, 2] == 1) & (tok[:, 13] == 0); mine = (tok[:, 1] == 1) & (tok[:, 13] == 0)
ce, cm = np.concatenate([[0], np.cumsum(enemy)]), np.concatenate([[0], np.cumsum(mine)])
n_en, n_my = ce[off[1:]] - ce[off[:-1]], cm[off[1:]] - cm[off[:-1]]
np.savez(A.out, z=Z, gate=sub["y_gate"], tick=sub["tick"], el=sub["sc"][:, 3] * 10, n_en=n_en, n_my=n_my,
         my_dt=sub["past"][:, 0, 4], opp_dt=sub["opp_past"][:, 0, 4], rep=sub["rep"], side=sub["side"],
         split=sub["split"], wait_dt=sub["y_wait_dt"], sel=sel, ckpt=str(CK.get(A.ckpt, A.ckpt)))
print("done", round(time.time() - T0), "s", flush=True)
