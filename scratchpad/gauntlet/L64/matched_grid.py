"""L64c: score a NEW S1 checkpoint and the OLD init on the SAME val plays at matched grids.
Old-model predictions come from rescore_old_preds.npz (L64 subagent; old init through its own encoder, 432 grid,
deployable-masked). The new model's argmax half-tile cell (36x64) is turned into a board-frame xy and (i) binned to
1-tile 18x32 tiles, (ii) snapped to the nearest 432-cell centre. Rows are joined on (tag, side, tick).
Usage: matched_grid.py <deck> <ckpt.pt> [--preds rescore_old_preds.npz] -> prints one json line."""
import argparse, json, sys
from pathlib import Path
import numpy as np, torch
REPO = Path("C:/Users/benpe/ClashBot"); sys.path.insert(0, str(REPO))
from pipeline.dataset import load as load_ds
from pipeline.model_v3 import S1Model, GRID_X, GRID_Y, hand_mask_from_sc
from pipeline.obs_contract import load_deck
from pipeline.train_s1 import Rows

ap = argparse.ArgumentParser(); ap.add_argument("deck"); ap.add_argument("ckpt"); ap.add_argument("--preds", default=str(REPO / "scratchpad/gauntlet/L64/rescore_old_preds.npz"))
a = ap.parse_args()
deck = load_deck(a.deck); arrs, meta = load_ds(deck.data_dir / "pipeline" / "s1_dataset.npz")
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ck = torch.load(a.ckpt, map_location=dev); args = ck.get("args", {})
model = S1Model(d=args.get("d", 128), layers=args.get("layers", 4)).to(dev); model.load_state_dict(ck["model"]); model.eval()
va = np.where((arrs["split"] == 1) & (arrs["y_gate"] == 1))[0]
rows = Rows(arrs, va, dev)
pred_xy, pro_xy = [], []
with torch.no_grad():
    for s in range(0, len(va), 512):
        ids = va[s:s + 512]; b = rows.batch(ids)
        out = model(b["tok"], b["mask"], b["sc"], b["past"], card_slot=b["slot"], hand_mask=hand_mask_from_sc(b["sc"]))
        c = out["cell"].argmax(-1)
        pred_xy.append(torch.stack([(c % GRID_X + 0.5) / GRID_X, (c // GRID_X + 0.5) / GRID_Y], -1).cpu().numpy())
        pro_xy.append(b["xy"].cpu().numpy())
pred_xy, pro_xy = np.concatenate(pred_xy), np.concatenate(pro_xy)
tags = np.asarray(arrs["tags"])[arrs["rep"][va]]
key_new = {(str(t), int(sd), int(tk)): i for i, (t, sd, tk) in enumerate(zip(tags, arrs["side"][va], arrs["tick"][va]))}
z = np.load(a.preds)
key_old = [(str(t), int(sd), int(tk)) for t, sd, tk in zip(z["tag"], z["side"], z["tick"])]
j = np.array([key_new.get(k, -1) for k in key_old]); ok = j >= 0
print(json.dumps({"n_new_val_play": int(len(va)), "n_old": int(len(key_old)), "joined": int(ok.sum())}))
jn = j[ok]; C = z["cell432_centers"]
def tile(xy): return np.floor(xy[:, 0] * 18).astype(int) + 18 * np.floor(xy[:, 1] * 32).astype(int)
def cell432(xy): return np.argmin(((xy[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
pn, pp = pred_xy[jn], pro_xy[jn]
assert np.abs(pp - z["pro_frame_xy"][ok]).max() < 1e-3, "pro xy disagree between builders"
new_tile = tile(pn) == tile(pp); new_432 = cell432(pn) == z["pro_cell432"][ok]
old_tile = z["tile18x32_pred"][ok] == z["tile18x32_pro"][ok]; old_432 = z["hit1"][ok] == 1
clean = z["in_old_train"][ok] == 0
d_new = np.sqrt((((pn - pp) * [18, 32]) ** 2).sum(-1)); d_old = np.sqrt((((z["argmax_frame_xy"][ok] - pp) * [18, 32]) ** 2).sum(-1))
r = {"ckpt": a.ckpt, "n": int(ok.sum()), "n_clean": int(clean.sum()),
     "new_tile_top1": float(new_tile.mean()), "old_tile_top1": float(old_tile.mean()),
     "new_432_top1": float(new_432.mean()), "old_432_top1": float(old_432.mean()),
     "clean_new_tile": float(new_tile[clean].mean()), "clean_old_tile": float(old_tile[clean].mean()),
     "clean_new_432": float(new_432[clean].mean()), "clean_old_432": float(old_432[clean].mean()),
     "new_dist_tiles_mean": float(d_new.mean()), "new_dist_median": float(np.median(d_new)), "new_within1": float((d_new <= 1).mean()), "new_within2": float((d_new <= 2).mean()),
     "old_dist_tiles_mean": float(d_old.mean()), "old_dist_median": float(np.median(d_old)), "old_within1": float((d_old <= 1).mean()), "old_within2": float((d_old <= 2).mean())}
print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}))
