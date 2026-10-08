"""Does the fv6 barrel branch move NON-barrel Rocket / Log aims? VAL play rows of gen_dataset_v32_fv5 whose pro card is
the Log or Rocket, split by whether an enemy Goblin Barrel is in flight. Per ckpt: argmax cell (teacher-forced card),
exact agreement with the pro, mean distance to the pro in tiles; per pair: share of rows whose argmax changed.
    python nonbarrel_aims.py OUT.json NAME=CKPT [NAME=CKPT ...]"""
import json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
from pipeline.model_v3 import cell_label
from pipeline.train_rocket_curriculum import load_subset

DATA = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
out_path, specs = sys.argv[1], dict(a.split("=", 1) for a in sys.argv[2:])
with np.load(DATA) as z:
    cv = json.loads(str(z["meta"]))["card_vocab"]
    ids = np.flatnonzero((z["y_gate"] == 1) & (z["split"] == 1) & np.isin(z["y_card"], [cv.index("the-log"), cv.index("rocket")]))
sub, _ = load_subset(DATA, ids)
GB = cv.index("goblin-barrel")
barrel = ((sub["projectiles"][:, :, 0] == GB) & (sub["projectiles"][:, :, 1] == 1)).any(1)
card = np.where(sub["y_card"] == cv.index("rocket"), "rocket", "log")
lab = cell_label(torch.from_numpy(sub["y_xy"].astype(np.float32)), "lattice").numpy()
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
rows = GenRows(sub, np.arange(len(ids)), dev)
pred = {}
for name, ck in specs.items():
    model, _ = load_model(ck, dev); model.eval()
    p = []
    with torch.no_grad():
        for s in range(0, len(ids), 512):
            b = rows.batch(np.arange(s, min(s + 512, len(ids))))
            p.append(model(b, card=b["card"], form=b["form"])["cell"].argmax(-1).cpu().numpy())
    pred[name] = np.concatenate(p)
dist = lambda a, b: np.hypot((a % 36 - b % 36) / 2, (a // 36 - b // 36) / 2)
res, names = {}, list(specs)
for c in ("log", "rocket"):
    for has in (False, True):
        m = (card == c) & (barrel == has)
        key = f"{c} | barrel in flight={has}"
        res[key] = {"n": int(m.sum()), **{f"{n}: exact": round(float((pred[n][m] == lab[m]).mean()), 4) for n in names},
                    **{f"{n}: mean dist tiles": round(float(dist(pred[n][m], lab[m]).mean()), 3) for n in names},
                    **{f"changed {a}->{b}": round(float((pred[a][m] != pred[b][m]).mean()), 4) for a, b in zip(names, names[1:])},
                    **{f"changed >1 tile {a}->{b}": round(float((dist(pred[a][m], pred[b][m]) > 1).mean()), 4) for a, b in zip(names, names[1:])}}
Path(out_path).write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
