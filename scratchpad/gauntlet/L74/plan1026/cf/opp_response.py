"""P3-FORK3 opponent check, human side: what the 45 s after a CHIP Rocket look like in real games, by source.

    python -B opp_response.py [live|pro|both] [--out OUT.json]          (laptop; icebow/.venv python; macros/mine.py loaders)

Events (association, never causal): an own tower Rocket on an enemy PRINCESS (mine.tower_spell, nearest tower L / R) that is not
a finisher (no enemy princess falls within FINISH_TICKS) = treated; control = 20-tick grid moments with the Rocket in hand,
own elixir >= 4 and no own Rocket from 100 ticks before to WINDOW after (the "could, did not" moments). Outcomes over WINDOW
ticks: own / enemy princess HP lost (princess units, mine.lost), opponent plays + elixir committed, own plays + elixir.
Per phase (1x / 2x / OT), means and treated - control with a match-cluster bootstrap 90% CI. The SIM side of the same table
comes from the fork dumps (fork3_tables.py): there the contrast is causal (rocket_princess vs the policy's own action)."""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "macros"))
import mine as MN  # noqa: E402  (loaders + helpers; patches hablib costs in-process)

H = MN.H
WINDOW, FINISH_TICKS, STEP, PRE = 900, 80, 20, 100
KEYS = ("own_lost", "foe_lost", "foe_plays", "foe_elixir", "own_plays", "own_elixir")


def phase(t):
    return "1x" if t < 2400 else "2x" if t < 3600 else "OT"


def outcome(m, t):
    t1 = min(t + WINDOW, m["end"])
    fo = [p for p in m["opp"] if t < p["tick"] <= t1]
    ow = [q for q in m["own"] if t < q["tick"] <= t1]
    return {"own_lost": MN.lost(m, "own", t, t1, "LR"), "foe_lost": MN.lost(m, "opp", t, t1, "LR"),
            "foe_plays": len(fo), "foe_elixir": sum(H.cost(p["card"]) or 0 for p in fo),
            "own_plays": len(ow), "own_elixir": sum(H.cost(q["card"]) or 0 for q in ow)}


def chip(m, q):
    if q["card"] != "rocket" or not MN.tower_spell(q):
        return False
    s = min(MN.EN_T, key=lambda k: math.hypot(q["x"] - MN.EN_T[k][0], q["y"] - MN.EN_T[k][1]))
    if s == "K":
        return False
    c0 = MN.crowns(m, q["tick"])[0]
    return MN.crowns(m, q["tick"] + FINISH_TICKS)[0] == c0         # a princess falling within 4 s = a finisher


def events(m):
    """-> [(kind, phase, outcome)] for one match (only moments with a full WINDOW before the end)."""
    out = []
    rk = sorted(q["tick"] for q in m["own"] if q["card"] == "rocket")
    for q in m["own"]:
        if q["tick"] + WINDOW <= m["end"] and chip(m, q):
            out.append(("rocket", phase(q["tick"]), outcome(m, q["tick"])))
    for t in range(200, int(m["end"]) - WINDOW, STEP):
        if any(t - PRE <= r <= t + WINDOW for r in rk):
            continue
        if MN.inhand(m, t, "rocket") and (MN.elixir(m, t) or 0) >= 4:
            out.append(("control", phase(t), outcome(m, t)))
    return out


def table(rows, B=500, seed=0):
    """rows: [(match id, kind, phase, outcome)] -> {phase: {kind: means, diff: {key: [d, lo, hi]}, n}}."""
    rng = random.Random(seed)
    res = {}
    for ph in ("1x", "2x", "OT", "all"):
        sub = [r for r in rows if ph == "all" or r[2] == ph]
        by = {}
        for mid, kind, _, o in sub:
            by.setdefault(mid, {"rocket": [], "control": []})[kind].append(o)
        mids = sorted(by)

        def means(ms):
            agg = {}
            for kind in ("rocket", "control"):
                os_ = [o for mm in ms for o in by[mm][kind]]
                agg[kind] = {k: (sum(o[k] for o in os_) / len(os_)) if os_ else None for k in KEYS}
                agg[kind]["n"] = len(os_)
            return agg
        base = means(mids)
        if not base["rocket"]["n"] or not base["control"]["n"]:
            res[ph] = base
            continue
        boots = []
        for _ in range(B):
            bm = means([rng.choice(mids) for _ in mids])
            if bm["rocket"]["n"] and bm["control"]["n"]:
                boots.append({k: bm["rocket"][k] - bm["control"][k] for k in KEYS})
        diff = {}
        for k in KEYS:
            v = sorted(b[k] for b in boots)
            diff[k] = [round(base["rocket"][k] - base["control"][k], 4), round(v[int(0.05 * len(v))], 4),
                       round(v[int(0.95 * len(v)) - 1], 4)]
        res[ph] = {**base, "diff": diff, "matches": len(mids)}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default="both", choices=("live", "pro", "both"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    srcs = {"live": MN.live_source, "pro": MN.pro_source}
    out = {}
    for name in (("live", "pro") if a.src == "both" else (a.src,)):
        rows = []
        for m in srcs[name]():
            for kind, ph, o in events(m):
                rows.append((m["cid"], kind, ph, o))
        out[name] = table(rows)
        print(name, json.dumps(out[name]["all"], default=str)[:600], flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
