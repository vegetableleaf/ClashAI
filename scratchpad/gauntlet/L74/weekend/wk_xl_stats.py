"""S9XL summary: D2 / D3 / D10 fork scoring, XL alone and pooled with the earlier moments of the same drill.
python wk_xl_stats.py OUT.txt VERDICTS.json XL_DIRS PRIOR_DIRS     (comma lists of run dirs holding matches.jsonl)
Line format = wk_stats.s9.  Label = whether the win CI (DO - HOLD, CR1 clustered by match) excludes 0.
verdicts.json (feeds S10XL): pooled label if it is not "no difference", else the XL label."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wk_stats as W   # noqa: E402

DR = ("D2", "D3", "D10")


def by_drill(dirs):
    by = {}
    for r in W.load(dirs):
        for o in r["mech"]["opps"]:
            if o.get("arms") and "Ares" in o and o.get("drill") in DR:
                by.setdefault(o["drill"], []).append((r["_cl"], o))
    return by


def line(dr, ops, tag):
    cl = [c for c, _ in ops]
    alt = (lambda o: o["arms"]["alt"]) if dr != "D10" else (lambda o: o["Ares"])
    d = W.cr_mean([W.win(o["arms"]["do"]) - W.win(alt(o)) for _, o in ops], cl)
    do_own = W.cr_mean([W.win(o["arms"]["do"]) - W.win(o["Ares"]) for _, o in ops], cl)
    alt_own = W.cr_mean([W.win(alt(o)) - W.win(o["Ares"]) for _, o in ops], cl) if dr != "D10" else (None, None, 0, 0)
    t20 = W.cr_mean([W.tdiff(o["arms"]["do"], "20") - W.tdiff(alt(o), "20") for _, o in ops], cl)
    v = W.verdict(d[0], d[1])
    pts = "" if d[1] is None else f" (win CI half-width +-{100 * d[1]:.1f} pts)"
    return (f"{dr} {tag} DO={W.NAMES[dr][0]} vs HOLD={W.NAMES[dr][1]}: n {len(ops)} moments in {len(set(cl))} matches | win DO - HOLD {W.fmt(d, 4)}{pts} | "
            f"DO - own {W.fmt(do_own, 4)} | HOLD - own {W.fmt(alt_own, 4)} | tower diff@20 DO - HOLD {W.fmt(t20, 0)}\n{dr} {tag} label: {v}"), v


if __name__ == "__main__":
    out, vj, xl, prior = sys.argv[1:5]
    bx, bp = by_drill(xl), by_drill(xl + "," + prior)
    rows = W.load(xl)
    L = ["S9XL drills at scale (SIM, match end, common random numbers, archetype-weighted opponents ~60% unfavourable); DO = first option, HOLD = the contrasted option.",
         f"XL matches {len(rows)}; moments reached/expected per match summed (drill passes): {sum(r['mech'].get('moments', [0, 0])[1] for r in rows)}/{sum(r['mech'].get('moments', [0, 0])[0] for r in rows)}; "
         f"no-arm skips {sum(len(r['mech'].get('no_arm', [])) for r in rows)}; " + W.faith(rows),
         "pooled = XL + the earlier moments of the same drill (D2/D3: S9 seeds 1000:1600; D10: S3 seeds 0:240 evo+lad, unweighted opponents, same prevent mechanic, plus S9's D10 forks)"]
    V = {}
    for dr in DR:
        if dr not in bx:
            L.append(f"{dr}: no XL forked moments")
            V[dr] = "none"
            continue
        a, va = line(dr, bx[dr], "XL")
        b, vb = line(dr, bp[dr], "POOLED")
        L += [a, b]
        lab = vb if vb != "no difference" else va
        L.append(f"{dr} label: {lab} (XL {va}; pooled {vb})")
        V[dr] = {"DO better": "do", "HOLD better": "alt"}.get(lab, "none")
    L.append("VERDICT: drills with a label whose win CI excludes 0 (XL or pooled): " + (", ".join(f"{k}={v}" for k, v in V.items() if v != "none") or "none"))
    Path(out).write_text("\n".join(L) + "\n")
    Path(vj).write_text(json.dumps(V))
    print("\n".join(L))
