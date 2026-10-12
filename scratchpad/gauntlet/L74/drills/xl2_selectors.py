"""XL2 opportunity adapter. Legacy drills.py and its harvest are left untouched.

Imports requiring the pod's card catalogue are delayed until harvest. D5 adds visible
barrels; D7 includes both quiet and threatened opportunities for learning WHEN.
"""
import importlib
import sys
from pathlib import Path


def catalog():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return importlib.import_module("drills")


def barrel_targets(st):
    """Visible barrels / projectiles only, in own tiles; never hidden deployments."""
    targets = []
    for b in st[3]:
        if b[0].removesuffix("_evo") in ("skeleton_barrel", "goblin_barrel") and b[2] <= 18:
            targets.append((b[1], b[2]))
    for name, x, y in st[7]:
        if str(name).lower().replace("_", "").replace(" ", "") in ("goblinbarrel", "skeletonbarrel") and y <= 18:
            targets.append((x, y))
    return sorted(set(targets))


def d5(M, i, st, D=None):
    D = D or catalog()
    yield from D.D5(M, i, st)
    if D.afford(st, {"Log"}):
        for x, y in barrel_targets(st):
            yield "do", "barrel", dict(x=x, y=y, n=1, v=0, barrel=True)


def harvest(m, D=None):
    D = D or catalog()
    M, out, last = D.Match(m), [], {}
    for i, st in enumerate(M.S):
        t = st[0]
        if M.pending(t):
            continue
        for name, sel, judge, rf in D.DRILLS:
            selected = d5(M, i, st, D) if name == "D5" else sel(M, i, st)
            for kind, key, info in selected:
                if kind not in ("do", "dohold") and not (name == "D7" and kind == "hold"):
                    continue
                # D7 is one late-tower opportunity regardless of threat state.
                kk = (name, key)
                if t - last.get(kk, -10**9) < rf:
                    continue
                last[kk] = t
                res, _ = judge(M, t, "do" if name == "D7" else kind, info)
                target = res["do"] if isinstance(res, dict) else res
                out.append(dict(t=t, drill=name, kind=kind, info=info, target=int(target)))
    for t, info in D.D9_moments(M):
        out.append(dict(t=t + int(info["gap"]), drill="D9", kind="dohold", info=info, target=int(info["do"])))
    return out
