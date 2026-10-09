"""--gate-hazard-threatened SIM A/B summary (vm_ab.sh: <dir>/{base,thr,rad}_{evo,lad}/matches.jsonl), paired by
(census, tag) against base. Threat metrics from the measurement-only telemetry patch (vm_threat_patch.py).
    python sim_summary.py ~/threat/sim [arm ...]"""
import json, math, os, random, statistics, sys
from collections import Counter

O = sys.argv[1]
ARMS = sys.argv[2:] or ["thr", "rad"]
PH = ("1x", "2x", "OT")
CHEAP = {"Skeletons", "Log"}
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


def boot_diff(d, B=4000):
    m = sorted(sum(random.choices(d, k=len(d))) / len(d) for _ in range(B))
    return f"{sum(d) / len(d):+.1f} [{m[int(.025 * B)]:+.1f}, {m[int(.975 * B)]:+.1f}]"


def lost(r):
    t = r["behaviour"]["threat"]
    return t["hp_start"] - t["hp_end"]


def eps(rows):
    return [e for r in rows for e in r["behaviour"]["threat"]["episodes"]]


def describe(name, rows):
    E = eps(rows)
    lat = [e[1] for e in E]
    within = lambda k: sum(x is not None and x <= k for x in lat) / max(len(lat), 1)  # noqa: E731
    med = statistics.median([x if x is not None else 10 ** 9 for x in lat]) if lat else None
    print(f"\n== {name}: n {len(rows)} | tower HP lost/match {sum(map(lost, rows)) / len(rows):.0f} | 3-crown losses "
          f"{sum(r['crowns_against'] == 3 for r in rows)} | crowns against/match {sum(r['crowns_against'] for r in rows) / len(rows):.3f}")
    print(f"   damage episodes/match {len(E) / len(rows):.2f} | first own play after episode start: <=1 s {within(20):.3f} "
          f"<=2 s {within(40):.3f} <=5 s {within(100):.3f} | median {med} ticks | none before the end {lat.count(None)}")
    for lo, hi in ((0, 3), (3, 6), (6, 9), (9, 11)):
        sub = [e[1] for e in E if e[2] is not None and lo <= e[2] < hi]
        if sub:
            print(f"     elixir [{lo},{hi}) at episode start: n {len(sub)} play <=2 s {sum(x is not None and x <= 40 for x in sub) / len(sub):.3f}")
    pu = [r["behaviour"]["push"] for r in rows if "push" in r["behaviour"]]
    st = [v for p in pu for v in p["big_elixir_at_start"]]
    print(f"   elixir at big-push start mean {sum(st) / max(len(st), 1):.2f} (n {len(st)}) | plays/match "
          f"{sum(r['plays_accepted'] for r in rows) / len(rows):.2f}")
    for p in PH:
        cards = Counter()
        for r in rows:
            cards.update(r["behaviour"]["phase_cards"][p])
        tot = sum(cards.values())
        e = [r["behaviour"].get("economy", {}).get(p) for r in rows]
        pl = sum(z["plays"] for z in e if z)
        el = sum(z["elixir_at_play"] * z["plays"] for z in e if z and z["elixir_at_play"] is not None) / max(pl, 1)
        lk = [r["behaviour"].get("leak_ge_9_5", {}).get(p) for r in rows]
        lk = [x for x in lk if x is not None]
        print(f"   {p}: elixir@play {el:.2f} | leak>=9.5 {sum(lk) / max(len(lk), 1):.3f} | cheap (Skel+Log) "
              f"{sum(cards[c] for c in CHEAP) / max(tot, 1):.3f} | " + ", ".join(f"{c} {v / max(tot, 1):.3f}" for c, v in cards.most_common(8)))


A = load("base")
describe("base", list(A.values()))
for arm in ARMS:
    Bk = load(arm)
    keys = sorted(set(A) & set(Bk))
    if not keys:
        continue
    a, b = [A[k] for k in keys], [Bk[k] for k in keys]
    up = sum(score(y) > score(x) for x, y in zip(a, b)); dn = sum(score(y) < score(x) for x, y in zip(a, b))
    print(f"\n######## {arm} vs base: paired n={len(keys)} (base {len(A)}, {arm} {len(Bk)})")
    print(f"wins base {sum(map(score, a)):.1f} vs {arm} {sum(map(score, b)):.1f} (delta {sum(map(score, b)) - sum(map(score, a)):+.1f})"
          f" | {arm} better {up} worse {dn} sign p={sign_p(up, dn):.4f}")
    for cen in ("evo", "lad"):
        ks = [i for i, k in enumerate(keys) if k[0] == cen]
        u = sum(score(b[i]) > score(a[i]) for i in ks); d = sum(score(b[i]) < score(a[i]) for i in ks)
        print(f"   {cen}: base {sum(score(a[i]) for i in ks):.1f} {arm} {sum(score(b[i]) for i in ks):.1f} better {u} worse {d} p={sign_p(u, d):.3f}")
    print(f"   my tower HP lost/match, paired delta {arm} - base: {boot_diff([lost(y) - lost(x) for x, y in zip(a, b)])}")
    print(f"   tower_hp_diff (mine - theirs) paired delta: {boot_diff([y['tower_hp_diff'] - x['tower_hp_diff'] for x, y in zip(a, b)])}")
    print(f"   3-crown losses base {sum(r['crowns_against'] == 3 for r in a)} {arm} {sum(r['crowns_against'] == 3 for r in b)}")
    describe(arm, b)
