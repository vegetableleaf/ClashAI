"""--rocket-dead-target SIM A/B summary (vm_ab.sh: <dir>/{base,block}_{evo,lad}/matches.jsonl), paired by (census, tag).
Rocket rows from telemetry 'lr_rockets' (vm_tel_patch.py). Dead-target Rocket = blast (2.0) covers a destroyed enemy
tower footprint (+1.0 princess / +1.4 king), no alive enemy tower footprint, no enemy body within 2.5 tiles at the play.
    python sim_summary.py ~/rocket_dead/sim"""
import json, math, os, random, sys
from collections import Counter

O = sys.argv[1]
PH = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))
T = {"K": (9.0, 3.0, 1.4), "L": (3.5, 6.5, 1.0), "R": (14.5, 6.5, 1.0)}
random.seed(0)


def load(arm):
    out = {}
    for s in ("evo", "lad"):
        p = f"{O}/{arm}_{s}/matches.jsonl"
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r.get("arm") == "plain":
                    out[(s, r["tag"])] = r
    return out


def score(r): return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def boot(v, B=2000):
    v = list(v)
    if not v: return "n/a"
    m = sorted(sum(random.choices(v, k=len(v))) / len(v) for _ in range(B))
    return f"{sum(v) / len(v):.3f} [{m[int(.025 * B)]:.3f},{m[int(.975 * B)]:.3f}]"


def kind(row):
    t, x, y, aK, aL, aR, n0, n1 = row
    alive = {"K": aK, "L": aL, "R": aR}
    over = {k: math.hypot(x - tx, y - ty) <= 2.0 + tr for k, (tx, ty, tr) in T.items()}
    dead = any(over[k] and not alive[k] for k in T)
    live = any(over[k] and alive[k] for k in T)
    return "dead_empty" if dead and not live and n0 == 0 else "tower" if live else "empty" if n0 == 0 and n1 == 0 else "units"


A, Bk = load("base"), load("block")
keys = sorted(set(A) & set(Bk))
a, b = [A[k] for k in keys], [Bk[k] for k in keys]
up = sum(score(y) > score(x) for x, y in zip(a, b)); dn = sum(score(y) < score(x) for x, y in zip(a, b))
print(f"== paired n={len(keys)} (base {len(A)}, block {len(Bk)})")
print(f"wins base {sum(map(score, a)):.1f} vs block {sum(map(score, b)):.1f} | block better {up} worse {dn} sign p={sign_p(up, dn):.4f}"
      f" | tower-hp diff delta {sum(y['tower_hp_diff'] - x['tower_hp_diff'] for x, y in zip(a, b)) / max(len(keys), 1):+.0f}")
for cen in ("evo", "lad"):
    ks = [i for i, k in enumerate(keys) if k[0] == cen]
    u = sum(score(b[i]) > score(a[i]) for i in ks); d = sum(score(b[i]) < score(a[i]) for i in ks)
    print(f"   {cen}: base {sum(score(a[i]) for i in ks):.1f} block {sum(score(b[i]) for i in ks):.1f} better {u} worse {d} p={sign_p(u, d):.3f}")
ot = [i for i in range(len(keys)) if a[i]["end_tick"] > 3600 or b[i]["end_tick"] > 3600]
print(f"OT (either arm past 3600) n={len(ot)}: base {sum(score(a[i]) for i in ot):.1f} block {sum(score(b[i]) for i in ot):.1f}")
changed = sum(x["behaviour"].get("lr_rockets") != y["behaviour"].get("lr_rockets") or score(x) != score(y) for x, y in zip(a, b))
print(f"matches whose Rockets or outcome differ: {changed}")
for name, rows in (("base", a), ("block", b)):
    R = [q for r in rows for q in r["behaviour"].get("lr_rockets", [])]
    c = Counter(kind(q) for q in R)
    print(f"\n== {name}: Rockets/match {len(R) / len(rows):.3f} | " + " ".join(f"{k} {c[k] / len(rows):.4f}" for k in
                                                                         ("dead_empty", "tower", "units", "empty")))
    print(f"   dead_empty Rockets: {c['dead_empty']} (1x/2x/OT {[sum(kind(q) == 'dead_empty' and lo <= q[0] < hi for q in R) for _, lo, hi in PH]})"
          f" | Rockets after an enemy princess fell {sum(not (q[4] and q[5]) for q in R)}")
    tr = [r["behaviour"]["tower_rockets_phase"] for r in rows]
    pu = [r["behaviour"]["push"] for r in rows if "push" in r["behaviour"]]
    st = [v for p in pu for v in p["big_elixir_at_start"]]
    print("   tower Rockets/match " + " ".join(f"{p} {sum(z[p] for z in tr) / len(rows):.3f}" for p, _, _ in PH)
          + f" | push Rockets/match {boot([p['push_rockets'] for p in pu])} | elixir at big-push start {sum(st) / max(len(st), 1):.2f}")
    for p, _, _ in PH:
        cards = Counter()
        for r in rows:
            cards.update(r["behaviour"]["phase_cards"][p])
        tot = sum(cards.values())
        print(f"   {p}: cheap (Skel+Log) {(cards['Skeletons'] + cards['Log']) / max(tot, 1):.3f} | Rocket {cards['Rocket'] / max(tot, 1):.3f}")
