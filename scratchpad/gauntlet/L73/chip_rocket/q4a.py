"""Q4a: in the imitation data (gen_v32_fv5, icebow deck 90 PLAY rows with Rocket affordable), what did pros play? chip / catch / other Rocket vs X-Bow."""
import numpy as np, pickle, os, sys, zipfile, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import NPZ, take
from pipeline.opp_elixir_count import card_cost
import json
z = np.load(NPZ); meta = json.loads(str(z["meta"])); CV = meta["card_vocab"]
sel = np.flatnonzero((z["deck_id"] == 90) & (z["y_gate"] == 1))
zf = zipfile.ZipFile(NPZ)
hand = take(zf, "hand_card", sel).astype(int); el = np.floor(take(zf, "sc", sel)[:, 3] * 10 + 1e-3)
yc = z["y_card"][sel]; tick = z["tick"][sel]
COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
RK, XB = CV.index("rocket"), CV.index("x-bow")
aff = ((hand == RK) & (COST[hand] <= el[:, None])).any(1)
kinds = {r["row"]: r["kind"] for r in pickle.load(open(os.path.join(HERE, "chip_rows.pkl"), "rb"))}
lab = np.array([kinds.get(int(i), "rocket?") if c == RK else ("x-bow" if c == XB else "other") for i, c in zip(sel, yc)])
ph = np.where(tick >= 3600, "OT", np.where(tick >= 2400, "2x", "1x"))
for p in ("all", "1x", "2x", "OT"):
    m = aff & ((ph == p) if p != "all" else True)
    c = collections.Counter(lab[m].tolist()); n = m.sum()
    xb_aff = ((hand == XB) & (COST[hand] <= el[:, None])).any(1)
    print(f"{p:3s} play rows with Rocket affordable n={n}: " + ", ".join(f"{k} {v/n:.3f}" for k, v in c.most_common()) +
          f" | of those with X-Bow also affordable (n={(m & xb_aff).sum()}): chip {np.mean(lab[m & xb_aff]=='chip'):.3f} x-bow {np.mean(lab[m & xb_aff]=='x-bow'):.3f}")
