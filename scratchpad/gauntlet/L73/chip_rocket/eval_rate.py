"""Over-Rocketing check on VAL deck-90 PLAY rows with Rocket affordable: argmax-Rocket share and live-rule Rocket share
(gate > tau_phase AND argmax) for base / TowerRefine arms, vs the pros' actual Rocket share; by phase; plus top-1 on non-Rocket rows."""
import os, sys, numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import load_rows, NPZ, CK
import tower_refine
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
from pipeline.opp_elixir_count import card_cost
DEV = torch.device("cuda")
z = np.load(NPZ)
sel = np.flatnonzero((z["deck_id"] == 90) & (z["y_gate"] == 1) & (z["split"] == 1))
sub, meta = load_rows(sel); n = len(sel); CV = meta["card_vocab"]; RK = CV.index("rocket")
COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
hand = sub["hand_card"].astype(int); el = np.floor(sub["sc"][:, 3] * 10 + 1e-3)
aff = (hand > 0) & (COST[hand] <= el[:, None] + 1e-6); rk_aff = (aff & (hand == RK)).any(1)
ph = np.where(sub["tick"] >= 3600, 2, np.where(sub["tick"] >= 2400, 1, 0)); tau = np.array([.35, .45, .55])[ph]
pro_rk = sub["y_card"] == RK
rows = GenRows(sub, np.arange(n), DEV)
models = {"base(live)": lambda: load_model(CK["live"], DEV)[0], "tw1": lambda: tower_refine.load(os.path.join(HERE, "tr_w1.pt"), DEV)[0],
          "tw2": lambda: tower_refine.load(os.path.join(HERE, "tr_w2.pt"), DEV)[0],
          "tw4": lambda: tower_refine.load(os.path.join(HERE, "tr_w4.pt"), DEV)[0]}
for name, mk in models.items():
    m = mk(); m.eval(); top = np.zeros(n, int); gate = np.zeros(n)
    with torch.no_grad():
        for s in range(0, n, 512):
            i = np.arange(s, min(s + 512, n)); o = m(rows.batch(i))
            lg = np.where(aff[i], o["card"].float().cpu().numpy(), -np.inf); top[i] = lg.argmax(1); gate[i] = torch.sigmoid(o["gate"].float()).cpu().numpy()
    am_rk = hand[np.arange(n), top] == RK; live = am_rk & (gate > tau)
    ok = top == sub["y_hand_pos"]
    print(f"{name:11s} top1 all {ok.mean():.4f} | top1 on non-Rocket pro rows {ok[~pro_rk].mean():.4f} | Rocket-affordable rows n={rk_aff.sum()}: "
          f"pros Rocket {pro_rk[rk_aff].mean():.3f}, argmax Rocket {am_rk[rk_aff].mean():.3f}, live-rule Rocket {live[rk_aff].mean():.3f} | "
          + " ".join(f"{p}: pros {pro_rk[rk_aff & (ph == k)].mean():.3f} argmax {am_rk[rk_aff & (ph == k)].mean():.3f}" for k, p in enumerate(("1x", "2x", "OT")))
          + f" | argmax-Rocket precision (pro played Rocket) {pro_rk[am_rk & rk_aff].mean():.3f}", flush=True)
