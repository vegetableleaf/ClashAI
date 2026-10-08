"""Train TowerRefine (base frozen) on icebow-deck (deck 90) pro PLAY rows of gen_dataset_v32_fv5, TRAIN split; evaluate on VAL.
Loss = card CE (hand slot) + cell CE (lattice label of the pro's placement, teacher-forced card), per-row weight w_chip on the
pro chip-Rocket rows (pros_chip.pkl labels) and 1 elsewhere, sampled with replacement in proportion to the weights.
  python train_tower_refine.py --w-chip 1 --steps 4000 --out tr_w1.pt"""
import argparse, os, sys, pickle, json, time, math
import numpy as np, torch, torch.nn.functional as F
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import load_rows, NPZ, CK
from tower_refine import build
from pipeline.eval_gen import GenRows
from pipeline.model_v3 import cell_label
from pipeline.opp_elixir_count import card_cost
ap = argparse.ArgumentParser()
ap.add_argument("--w-chip", type=float, default=1.0); ap.add_argument("--steps", type=int, default=4000)
ap.add_argument("--bs", type=int, default=256); ap.add_argument("--lr", type=float, default=1e-3)
ap.add_argument("--base", default=CK["live"]); ap.add_argument("--out", required=True)
ap.add_argument("--no-card", action="store_true"); ap.add_argument("--no-cell", action="store_true")
ap.add_argument("--eval-only", action="store_true")
A = ap.parse_args()
torch.manual_seed(0); rng = np.random.default_rng(0)
DEV = torch.device("cuda"); T0 = time.time()
log = lambda *a: print(f"[{time.time()-T0:5.0f}s]", *a, flush=True)
z = np.load(NPZ)
sel = np.flatnonzero((z["deck_id"] == 90) & (z["y_gate"] == 1))
kind = {r["row"]: r["kind"] for r in pickle.load(open(os.path.join(HERE, "chip_rows.pkl"), "rb"))}
sub, meta = load_rows(sel); n = len(sel); log("deck-90 play rows", n)
CV = meta["card_vocab"]; RK = CV.index("rocket")
split = sub["split"]; chip = np.array([kind.get(int(i)) == "chip" for i in sel])
rows = GenRows(sub, np.arange(n), DEV)
model, st = build(A.base, DEV, card=not A.no_card, cell=not A.no_cell)
COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
hand = sub["hand_card"].astype(int); el = np.floor(sub["sc"][:, 3] * 10 + 1e-3)
aff = (hand > 0) & (COST[hand] <= el[:, None] + 1e-6)
tau = np.array([.35, .45, .55])[np.where(sub["tick"] >= 3600, 2, np.where(sub["tick"] >= 2400, 1, 0))]
c = np.arange(2304); CX, CY = (c % 36) * .5, (c // 36) * .5


def step_loss(b, w):
    o = model(b, card=b["card"], form=b["form"])
    lc = F.cross_entropy(o["card"], b["slot"], reduction="none")
    ll = F.cross_entropy(o["cell"].float(), cell_label(b["xy"], "lattice"), reduction="none")
    return ((lc + ll) * w).sum() / w.sum(), lc.mean().item(), ll.mean().item()


@torch.no_grad()
def evaluate(m):
    model.eval(); val = np.flatnonzero(split == 1); R = {"top1": [], "card_nll": [], "cell_nll": []}
    for s in range(0, len(val), 512):
        ids = val[s:s + 512]; b = rows.batch(ids); o = m(b, card=b["card"], form=b["form"])
        cl = o["card"].float().cpu().numpy(); lg = np.where(aff[ids], cl, -np.inf)
        R["top1"] += list(lg.argmax(1) == b["slot"].cpu().numpy())
        R["card_nll"] += list(F.cross_entropy(o["card"].float(), b["slot"], reduction="none").cpu().numpy())
        R["cell_nll"] += list(F.cross_entropy(o["cell"].float(), cell_label(b["xy"], "lattice"), reduction="none").cpu().numpy())
    out = {k: float(np.mean(v)) for k, v in R.items()}
    for name, msk in (("chip_val", chip & (split == 1)), ("chip_train", chip & (split == 0))):
        ids = np.flatnonzero(msk); Q = {"live_rocket": [], "rank1": [], "p_rk": [], "mass_tower": []}
        for s in range(0, len(ids), 512):
            i = ids[s:s + 512]; b = rows.batch(i); o = m(b)
            cl = o["card"].float().cpu().numpy(); gate = torch.sigmoid(o["gate"].float()).cpu().numpy()
            lg = np.where(aff[i], cl, -np.inf); P = np.exp(lg - lg.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
            isr = hand[i] == RK; top = isr[np.arange(len(i)), lg.argmax(1)]
            Q["rank1"] += list(top); Q["live_rocket"] += list(top & (gate > tau[i])); Q["p_rk"] += list((P * isr).sum(1))
            rslot = isr.argmax(1)
            pc = torch.softmax(m(b, card=torch.full((len(i),), RK, device=DEV), form=torch.as_tensor(sub["hand_form"][i, rslot], device=DEV))["cell"].float(), -1).cpu().numpy()
            ax = sub["y_xy"][i, 0] * 18; TX = np.where(ax < 9, 3.5, 14.5)
            disk = np.hypot(CX[None] - TX[:, None], CY[None] - 6.5) <= 3.0
            Q["mass_tower"] += list((pc * disk).sum(1))
        out.update({f"{name}_{k}": float(np.mean(v)) for k, v in Q.items()}); out[f"{name}_n"] = len(ids)
    return out


base_eval = evaluate(model.base); log("BASE", json.dumps({k: round(v, 4) for k, v in base_eval.items()}))
if A.eval_only: sys.exit()
tr_idx = np.flatnonzero(split == 0); wts = np.where(chip[tr_idx], A.w_chip, 1.0); p = wts / wts.sum()
opt = torch.optim.AdamW(model.tr.parameters(), lr=A.lr, weight_decay=0.01)
for it in range(1, A.steps + 1):
    ids = np.sort(rng.choice(tr_idx, A.bs, p=p))
    b = rows.batch(ids)
    loss, lc, ll = step_loss(b, torch.ones(len(ids), device=DEV))   # weighting is done by sampling
    opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.tr.parameters(), 1.0); opt.step()
    if it % 500 == 0: log(f"step {it} card {lc:.4f} cell {ll:.4f}")
res = evaluate(model); log("TOWER_REFINE", json.dumps({k: round(v, 4) for k, v in res.items()}))
torch.save({"base": A.base, "cfg": {"card": not A.no_card, "cell": not A.no_cell}, "tower_refine": model.tr.state_dict(),
            "w_chip": A.w_chip, "steps": A.steps, "eval_base": base_eval, "eval": res}, os.path.join(HERE, A.out))
log("saved", A.out)
