"""lethal_rocket SIM A/B summary: wins per arm, paired sign test, rule fires (plays with why == 'lethal_rocket'), their
earliest decision tick, and the matches they decided.  python sim_summary.py ~/lethal/sim"""
import json, math, os, sys
from collections import Counter

O = sys.argv[1]


def load(name):
    out = {}
    for s in ("evo", "lad"):
        p = f"{O}/{name}_{s}/matches.jsonl"
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r["arm"] == "plain":
                    out[(s, r["tag"])] = r
    return out


def score(r):
    return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


base, lr = load("v3_base"), load("v3_lr")
keys = sorted(set(base) & set(lr))
print(f"paired games {len(keys)} (base {len(base)}, lr {len(lr)})")
for name, arm in (("base", base), ("lethal_rocket", lr)):
    print(f"  {name}: wins {sum(score(arm[k]) for k in keys):.1f} / {len(keys)}; outcomes {dict(Counter(arm[k]['outcome'] for k in keys))}")
b = sum(score(lr[k]) > score(base[k]) for k in keys); c = sum(score(lr[k]) < score(base[k]) for k in keys)
print(f"  paired: lr better {b} / worse {c} (sign test p {sign_p(b, c):.3f})")


def beh(r):
    b = r.get("behaviour") or {}
    return b if isinstance(b, dict) else eval(b)          # older writers stored a repr string


for name, arm in (("base", base), ("lethal_rocket", lr)):
    bh = [beh(arm[k]) for k in keys]
    rk = sum(((b.get("phase_cards") or {}).get("OT") or {}).get("Rocket", 0) for b in bh)
    ot = sum(((b.get("economy") or {}).get("OT") or {}).get("minutes", 0) > 0 for b in bh)
    print(f"  {name}: OT Rocket plays {rk}; finish_offs {sum(b.get('finish_offs', 0) for b in bh)}; matches reaching OT {ot}")
print("(search_s0 results carry no per-play 'why'; fires are counted by fire_log_s0.py below)")
ch = [k for k in keys if score(lr[k]) != score(base[k])]
print("  changed outcomes (tag, base -> lr, end_tick base/lr):",
      [(k, base[k]["outcome"], lr[k]["outcome"], base[k]["end_tick"], lr[k]["end_tick"]) for k in ch])

# fires logged by fire_log_s0.py (sim_fires.sh) and the logged re-run's determinism vs the plain lr arm
import glob
fires = [json.loads(l) for f in glob.glob(f"{O}/fires_*/fires_*.jsonl") for l in open(f)]
if fires:
    ts = sorted(x["t_sec"] for x in fires)
    print(f"logged fires {len(fires)}: model-board t_sec min {ts[0]:.2f} (OT edge 180.00), before 180 s: "
          f"{sum(t < 180 for t in ts)}; lanes {dict(Counter(x['target']['lane'] for x in fires))}; "
          f"target HP median {sorted(x['target']['hp'] for x in fires)[len(fires) // 2]}; damage/level "
          f"{dict(Counter((x['target']['damage'], x['target']['level']) for x in fires))}")
    log = load("v3_lrlog")
    same = sum(log[k]["outcome"] == lr[k]["outcome"] for k in keys if k in log)
    print(f"  logged re-run outcomes identical to the lr arm: {same} / {sum(k in log for k in keys)}")
