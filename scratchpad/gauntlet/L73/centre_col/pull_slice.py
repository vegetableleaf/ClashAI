"""Building PULL slice + CPU bit-check of the non-cell heads.
    python pull_slice.py OUT.json BASE CKPT [CKPT ...]
(1) VAL play rows: pro card Tesla / X-Bow, own half (Y < 15), pro X in [7, 11], nearest enemy body a building-targeter
in a lane (|eX - 9| >= 1). Pro offset direction (toward the threat's lane / centre X 9 / away); per ckpt the argmax
over the pro's ROW restricted to X 7..11, its direction, and exact-X agreement with the pro.
(2) 2,000 val rows on CPU: gate / card / wait / value of every ckpt torch.equal to BASE's (the module must not touch
them); max |diff| reported."""
import collections, json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.dataset import load
from pipeline.model_gen import load_model
from pipeline.model_v3 import cell_label
from pipeline.train_gen import GenRows

DATA = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
BT = {"hog_rider", "giant", "golem", "golemite", "royal_giant", "ram_rider", "battle_ram", "balloon", "elixir_golem",
      "goblin_giant", "electro_giant", "lava_hound", "wall_breakers", "royal_hogs", "rune_giant", "goblin_demolisher",
      "mother_witch_hog", "elixir_golemite", "goblin_drill", "skeleton_barrel"}
from pipeline import vocab
UV = list(vocab.UNIT_VOCAB)
ukey = lambda c: UV[int(c)].removesuffix("_evo").removesuffix("_hero") if 0 <= int(c) < len(UV) else "?"
out_path, ckpts = sys.argv[1], sys.argv[2:]
arrs, meta = load(DATA)
voc = meta["card_vocab"]
LC = cell_label(torch.from_numpy(arrs["y_xy"].astype(np.float32)), "lattice").numpy()
cx, cy = LC % 36, LC // 36
cand = np.where((arrs["y_gate"] == 1) & (arrs["split"] == 1) & np.isin(arrs["y_card"], [voc.index("tesla"), voc.index("x-bow")])
                & (cx >= 14) & (cx <= 22) & (32 - cy / 2 < 15))[0]
tok, off = arrs["tok"], arrs["off"]
sel, info = [], []
for r in cand:
    X, Y = cx[r] / 2, 32 - cy[r] / 2
    t = tok[off[r]:off[r + 1]]
    en = t[(t[:, 2] == 1) & (t[:, 13] == 0)]
    if not len(en):
        continue
    ex, ey = en[:, 4] * 18, (1 - en[:, 5]) * 32
    j = int(np.argmin(np.hypot(ex - X, ey - Y)))
    if ukey(en[j, 0]) in BT and abs(ex[j] - 9) >= 1:
        sel.append(r); info.append((voc[arrs["y_card"][r]], X, float(ex[j])))
sel = np.array(sel)
direc = lambda X, eX: "toward" if (X - 9) * (eX - 9) > 0 else "centre9" if X == 9 else "away"
res = {"n": len(sel), "pro": dict(collections.Counter(direc(X, e) for _, X, e in info)),
       "pro_by_card": {c: dict(collections.Counter(direc(X, e) for cc, X, e in info if cc == c)) for c in ("tesla", "x-bow")}}
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
rows = GenRows(arrs, sel, dev)
for ck in ckpts:
    model, _ = load_model(ck, dev); model.eval()
    with torch.no_grad():
        b = rows.batch(sel)
        lg = model(b, card=b["card"], form=b["form"])["cell"].float().cpu().numpy()
    picks = [int(np.argmax(lg[k, cy[r] * 36 + 14: cy[r] * 36 + 23])) + 14 for k, r in enumerate(sel)]
    res[Path(ck).stem] = {"dir": dict(collections.Counter(direc(p / 2, e) for p, (_, X, e) in zip(picks, info))),
                          "exact_X": float(np.mean([p / 2 == X for p, (_, X, e) in zip(picks, info)]))}
# CPU bit-check
cpu = torch.device("cpu")
va = np.sort(np.random.default_rng(0).choice(np.where(arrs["split"] == 1)[0], 2000, replace=False))
vr = GenRows(arrs, va, cpu)
outs = {}
for ck in ckpts:
    model, _ = load_model(ck, cpu); model.eval()
    with torch.no_grad():
        acc = collections.defaultdict(list)
        for s in range(0, len(va), 250):
            b = vr.batch(va[s:s + 250])
            o = model(b, card=b["card"], form=b["form"])
            for k in ("gate", "card", "wait", "value", "cell"):
                acc[k].append(o[k])
    outs[ck] = {k: torch.cat(v) for k, v in acc.items()}
base = outs[ckpts[0]]
res["cpu_bitcheck_vs_base"] = {Path(ck).stem: {k: {"equal": bool(torch.equal(outs[ck][k], base[k])),
                                                   "max_abs": float(torch.nan_to_num(outs[ck][k] - base[k], 0, 0, 0).abs().max())}
                                               for k in base} for ck in ckpts[1:]}
Path(out_path).write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
