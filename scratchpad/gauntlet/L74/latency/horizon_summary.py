"""L74 horizon SIM A/B summary (sim_horizon.sh): wins, paired sign test vs d26, plays / refusals, elixir metrics.
    ~/venv/bin/python horizon_summary.py ~/afford/sim"""
import json
import math
import os
import sys
from statistics import mean

O = sys.argv[1]
ARMS = ("d26", "d24", "d24a23")


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


def phase_stat(rows, key, ph):
    """plays-weighted elixir at play / match-mean leak share for one phase."""
    if key == "elixir_at_play":
        v = [(r["behaviour"]["economy"][ph]["elixir_at_play"], r["behaviour"]["economy"][ph]["plays"]) for r in rows
             if r["behaviour"]["economy"][ph]["elixir_at_play"] is not None]
        return round(sum(a * n for a, n in v) / max(1, sum(n for _, n in v)), 3)
    v = [r["behaviour"]["leak_ge_9_5"][ph] for r in rows if r["behaviour"]["leak_ge_9_5"][ph] is not None]
    return round(mean(v), 4) if v else None


arms = {a: load(a) for a in ARMS}
keys = sorted(set.intersection(*(set(v) for v in arms.values() if v)))
print(f"paired games {len(keys)} ({ {a: len(v) for a, v in arms.items()} })")
for a in ARMS:
    if not arms[a]:
        continue
    rs = [arms[a][k] for k in keys]
    att, acc = sum(r["plays_attempted"] for r in rs), sum(r["plays_accepted"] for r in rs)
    print(f"{a:>7}: wins {sum(map(score, rs)):.1f}/{len(rs)}  crowns diff {mean(r['crowns_diff'] for r in rs):+.3f}  "
          f"plays {att} accepted {acc} refused {att - acc} ({100 * (att - acc) / max(1, att):.2f}%)  "
          f"accepted/min {mean(r['behaviour']['accepted_per_min'] for r in rs):.3f}  "
          f"elixir@play 1x/2x/OT {[phase_stat(rs, 'elixir_at_play', p) for p in ('1x', '2x', 'OT')]}  "
          f"leak>=9.5 {[phase_stat(rs, 'leak', p) for p in ('1x', '2x', 'OT')]}  end tick {mean(r['end_tick'] for r in rs):.0f}")
    if a != "d26":
        b = sum(score(arms[a][k]) > score(arms["d26"][k]) for k in keys)
        c = sum(score(arms[a][k]) < score(arms["d26"][k]) for k in keys)
        print(f"         vs d26: better {b} / worse {c} (sign test p {sign_p(b, c):.3f}); "
              f"wins delta {sum(score(arms[a][k]) - score(arms['d26'][k]) for k in keys):+.1f}")
