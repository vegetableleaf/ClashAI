"""--xbow-dead-lane SIM A/B summary (vm_ab.sh: <dir>/{base,block}_{evo,lad}/matches.jsonl). Paired by (census, tag).
X-Bow classes from telemetry 'lr_xbows' with classes.py's geometry (KONLY / OFF_P / DL_LOCK / DL_BACK / DEF).
    python sim_summary.py ~/deadlane/sim"""
import json, math, os, random, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classes import cls  # noqa: E402

O = sys.argv[1]
PH = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))
CHEAP = {"Skeletons", "Log"}
C = ("KONLY", "OFF_P", "DL_LOCK", "DL_BACK", "DEF")
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


def ph(t): return "1x" if t < 2400 else "2x" if t < 3600 else "OT"


def xbow_rows(r):
    return [dict(t=x[0], ph=ph(x[0]), c=cls(x[1], x[2], {"K": True, "L": x[3], "R": x[4]}), down=not (x[3] and x[4]))
            for x in r["behaviour"].get("lr_xbows", [])]


A, Bk = load("base"), load("block")
keys = sorted(set(A) & set(Bk))
a, b = [A[k] for k in keys], [Bk[k] for k in keys]
up = sum(score(y) > score(x) for x, y in zip(a, b)); dn = sum(score(y) < score(x) for x, y in zip(a, b))
print(f"== paired n={len(keys)} (base {len(A)}, block {len(Bk)})")
print(f"wins base {sum(map(score, a)):.1f} vs block {sum(map(score, b)):.1f} | block better {up} worse {dn} sign p={sign_p(up, dn):.4f}"
      f" | tower-hp diff delta {sum(y['tower_hp_diff'] - x['tower_hp_diff'] for x, y in zip(a, b)) / len(keys):+.0f}")
for cen in ("evo", "lad"):
    ks = [i for i, k in enumerate(keys) if k[0] == cen]
    u = sum(score(b[i]) > score(a[i]) for i in ks); d = sum(score(b[i]) < score(a[i]) for i in ks)
    print(f"   {cen}: base {sum(score(a[i]) for i in ks):.1f} block {sum(score(b[i]) for i in ks):.1f} better {u} worse {d} p={sign_p(u, d):.3f}")
ot = [i for i in range(len(keys)) if a[i]["end_tick"] > 3600 or b[i]["end_tick"] > 3600]
print(f"OT (either arm past 3600 ticks) n={len(ot)}: base {sum(score(a[i]) for i in ot):.1f} block {sum(score(b[i]) for i in ot):.1f}"
      f" | base reached OT {sum(r['end_tick'] > 3600 for r in a)} block {sum(r['end_tick'] > 3600 for r in b)}")
changed = sum(len(xbow_rows(x)) != len(xbow_rows(y)) or score(x) != score(y) for x, y in zip(a, b))
print(f"matches whose outcome or X-Bow count differ: {changed}")
for name, rows in (("base", a), ("block", b)):
    X = [xbow_rows(r) for r in rows]
    print(f"\n== {name}: X-Bows/match {boot([len(x) for x in X])}")
    for p in ("1x", "2x", "OT", None):
        cnt = Counter(q["c"] for x in X for q in x if p is None or q["ph"] == p)
        print(f"   {p or 'all':3s} per match " + " ".join(f"{c} {cnt[c] / len(rows):.3f}" for c in C))
    down = Counter(q["c"] for x in X for q in x if q["down"])
    print(f"   with an enemy princess down: n {sum(down.values())} " + " ".join(f"{c} {down[c]}" for c in C))
    print(f"   blocked set (KONLY + DL_LOCK)/match {boot([sum(q['c'] in ('KONLY', 'DL_LOCK') for q in x) for x in X])}")
    xp = [r["behaviour"]["xbow_phase"] for r in rows]
    print("   lead-rule defensive X-Bows/match " + " ".join(f"{p} {sum(z[p]['defensive'] for z in xp) / len(rows):.3f}" for p, _, _ in PH))
    tr = [r["behaviour"]["tower_rockets_phase"] for r in rows]
    pu = [r["behaviour"]["push"] for r in rows if "push" in r["behaviour"]]
    st = [v for p in pu for v in p["big_elixir_at_start"]]
    rk = sum(sum(r["behaviour"]["phase_cards"][p].get("Rocket", 0) for p, _, _ in PH) for r in rows)
    print(f"   Rockets/match {rk / len(rows):.3f}: tower " + " ".join(f"{p} {sum(z[p] for z in tr) / len(rows):.3f}" for p, _, _ in PH)
          + f" | push Rockets/match {boot([p['push_rockets'] for p in pu])}")
    print(f"   elixir at big-push start mean {sum(st) / max(len(st), 1):.2f} (n {len(st)})")
    for p, _, _ in PH:
        cards = Counter()
        for r in rows:
            cards.update(r["behaviour"]["phase_cards"][p])
        tot = sum(cards.values())
        e = [r["behaviour"].get("economy", {}).get(p) for r in rows]
        pl = sum(z["plays"] for z in e if z); el = sum(z["elixir_at_play"] * z["plays"] for z in e if z and z["elixir_at_play"] is not None) / max(pl, 1)
        print(f"   {p}: elixir@play {el:.2f} | cheap (Skel+Log) {sum(cards[c] for c in CHEAP) / max(tot, 1):.3f} | "
              + ", ".join(f"{c} {v / max(tot, 1):.3f}" for c, v in cards.most_common(8)))
