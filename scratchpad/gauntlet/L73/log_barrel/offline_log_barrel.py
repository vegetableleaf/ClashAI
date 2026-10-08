"""W3 offline: pro Log rows with an enemy Goblin Barrel in flight (visible target) in gen_dataset_v32_fv5,
teacher-forced on the pro's card. Plain argmax vs log_aim=log_barrel (pipeline.decision_options.choose_cells, the
SIM/live function) vs the pro's own placement (lattice label).
    python offline_log_barrel.py OUT.json CKPT
Board frame tiles (me at the bottom; my Log rolls toward decreasing y). "covers (q4)" = q4.py log_hits:
|dx| <= 2.5 and -1 <= log_y - landing_y <= 10.1; "covers (catalog)" = the option's own corridor (1.95, -0.6..10.1).
Lane = x < 9 vs x >= 9 tiles, same as the pro's."""
import json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.dataset import load
from pipeline.model_gen import load_model
from pipeline.model_v3 import cell_label
from pipeline.train_gen import GenRows
from pipeline.decision_options import DecisionOptions, barrel_landings, choose_cells, cell_centres_tiles, rolling_corridor

DATA = "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
out_path, ckpt = sys.argv[1], sys.argv[2]
torch.set_num_threads(int(__import__('os').environ.get('THREADS', '8')))
arrs, meta = load(DATA)
voc = meta["card_vocab"]
gb, log = voc.index("goblin-barrel"), voc.index("the-log")
proj = arrs["projectiles"]
play = (arrs["y_gate"] == 1) & (arrs["y_card"] == log)
cand = np.where(play)[0]
inflight = [r for r in cand if barrel_landings(proj[r], gb)]
ids = np.array(inflight)
print(f"pro Log play rows {len(cand)}, with an enemy barrel in flight (target visible) {len(ids)}", flush=True)
dev = torch.device("cpu")
model, st = load_model(ckpt, dev); model.eval()
grid = str(st["args"].get("grid", "lattice"))
rows = GenRows(arrs, ids, dev)
X, Y = cell_centres_tiles(grid)
corr = rolling_corridor("Log")
on = DecisionOptions(log_aim="log_barrel")
pro = cell_label(torch.from_numpy(arrs["y_xy"][ids].astype(np.float32)), grid).numpy()
plain, aimed, lands = [], [], []
with torch.no_grad():
    for s in range(0, len(ids), 256):
        chunk = ids[s:s + 256]
        b = rows.batch(chunk)
        lg = model(b, card=b["card"], form=b["form"])["cell"].float()
        bl = [barrel_landings(proj[r], gb) for r in chunk]
        plain.append(lg.argmax(-1).numpy())
        aimed.append(choose_cells(lg, ["Log"] * len(chunk), on, grid=grid, barrels=bl).numpy())
        lands += bl
plain, aimed = np.concatenate(plain), np.concatenate(aimed)


def cov(cell, L, q4):
    for bx, by in L:
        dx, ahead = abs(X[cell] - bx * 18), Y[cell] - by * 32
        if (dx <= 2.5 and -1 <= ahead <= 10.1) if q4 else (dx <= corr[0] and -corr[1] <= ahead <= corr[2]):
            return True
    return False


def wilson(k, n, z=1.96):
    if not n: return [None] * 3
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** .5 / d
    return [round(p, 4), round(c - h, 4), round(c + h, 4)]


res = {"ckpt": ckpt, "grid": grid, "n_pro_log_rows": int(len(cand)), "n_inflight": int(len(ids))}
split = arrs["split"][ids]
for name, mask in (("all", np.ones(len(ids), bool)), ("val", split == 1), ("train", split != 1)):
    n = int(mask.sum()); out = {"n": n}
    for m, cells in (("pro", pro), ("plain", plain), ("log_barrel", aimed)):
        c = cells[mask]; L = [lands[i] for i in np.flatnonzero(mask)]; P = pro[mask]
        dist = np.hypot(X[c] - X[P], Y[c] - Y[P])
        out[m] = {"covers_q4": wilson(sum(cov(x, l, True) for x, l in zip(c, L)), n),
                  "covers_catalog": wilson(sum(cov(x, l, False) for x, l in zip(c, L)), n),
                  "lane_agree_pro": wilson(int(((X[c] < 9) == (X[P] < 9)).sum()), n),
                  "exact_pro": wilson(int((c == P).sum()), n),
                  "within_1_tile_pro": wilson(int((dist <= 1.0).sum()), n),
                  "median_dist_to_pro_tiles": float(np.median(dist)) if n else None}
    out["changed_vs_plain"] = wilson(int((aimed[mask] != plain[mask]).sum()), n)
    res[name] = out
print(json.dumps(res, indent=1))
Path(out_path).write_text(json.dumps(res, indent=1))
