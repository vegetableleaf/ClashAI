"""What decides the pros' centre column (X 8.5 vs 9.5)? VAL play rows of gen_dataset_v32_fv5 whose pro label is a
non-spell card on X 8.5 / 9.5 in the own half (Y < 15). Model frame, tiles: X = cx / 2, Y = 32 - cy / 2.
    python slices.py OUT.json CKPT [CKPT ...]
Per slice: n, P(pro picks 8.5), P(pro on the nearest enemy body's side | that enemy |eX - 9| >= 1), and per ckpt the
BINARY agreement: on the pro's row, does logit(8.5) vs logit(9.5) pick the pro's column (teacher-forced card).
Threat = nearest enemy body (side_enemy, not a spell) to the pro's cell. Building-targeters / air from the vocab keys."""
import collections, json, sys
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline import vocab
from pipeline.dataset import load
from pipeline.model_gen import load_model
from pipeline.model_v3 import cell_label
from pipeline.train_gen import GenRows

DATA = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
SPELL = {"the-log", "tornado", "rocket", "fireball", "arrows", "zap", "goblin-barrel", "poison", "earthquake", "freeze",
         "lightning", "giant-snowball", "barbarian-barrel", "royal-delivery", "graveyard", "rage", "clone", "void", "vines"}
BT = {"hog_rider", "giant", "golem", "golemite", "royal_giant", "ram_rider", "battle_ram", "balloon", "elixir_golem",
      "goblin_giant", "electro_giant", "lava_hound", "wall_breakers", "royal_hogs", "rune_giant", "goblin_demolisher",
      "mother_witch_hog", "elixir_golemite", "goblin_drill", "skeleton_barrel"}
AIR = {"balloon", "bats", "baby_dragon", "electro_dragon", "flying_machine", "inferno_dragon", "lava_hound", "lava_pups",
       "mega_minion", "minions", "minion_horde", "phoenix", "skeleton_dragons", "spirit_empress_air", "skeleton_barrel"}
BUILDING = {"tesla", "x-bow", "cannon", "inferno-tower", "bomb-tower", "tombstone", "goblin-cage", "furnace", "mortar",
            "barbarian-hut", "goblin-hut", "elixir-collector", "goblin-drill"}
UV = list(vocab.UNIT_VOCAB)


def ukey(c):
    k = UV[int(c)] if 0 <= int(c) < len(UV) else "?"
    for suf in ("_evo", "_hero", "_ability"):
        k = k.removesuffix(suf)
    return k


out_path, ckpts = sys.argv[1], sys.argv[2:]
arrs, meta = load(DATA)
voc = meta["card_vocab"]
play = (arrs["y_gate"] == 1) & (arrs["split"] == 1)
LC = cell_label(torch.from_numpy(arrs["y_xy"].astype(np.float32)), "lattice").numpy()
cx, cy = LC % 36, LC // 36
sel = np.where(play & np.isin(cx, (17, 19)) & (32 - cy / 2 < 15) & ~np.isin(arrs["y_card"], [voc.index(s) for s in SPELL if s in voc]))[0]
tok, off, sc, past = arrs["tok"], arrs["off"], arrs["sc"], arrs["past"]
feat = []
for r in sel:
    X, Y = cx[r] / 2, 32 - cy[r] / 2
    t = tok[off[r]:off[r + 1]]
    en = t[(t[:, 2] == 1) & (t[:, 13] == 0)]
    f = {"card": voc[arrs["y_card"][r]], "X": X, "Y": Y}
    c = f["card"]
    f["card_grp"] = c if c in ("tesla", "x-bow", "knight", "ice-wizard", "skeletons") else ("other building" if c in BUILDING else "other troop")
    if len(en):
        ex, ey = en[:, 4] * 18, (1 - en[:, 5]) * 32
        j = int(np.argmin(np.hypot(ex - X, ey - Y)))
        k = ukey(en[j, 0])
        f.update(eX=float(ex[j]), eY=float(ey[j]), threat=("building-targeter" if k in BT else "air" if k in AIR else "troop"),
                 threat_key=k, dist=float(np.hypot(ex[j] - X, ey[j] - Y)), n_enemy=int(len(en)))
    # my towers: hp 52..54 (K, L, R), alive 64..66
    hpL, hpR, aL, aR, hpK = sc[r, 53], sc[r, 54], sc[r, 65], sc[r, 66], sc[r, 52]
    f["princess"] = ("L down" if aL < 0.5 else "R down" if aR < 0.5 else "L lower" if hpL < hpR - 0.02 else
                     "R lower" if hpR < hpL - 0.02 else "equal")
    f["king_active_proxy"] = bool(hpK < 0.999 or aL < 0.5 or aR < 0.5)
    p0 = past[r, 0]
    if p0[0] > 0:
        px = round(float(p0[2]) * 36) / 2
        f["prev_col"] = "8.5" if px == 8.5 else "9.5" if px == 9.5 else "left (<8.5)" if px < 8.5 else "right (>9.5)"
        f["prev_dt"] = float(p0[4])
    else:
        f["prev_col"] = "none"
    feat.append(f)

