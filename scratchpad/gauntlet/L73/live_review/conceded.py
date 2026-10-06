"""What happened in the 30 s before the first conceded tower fell (all losses where the opponent scored first)."""
import collections, math, statistics as st, json, bisect
from core import *
from analyze import own_bodies, lane, TESLA, XBOW, WINCON, BARRELS
xs = load_all()
rows = []
for m, d in xs:
    if m["result"] != "LOSS" or m["state_src"] != "decision": continue
    S = d["states"]; obs = m["obs"]; T = [s["tick"] for s in S]
    dead = m["dead"]
    ev = [(dead[k], k) for k in ("mL", "mR") if dead[k] is not None]
    if not ev: continue
    ev.sort()
    # opponent first only
    mine_dead = [(dead[k], k) for k in ("eL", "eR") if dead[k] is not None]
    if mine_dead and min(mine_dead)[0] < ev[0][0]: continue
    tk, sl = ev[0]; ln = sl[1]
    tx, ty = (3.5, 25.5) if ln == "L" else (14.5, 25.5)
    W0 = tk - 600
    enem = collections.Counter(); tesla_near = False; el = []; hands = []
    for s in S:
        if not (W0 <= s["tick"] <= tk): continue
        mine, enemy = own_bodies(s, obs)
        for e in enemy:
            if math.hypot(e[0] - tx, e[1] - ty) <= 9: enem[nm(e[2])] = 1
        if any(b[2] in TESLA and math.hypot(b[0] - tx, b[1] - ty) <= 8 for b in mine): tesla_near = True
        el.append(s["el"])
    pl = [p for p in m["plays"] if p["conf"] and W0 <= p["tick"] <= tk]
    near_pl = [p for p in pl if math.hypot(p["x"] - tx, p["y"] - ty) <= 9]
    # tower hp 30 s before and 15 s before
    hpv = []
    for s in S:
        for b in s["bodies"]:
            if slot_of(b, obs) == sl and b[4] > 0: hpv.append((s["tick"], b[4] / b[5]))
    def hp_at_(t):
        v = [h for tt, h in hpv if tt <= t]
        return v[-1] if v else None
    rows.append({"log": m["file"][10:25], "tick": tk, "sec": round(tk / 20), "lane": ln, "hp_-30s": hp_at_(tk - 600), "hp_-15s": hp_at_(tk - 300), "enemy": sorted(enem), "tesla_near": tesla_near,
                 "mean_el": round(sum(el) / len(el), 1) if el else None, "plays": len(pl), "plays_near_tower": len(near_pl), "cards": collections.Counter(p["name"] for p in pl)})
print(len(rows))
print("tesla near tower in last 30 s:", sum(r["tesla_near"] for r in rows))
print("mean elixir over window:", st.mean(r["mean_el"] for r in rows if r["mean_el"] is not None))
print("plays in window mean:", st.mean(r["plays"] for r in rows), "near tower", st.mean(r["plays_near_tower"] for r in rows))
print("hp -30s <0.5:", sum(1 for r in rows if r["hp_-30s"] is not None and r["hp_-30s"] < 0.5), "hp -30s >=0.9", sum(1 for r in rows if r["hp_-30s"] is not None and r["hp_-30s"] >= 0.9))
print("lane", collections.Counter(r["lane"] for r in rows))
c = collections.Counter(); [c.update(r["enemy"]) for r in rows]; print(c.most_common(20))
cc = collections.Counter(); [cc.update(r["cards"]) for r in rows]; print(cc)
print("no plays near tower:", sum(1 for r in rows if r["plays_near_tower"] == 0))
print("window mean elixir<=3:", sum(1 for r in rows if r["mean_el"] is not None and r["mean_el"] <= 3))
json.dump(rows, open(HERE + "conceded_first.json", "w"), indent=0, default=str)
