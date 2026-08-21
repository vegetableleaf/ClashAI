"""WHY does a drill pay most for the wrong outcome? Per-REWARD-TERM means, split by outcome.

`run.py drills --outcomes` is the acceptance test: it says WHETHER passing pays best. When it says
no, this says WHICH TERM is responsible, which is the only way to fix the reward underneath rather
than papering over it with a drill-completion bonus.

    python tools/drill_terms.py nado_king_activation [reps]

Reads `env.rw_stats.match_summary()` at the end of each episode -- the same per-term accounting the
trainer already keeps -- and averages each term over the episodes that ended in each outcome. A
term that never fires for an outcome shows "-", which is usually the finding: the first fix this
tool produced was a king-activation credit that paid +0.5 on episodes that FAILED the drill and
nothing at all on the ones that passed.

Exploration matches `drills --outcomes` (0.45 wait, 0.75 cell floor, 0.6 of it through the prior)
so the episodes examined here are the ones training actually generates.
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim import scenarios as sc                 # noqa: E402
from clashrl.sim import doctrine as _doc                # noqa: E402
from clashrl.sim.drill_env import DrillEnv              # noqa: E402


def explore(env, rnd):
    """The trainer's drill sampling mixture -- see drill_env.outcomes()."""
    hand = [c for c in env._hand_ids()
            if 0 <= c < len(env.specs) and float(env.eng.elixir[0]) >= float(env.specs[c].elixir)]
    if not hand or rnd.random() < 0.45:
        return (0, 0, 0)
    cid = rnd.choice(hand)
    if rnd.random() < 0.75 and rnd.random() < 0.6:
        try:
            dc = _doc.doctrine_cells(env, cid)
        except Exception:                                # noqa: BLE001
            dc = None
        if dc:
            tot = sum(w for _c, w in dc)
            r, acc = rnd.random() * tot, 0.0
            for c, w in dc:
                acc += w
                if r <= acc:
                    return (1, cid, int(c))
    return (1, cid, rnd.randrange(env.n_cells))


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "nado_king_activation"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    cfg = Config.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                   "config", "config.yaml"))
    sc.load_all()                                        # the registry is populated on import of the packs
    s = sc.get(name)
    rnd = random.Random(5)
    by = {}                                              # verdict -> [ {term: total}, ... ]
    ep_r = {}
    for k in range(reps):
        env = DrillEnv(cfg, s, seed=7000 + k, level=11)
        env.reset()
        done, tot, info = False, 0.0, {}
        while not done:
            _o, r, done, info = env.step(explore(env, rnd))
            tot += float(r)
        v = (info or {}).get("verdict", "?")
        terms = env.rw_stats.match_summary().get("terms", {})
        by.setdefault(v, []).append({k2: float(t.get("total", 0.0)) for k2, t in terms.items()})
        ep_r.setdefault(v, []).append(tot)

    cols = [c for c in ("pass", "fail", "timeout") if c in by] + \
           [c for c in sorted(by) if c not in ("pass", "fail", "timeout")]
    names = sorted({t for rows in by.values() for row in rows for t in row})
    print("%s   (%d episodes)" % (name, reps))
    print("%-24s %s" % ("", "".join("%12s" % ("%s(n=%d)" % (c[:7], len(by[c]))) for c in cols)))
    print("-" * (24 + 12 * len(cols)))
    for t in names:
        cells = []
        for c in cols:
            rows = by[c]
            vals = [row.get(t, 0.0) for row in rows]
            m = sum(vals) / max(1, len(vals))
            cells.append("%12s" % ("%+.3f" % m if any(abs(v) > 1e-9 for v in vals) else "-"))
        print("%-24s %s" % (t, "".join(cells)))
    print("-" * (24 + 12 * len(cols)))
    print("%-24s %s" % ("EPISODE TOTAL",
                        "".join("%12s" % ("%+.3f" % (sum(ep_r[c]) / len(ep_r[c]))) for c in cols)))


if __name__ == "__main__":
    main()
