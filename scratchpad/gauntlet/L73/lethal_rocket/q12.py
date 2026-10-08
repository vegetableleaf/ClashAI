"""Q1/Q2: replay the owner's OT match (live_play_20261008_131352) decision states through the live checkpoint.
  python q12.py <log> <ckpt>
1) validation: replayed p_play / top card / xy vs the logged ones, every decision;
2) Q1: ticks 3840-4304, per variant (base / +CellRefine / +TowerRefine = live): gate p, card probs, Rocket cell mass
   near each enemy princess, plain argmax vs rocket_area cell;
3) Q2: tower-HP ablations on the 4018 (aim L) and 4304 (aim R) states."""
import sys, os, json
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rebuild import Match, analyse, variant, tower_masks, _CX, _CY
from pipeline.model_v3 import cell_xy
from pipeline.decision_options import rocket_area_scores, is_xbow

torch.set_num_threads(8)
LOG, CKPT = sys.argv[1], sys.argv[2]
m = Match(LOG, CKPT)
model = m.model
masks, R, TR = tower_masks(m.grid)
print(f"side {m.side}; grid {m.grid}; rocket radius {R:.3f} tiles; princess collision radius {TR:.3f}; decisions {len(m.dec)}")
print("deck", m.deck)

# ---------- 1) validation ----------
dp, card_ok, xy_ok, xy_n, rows = [], 0, 0, 0, []
for i, d in enumerate(m.dec):
    dc = d["decision"]
    if dc.get("no_affordable") or dc.get("p_play") is None:
        continue
    b, info = m.batch(i)
    with torch.no_grad():
        o = model(b)
        p = float(torch.sigmoid(o["gate"][0]))
        lg = o["card"][0].clone(); lg[~torch.from_numpy(info["allowed"])] = -torch.inf
        pos = int(lg.argmax()); name = info["names"][pos]
        dp.append(abs(p - dc["p_play"]))
        card_ok += name == dc["name"]
        if name == dc["name"] and dc.get("xy") is not None and not (is_xbow(name) and dc["play"]) and not (dc["play"] and name != "Rocket"):
            c, f = info["hand"][pos]
            cell = model(b, card=torch.tensor([c]), form=torch.tensor([f]))["cell"]
            if name == "Rocket":
                area = rocket_area_scores(torch.softmax(cell, -1))
                cc = int(cell[0].masked_fill(~(area[0] == area[0].max()), -torch.inf).argmax())
            else:
                cc = int(cell[0].argmax())
            xy = cell_xy(cc, m.grid)
            xy_n += 1; xy_ok += max(abs(xy[0] - dc["xy"][0]), abs(xy[1] - dc["xy"][1])) < 1e-3
    rows.append((d["tick"], round(dc["p_play"], 4), round(p, 4), dc["name"], name))
dp = np.array(dp)
print(f"VALIDATION n={len(dp)}: |dp| median {np.median(dp):.5f} p90 {np.percentile(dp, 90):.5f} max {dp.max():.5f}; "
      f"|dp|<1e-3 {np.mean(dp < 1e-3):.3f} <1e-2 {np.mean(dp < 1e-2):.3f}; top card agrees {card_ok}/{len(dp)}; "
      f"xy agrees (wait rows + Rocket rows, same card) {xy_ok}/{xy_n}")
bad = [r for r in rows if abs(r[1] - r[2]) >= 1e-2 or r[3] != r[4]]
print("disagreements (tick, logged p, replay p, logged card, replay card):", len(bad))
for r in bad[:25]:
    print("  ", r)
win = [r for r in rows if 3840 <= r[0] <= 4304]
print("window 3840-4304 max |dp| %.5f, card agree %d/%d" % (max(abs(r[1] - r[2]) for r in win), sum(r[3] == r[4] for r in win), len(win)))

# ---------- 2) Q1 ----------
print("\nQ1 per decision 3840..4304 (variants base / cr = +CellRefine / full = +TowerRefine = live)")
idx = {d["tick"]: i for i, d in enumerate(m.dec)}
for t in sorted(idx):
    if not 3840 <= t <= 4304:
        continue
    i = idx[t]; dc = m.dec[i]["decision"]
    b, info = m.batch(i)
    res = analyse(m, b, info, model)
    print(f"tick {t} logged p {dc['p_play']:.3f} tau {dc.get('gate_tau')} play {dc['play']} {dc['name']} xy {dc.get('xy')} "
          f"el {m.dec[i]['public']['model_own_elixir']:.2f}")
    for v, r in res.items():
        print("   ", v, json.dumps(r))

# ---------- 3) Q2 ----------
print("\nQ2 tower-HP ablations (sc[56] = enemy L princess hp_frac, sc[57] = enemy R)")
for t in (4018, 4304):
    i = idx[t]
    b0, info = m.batch(i)
    print(f"state tick {t}: sc[52:58] = {np.round(b0['sc'][0, 52:58].numpy(), 3).tolist()} alive {b0['sc'][0, 64:70].tolist()}")
    L0, R0 = float(b0["sc"][0, 56]), float(b0["sc"][0, 57])
    cases = [("orig", L0, R0), ("swap", R0, L0), ("L=.05", .05, R0), ("L=.01", .01, R0), ("L=.30", .30, R0),
             ("L=1.0", 1.0, R0), ("R=.05", L0, .05), ("both=1", 1.0, 1.0), ("both=.102", L0, L0)]
    for name, l, r in cases:
        b = dict(b0); sc = b0["sc"].clone(); sc[0, 56], sc[0, 57] = l, r; b["sc"] = sc
        res = analyse(m, b, info, model)
        line = []
        for v, x in res.items():
            line.append(f"{v}: p {x['p']:.3f} P(Rk) {x['card'].get('Rocket', 0):.3f} top {x['top']} "
                        f"massL {x['rk_mass']['L']:.3f} massR {x['rk_mass']['R']:.3f} hitL {x['rk_mass']['L_hit']:.3f} "
                        f"hitR {x['rk_mass']['R_hit']:.3f} area {x['rk_area'][2]} argmax {x['rk_argmax'][2]}")
        print(f"  {name:9s} L {l:.3f} R {r:.3f} | " + " | ".join(line))
    # sweep the L tower HP, full model
    print("  sweep L hp (full model):")
    for l in (0.01, .03, .05, .08, .102, .15, .2, .3, .5, .75, 1.0):
        b = dict(b0); sc = b0["sc"].clone(); sc[0, 56] = l; b["sc"] = sc
        x = analyse(m, b, info, model, variants=("full",))["full"]
        print(f"    L {l:.3f}: p {x['p']:.3f} P(Rk) {x['card'].get('Rocket', 0):.3f} massL {x['rk_mass']['L']:.3f} "
              f"massR {x['rk_mass']['R']:.3f} area {x['rk_area'][2]} areaL {x['rk_area_at_tower']['L']:.3f} areaR {x['rk_area_at_tower']['R']:.3f}")