# model binary choice on the pro's row
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
rows = GenRows(arrs, sel, dev)
agree = {}
for ck in ckpts:
    model, st = load_model(ck, dev); model.eval()
    res = []
    with torch.no_grad():
        for s in range(0, len(sel), 512):
            ids = sel[s:s + 512]
            b = rows.batch(ids)
            lg = model(b, card=b["card"], form=b["form"])["cell"].float()
            row = torch.from_numpy(cy[ids]).to(dev) * 36
            pick85 = lg.gather(1, (row + 17)[:, None])[:, 0] > lg.gather(1, (row + 19)[:, None])[:, 0]
            res.append(pick85.cpu().numpy())
    agree[Path(ck).stem] = np.concatenate(res)
names = list(agree)


def stat(idx):
    idx = np.asarray(idx, int)
    if not len(idx):
        return None
    pro85 = np.array([feat[i]["X"] == 8.5 for i in idx])
    lane = [i for i in idx if "eX" in feat[i] and abs(feat[i]["eX"] - 9) >= 1]
    es = [(feat[i]["X"] - 9) * (feat[i]["eX"] - 9) > 0 for i in lane]
    d = {"n": int(len(idx)), "P_pro_8.5": round(float(pro85.mean()), 3), "n_lane": len(lane),
         "P_enemy_side": round(float(np.mean(es)), 3) if es else None}
    for nm in names:
        d[f"agree_{nm}"] = round(float((agree[nm][idx] == pro85).mean()), 3)
        if es:
            m_es = [((8.5 if agree[nm][i] else 9.5) - 9) * (feat[i]["eX"] - 9) > 0 for i in lane]
            d[f"enemy_side_{nm}"] = round(float(np.mean(m_es)), 3)
    return d


def by(key, idx=None, fn=None):
    g = collections.defaultdict(list)
    for i in (range(len(feat)) if idx is None else idx):
        v = fn(feat[i]) if fn else feat[i].get(key, "n/a")
        g[v].append(i)
    return {str(k): stat(v) for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])) if len(v) >= 30}


lanef = lambda f: ("no enemy" if "eX" not in f else "centre (|eX-9|<1)" if abs(f["eX"] - 9) < 1 else
                   "left lane" if f["eX"] < 9 else "right lane")
distf = lambda f: "no enemy" if "eX" not in f else ("<3" if f["dist"] < 3 else "3-6" if f["dist"] < 6 else "6-10" if f["dist"] < 10 else ">=10")
eyf = lambda f: "no enemy" if "eX" not in f else ("own half (eY<15)" if f["eY"] < 15 else "bridge (15-18)" if f["eY"] < 18 else "enemy half")
pull = [i for i, f in enumerate(feat) if f["card"] in ("tesla", "x-bow") and f.get("threat") == "building-targeter"]
res = {"n_rows": len(feat), "ckpts": ckpts, "ALL": stat(range(len(feat))),
       "card": by("card_grp"), "threat": by("threat"), "threat_lane": by(None, fn=lanef), "threat_dist": by(None, fn=distf),
       "threat_y": by(None, fn=eyf), "princess": by("princess"), "king_active_proxy": by("king_active_proxy"),
       "prev_own_col": by("prev_col"),
       "PULL tesla/x-bow vs building-targeter": stat(pull),
       "PULL by threat lane": by(None, pull, lanef), "PULL by princess": by("princess", pull),
       "card x threat": by(None, fn=lambda f: f"{f['card_grp']} | {f.get('threat', 'no enemy')}"),
       "knight/icewiz x threat_lane": by(None, [i for i, f in enumerate(feat) if f["card"] in ("knight", "ice-wizard")], lanef),
       "threat_key (top)": by("threat_key")}
Path(out_path).write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ("n_rows", "ALL", "PULL tesla/x-bow vs building-targeter")}, indent=1))
