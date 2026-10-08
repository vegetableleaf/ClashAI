"""Summarise the TowerRefine SIM A/B (~/probe_rocket/react{,lad}_tr_*): paired wins vs base (sign test), and from the
behaviour telemetry: Rocket share of plays by phase, tower Rockets per match (all / OT; OT per match among matches reaching OT),
defensive Rockets per match, chip share (tower hit, no troop), X-Bow share by phase. Cluster bootstrap over paired games."""
import json, math, os, random
O = os.path.expanduser("~/probe_rocket"); ARMS = ["tr_base", "tr_w1", "tr_w2"]; random.seed(0)


def load(n):
    out = {}
    for pre in ("react", "reactlad"):
        p = f"{O}/{pre}_{n}/matches.jsonl"
        if not os.path.exists(p): continue
        for l in open(p):
            r = json.loads(l)
            if r["arm"] == "plain": out[(pre, r["tag"])] = r
    return out


def score(r): return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def boot(vals_num, vals_den, B=2000):
    n = len(vals_num); pt = sum(vals_num) / max(sum(vals_den), 1e-9); rs = []
    for _ in range(B):
        idx = [random.randrange(n) for _ in range(n)]; d = sum(vals_den[i] for i in idx)
        if d: rs.append(sum(vals_num[i] for i in idx) / d)
    rs.sort(); return f"{pt:.3f} [{rs[int(.025*len(rs))]:.3f},{rs[int(.975*len(rs))]:.3f}]"


D = {a: load(a) for a in ARMS}
base = D["tr_base"]
for a in ARMS:
    c = D[a]; keys = sorted(set(base) & set(c))
    if not keys: continue
    up = sum(score(c[k]) > score(base[k]) for k in keys); dn = sum(score(c[k]) < score(base[k]) for k in keys)
    rows = [c[k] for k in keys]; bh = [r["behaviour"] for r in rows]
    ot = [b for b, r in zip(bh, rows) if r["end_tick"] > 3600]
    pc = lambda b, ph, card: b["phase_cards"].get(ph, {}).get(card, 0)
    tot = lambda b, ph: sum(b["phase_cards"].get(ph, {}).values())
    print(f"== {a}: n={len(keys)} wins {sum(score(r) for r in rows):.0f} vs base {sum(score(base[k]) for k in keys):.0f} | better {up} worse {dn} "
          f"sign p={sign_p(up, dn):.4f} | mean tower-hp diff delta {sum(c[k]['tower_hp_diff'] - base[k]['tower_hp_diff'] for k in keys)/len(keys):+.0f}")
    print("   Rocket share of plays: " + " ".join(f"{ph} {boot([pc(b, ph, 'Rocket') for b in bh], [tot(b, ph) for b in bh])}" for ph in ("1x", "2x", "OT")))
    print("   X-Bow share of plays:  " + " ".join(f"{ph} {boot([pc(b, ph, 'Xbow') for b in bh], [tot(b, ph) for b in bh])}" for ph in ("1x", "2x", "OT")))
    print(f"   tower Rockets/match all {boot([sum(b['tower_rockets_phase'].values()) for b in bh], [1]*len(bh))} | "
          f"OT tower Rockets/match (all matches) {boot([b['tower_rockets_phase'].get('OT', 0) for b in bh], [1]*len(bh))} | "
          f"per OT match {boot([b['tower_rockets_phase'].get('OT', 0) for b in ot], [1]*len(ot))} (n OT {len(ot)})")
    print(f"   Rockets/match {boot([b['rocket_share']['n'] for b in bh], [1]*len(bh))} | defensive Rockets/match {boot([b['defensive_rockets'] for b in bh], [1]*len(bh))} | "
          f"tower share of Rockets {boot([b['tower_rocket_share']['n'] for b in bh], [b['tower_rocket_share']['denominator'] for b in bh])}")
