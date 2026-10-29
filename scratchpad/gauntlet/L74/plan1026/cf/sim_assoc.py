"""P3-FORK3: the live-style ASSOCIATION of opp_response.py, computed inside the SIM, so SIM and live are compared on the same
estimand (CLXIII's own chip Rockets vs "could Rocket, did not" moments), not a forced fork against an association.

    python sim_assoc.py DUMP.jsonl [DUMP2 ...] [--from-update 1]

Natural chip Rocket = a rocket_played sample whose chosen cell is within 3 tiles of an enemy princess centre (my frame); control =
a rocket-trigger sample (Rocket affordable, not played). Outcome = the CHOSEN candidate's own continuation (continuation means
over K), from the root snapshot (ctx.snap) to the dg record at h ticks: own / foe princess HP lost (princess units). Per phase,
mean natural - mean control with a match-cluster bootstrap 90% CI. Needs cf_diag dumps."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
import p4_audit as PA  # noqa: E402

PRINCESS = ((3.5, 6.5), (14.5, 6.5))


def lost(s, h, i):
    """mean over continuations of (dg[h].snap[i] - root snap[i]) for the chosen candidate, or None."""
    d = (s["cands"][0].get("dg") or {}).get(h)
    if not d or not s.get("ctx"):
        return None
    v = [x[i] - s["ctx"]["snap"][i] for x in d["snap"] if x is not None]
    return float(np.mean(v)) if v else None


def phase(t):
    return "1x" if t < 2400 else "2x" if t < 3600 else "OT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--from-update", type=int, default=1)
    ap.add_argument("--h", default="stop")
    a = ap.parse_args()
    from pipeline import decision_options as DO
    x, y = DO.cell_centres_tiles("lattice")
    S = PA.load(a.files, a.from_update)
    rows = []
    for s in S:
        c = s["cands"][0]
        if s["trigger"] == "rocket_played" and c["play"] and min(math.hypot(x[c["cell"]] - px, y[c["cell"]] - py)
                                                                for px, py in PRINCESS) <= 3.0:
            kind = "rocket"
        elif s["trigger"] == "rocket":
            kind = "control"
        else:
            continue
        o, f = lost(s, a.h, 0), lost(s, a.h, 4)
        if o is not None:
            rows.append((s["mid"], kind, phase(s["tick"]), o, f))
    for ph in ("all", "1x", "2x", "OT"):
        sub = [r for r in rows if ph == "all" or r[2] == ph]
        for j, name in ((3, "own princess lost"), (4, "foe princess lost")):
            r = [(v[j], v[0]) for v in sub if v[1] == "rocket"]
            c = [(v[j], v[0]) for v in sub if v[1] == "control"]
            if len(r) < 5 or len(c) < 5:
                print(f"{ph} {name}: n rocket {len(r)} control {len(c)}")
                continue
            mids = sorted({m for _, m in r + c})
            rng = np.random.default_rng(0)
            boots = []
            for _ in range(1000):
                w = rng.choice(mids, len(mids))
                cnt = {m: 0 for m in mids}
                for m in w:
                    cnt[m] += 1
                rr = [v * cnt[m] for v, m in r]
                cc = [v * cnt[m] for v, m in c]
                nr, nc = sum(cnt[m] for _, m in r), sum(cnt[m] for _, m in c)
                if nr and nc:
                    boots.append(sum(rr) / nr - sum(cc) / nc)
            d = np.mean([v for v, _ in r]) - np.mean([v for v, _ in c])
            print(f"{ph} {name}: rocket {np.mean([v for v, _ in r]):.3f} (n {len(r)}) control {np.mean([v for v, _ in c]):.3f} "
                  f"(n {len(c)}) diff {d:+.3f} [{np.percentile(boots, 5):+.3f}, {np.percentile(boots, 95):+.3f}]")


if __name__ == "__main__":
    main()
