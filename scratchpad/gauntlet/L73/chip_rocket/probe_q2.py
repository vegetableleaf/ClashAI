"""Q2 matched-state probe: on pro tower-Rocket rows (chip and catch; Rocket affordable), what do the models do under the live rule,
and how much does inserting ONE enemy troop near the targeted princess tower move P(Rocket)? Public inputs only.
Live rule: play iff sigmoid(gate) > tau_phase (.35/.45/.55 by 1x/2x/OT), card = argmax affordable logit, cell = argmax.
Token frame = board frame normalized (x/18, y/32; enemy towers at y 3.0 / 6.5 tiles), same as y_xy and the lattice cells."""
import pickle, os, sys, json, collections, math
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import *
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
from pipeline.opp_elixir_count import card_cost
from pipeline.decision_options import xbow_offensive_cells
from pipeline import vocab
torch.set_num_threads(2)
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
models = sys.argv[1].split(",") if len(sys.argv) > 1 else list(CK)
extra = dict(a.split("=", 1) for a in sys.argv[2:])          # name=path for extra checkpoints (Q5 prototype)
CK.update(extra)
rows = pickle.load(open(os.path.join(HERE, "chip_rows.pkl"), "rb"))
rows = [r for r in rows if r["kind"] in ("chip", "catch")]
rows.sort(key=lambda r: r["row"])
sel = np.array([r["row"] for r in rows])
sub, meta = load_rows(sel); n = len(sel)
CV = meta["card_vocab"]; RK, XB = CV.index("rocket"), CV.index("x-bow")
COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
hand = sub["hand_card"].astype(int); el = np.floor(sub["sc"][:, 3] * 10 + 1e-3)
aff = (hand > 0) & (COST[hand] <= el[:, None] + 1e-6)
ok = (aff & (hand == RK)).any(1)
print("rows", n, "Rocket affordable", ok.sum(), flush=True)
TICK = sub["tick"]; PH = np.where(TICK >= 3600, 2, np.where(TICK >= 2400, 1, 0)); TAU = np.array([.35, .45, .55])[PH]
# targeted tower = enemy princess nearest the pro's aim (board tiles)
ax, ay = sub["y_xy"][:, 0] * 18, sub["y_xy"][:, 1] * 32
TX = np.where(ax < 9, 3.5, 14.5); TY = np.full(n, 6.5)
c = np.arange(2304); CXc, CYc = (c % 36) * .5, (c // 36) * .5
OFFC = xbow_offensive_cells((True, True, True), "lattice")
# sanity: enemy token distance to the aim point, chip vs catch
for kind in ("chip", "catch"):
    ds = []
    for i, r in enumerate(rows):
        if r["kind"] != kind: continue
        t = sub["tok"][sub["off"][i]:sub["off"][i + 1]]; e = t[t[:, 2] == 1]
        ds.append(min([math.hypot(x * 18 - ax[i], y * 32 - ay[i]) for x, y in e[:, 4:6]] + [99]))
    print("sanity", kind, "median min enemy-token distance to aim (tiles)", np.median(ds), "share <=3:", np.mean(np.array(ds) <= 3), flush=True)
WIZ, MUSK = vocab.unit_id("wizard"), vocab.unit_id("musketeer")
VAR = {"control": None,
       "wizard_behind_tower": (WIZ, lambda i: (TX[i], 4.8)),
       "musketeer_behind_tower": (MUSK, lambda i: (TX[i], 4.8)),
       "wizard_inner_side": (WIZ, lambda i: (TX[i] + (2.0 if TX[i] < 9 else -2.0), 6.5)),
       "wizard_behind_king": (WIZ, lambda i: (9.0, 1.0)),
       # identity-free token (cls embedding zeroed by a hook): an enemy object at the tower centre vs 5 tiles in front of it
       "null_at_tower": (-1, lambda i: (TX[i], TY[i])),
       "null_5t_front": (-1, lambda i: (TX[i], TY[i] + 5.0))}
import os as _os
if _os.environ.get("VARS"): VAR = {k: VAR[k] for k in _os.environ["VARS"].split(",")}
ZERO = []          # (row-in-batch, slot) whose cls embedding is zeroed


def _hook(mod, inp, out):
    if not ZERO: return out
    out = out.clone()
    for k, j in ZERO: out[k, j] = 0
    return out


def insert(b, ids, var):
    ZERO.clear()
    if VAR[var] is None: return b
    b = dict(b); tok = b["tok"].clone(); mask = b["mask"].clone(); uf = b["unit_form"].clone()
    cid, pos = VAR[var]
    for k, i in enumerate(ids):
        free = (~mask[k]).nonzero()
        j = int(free[0]) if len(free) else tok.shape[1] - 1
        x, y = pos(i)
        if cid < 0: ZERO.append((k, j))
        tok[k, j] = torch.tensor([max(cid, 0), 0, 1, 0, x / 18, y / 32, 1, 1, 0, 0, 0, 0, 1, 0], dtype=tok.dtype)
        mask[k, j] = True; uf[k, j] = 0
    b.update(tok=tok, mask=mask, unit_form=uf)
    return b


res = {}
g = GenRows(sub, np.arange(n), DEV)
for mn in models:
    if "tr_" in os.path.basename(CK[mn]):
        import tower_refine; model, st = tower_refine.load(CK[mn], DEV)
    else:
        model, st = load_model(CK[mn], DEV)
    model.eval()
    model.cls_emb.register_forward_hook(_hook)
    assert list(st["card_vocab"]) == list(CV) if "card_vocab" in st else True
    out = {}
    for var in VAR:
        R = collections.defaultdict(list)
        for s in range(0, n, 128):
            ids = np.arange(s, min(s + 128, n)); b = insert(g.batch(ids), ids, var)
            with torch.no_grad():
                o = model(b)
                gate = torch.sigmoid(o["gate"].float()).cpu().numpy(); cl = o["card"].float().cpu().numpy()
                rslot = (hand[ids] == RK).argmax(1)
                form = torch.as_tensor(sub["hand_form"][ids, rslot], device=DEV)
                pc = torch.softmax(model(b, card=torch.full((len(ids),), RK, device=DEV), form=form)["cell"].float(), -1).cpu().numpy()
                xs = (hand[ids] == XB).argmax(1); has_x = (hand[ids] == XB).any(1)
                px = torch.softmax(model(b, card=torch.full((len(ids),), XB, device=DEV), form=torch.as_tensor(sub["hand_form"][ids, xs], device=DEV))["cell"].float(), -1).cpu().numpy()
            for k, i in enumerate(ids):
                lg = np.where(aff[i], cl[k], -np.inf); P = np.exp(lg - lg.max()); P /= P.sum()
                pr = float(P[hand[i] == RK].sum()); am = int(lg.argmax()); top = CV[hand[i][am]]
                rl = lg[hand[i] == RK].max(); rank = 1 + int((lg > rl).sum())
                disk = np.hypot(CXc - TX[i], CYc - TY[i]) <= 3.0
                R["gate"].append(float(gate[k])); R["p_rocket"].append(pr); R["rank"].append(rank); R["top"].append(top)
                R["play"].append(bool(gate[k] > TAU[i])); R["live_rocket"].append(bool(gate[k] > TAU[i] and top == "rocket"))
                R["rocket_cell_on_tower"].append(float(pc[k][disk].sum())); R["rocket_argmax_on_tower"].append(bool(disk[pc[k].argmax()]))
                R["p_rocket_tower"].append(float(gate[k]) * pr * float(pc[k][disk].sum()))
                R["xbow_top_offensive"].append(bool(top == "x-bow" and OFFC[px[k].argmax()]) if has_x[k] else False)
        out[var] = {k: v for k, v in R.items()}
        print(mn, var, "done", flush=True)
    res[mn] = out
pickle.dump(dict(rows=rows, ok=ok, ph=PH, res=res), open(os.path.join(HERE, f"q2_{'_'.join(models)}{_os.environ.get('TAG','')}.pkl"), "wb"))
