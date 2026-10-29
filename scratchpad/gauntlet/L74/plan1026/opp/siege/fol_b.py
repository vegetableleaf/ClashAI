"""OPP-SIEGE2: follow-up after the on-time answer -- opponent plays in (answer, t + 200] within 11.5 tiles (X-Bow range) of
our reach X-Bow, live vs SIM, and the lock rate by that count; + the same on ALL reach X-Bows from (t, t + 200].
python -I fol_b.py live NAME=DIR ...   (same X-Bows / classes as siege_b)"""
import math
import sys
from collections import defaultdict
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import siege_b as SB  # noqa: E402

R = 11.5


def facts(data):
    out = defaultdict(list)
    for r, xs in data:
        P = r["plays"]
        for rec in SB.classify(r, xs):
            t0 = rec["t"]
            a = t0 + rec["dt"] if rec["cls"] == "answer_ontime" else t0
            n = sum(1 for p in P if a < p[0] <= t0 + SB.T_ALL and math.hypot(p[3] - rec["xx"], p[4] - rec["xy"]) <= R)
            el = sum(p[2] for p in P if a < p[0] <= t0 + SB.T_ALL and math.hypot(p[3] - rec["xx"], p[4] - rec["xy"]) <= R)
            out["all"].append((min(n, 2), el, rec["locked"]))
            if rec["cls"] == "answer_ontime" and rec["kind"] != "spell":
                out["ontime_unit"].append((min(n, 2), el, rec["locked"]))
    return out


for a in sys.argv[1:]:
    name, root = (a, None) if a == "live" else a.split("=", 1)
    F = facts(SB.live_xbows() if root is None else SB.sim_xbows(root))
    for g, v in F.items():
        by = {k: [lk for n, _, lk in v if n == k] for k in (0, 1, 2)}
        print(f"{name:9s} {g:11s} n {len(v):5d} | follow-up plays in range mean {sum(min(n, 2) for n, _, _ in v) / len(v):.2f}"
              f" elixir {sum(e for _, e, _ in v) / len(v):.2f} | share (lock) by 0 / 1 / 2+: "
              + " ".join(f"{len(by[k]) / len(v):.2f} ({sum(by[k]) / max(1, len(by[k])):.2f})" for k in (0, 1, 2)))
