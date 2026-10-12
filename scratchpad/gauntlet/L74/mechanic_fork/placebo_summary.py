"""Placebo vs rocket_tower, same seeds, first-of-episode, <= 3 per match.   python placebo_summary.py PLACEBO_DIR RT_DIR MAXSEED OUT.txt
Paired B - A per opportunity, 95% CI clustered by match (mech_summary.cr_mean).  rocket_tower 'same' opportunities enter as 0."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mech_summary import cr_mean, SCORE  # noqa: E402


def load(d, maxseed, cap):
    rows = [json.loads(x) for x in (Path(d) / "matches.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if not r.get("skipped") and r["seed"] < maxseed]
    opps = []
    for r in rows:
        fo = sorted((o for o in r["mech"]["opps"] if o.get("first", True)), key=lambda o: o["t0"])[:cap]
        opps += [(r["seed"], o) for o in fo]
    return rows, opps


def td(s):
    return s["hp_us"] - s["hp_them"]


def delta(o, k):
    if "Bres" not in o:
        return 0.0
    return td(o["Bres"][k]) - td(o["Ares"][k])


def stats(sel):
    cl = [s for s, _ in sel]
    out = {"n": len(sel), "matches": len(set(cl))}
    for k in ("10", "20", "end"):
        out["td@" + k] = cr_mean([delta(o, k) for _, o in sel], cl)
    out["win"] = cr_mean([100 * ((o["Bres"]["outcome"] == "win") - (o["Ares"]["outcome"] == "win")) if "Bres" in o else 0.0 for _, o in sel], cl)
    out["win_A"] = sum(o["Ares"]["outcome"] == "win" for _, o in sel) / max(1, len(sel))
    out["win_B"] = sum((o["Bres"] if "Bres" in o else o["Ares"])["outcome"] == "win" for _, o in sel) / max(1, len(sel))
    return out


def f(r, nd=0):
    mu, hw, n, c = r
    return "n/a" if mu is None else f"{mu:+.{nd}f} +/-{hw:.{nd}f}" if hw is not None else f"{mu:+.{nd}f}"


def line(lab, s):
    return (f"{lab:34s} n {s['n']:4d} m {s['matches']:3d} | tower diff +10s {f(s['td@10']):>12s} +20s {f(s['td@20']):>12s} "
            f"end {f(s['td@end']):>13s} | win B-A pp {f(s['win'], 1):>12s} (A {s['win_A']:.3f} -> B {s['win_B']:.3f})")


def main(a):
    pd, rd, ms, out = a[0], a[1], int(a[2]), a[3]
    prow, popp = load(pd, ms, 3)
    rrow, ropp = load(rd, ms, 3)
    L = [f"seeds 0:{ms}; placebo matches {len(prow)}, rocket_tower matches {len(rrow)}; first-of-episode, <= 3 per match"]
    sk = sum(len(r["mech"].get("skipped_unsnapshottable", [])) for r in prow)
    L.append(f"placebo opportunities {len(popp)} ({len(popp)/max(1,len(prow)):.2f}/match); forked {sum('Bres' in o for _, o in popp)}; "
             f"B root accepted {sum(bool((o.get('Bres', {}).get('root_play') or {}).get('accepted')) for _, o in popp)}; unsnapshottable skipped {sk}")
    chk = [o for _, o in popp if "Acheck" in o]
    # all A-replay checks in the placebo run (any opportunity incl. beyond cap)
    chk = [o for r in prow for o in r["mech"]["opps"] if "Acheck" in o]
    fa = {k: sum(o["Acheck"][k]["h"] == o["Ares"][k]["h"] for o in chk) for k in ("10", "20", "end")}
    L.append(f"FAITHFULNESS: A-replay from the snapshot vs the original, engine-state hash equal at +10s {fa['10']}/{len(chk)}, "
             f"+20s {fa['20']}/{len(chk)}, end {fa['end']}/{len(chk)}; outcome equal {sum(o['Acheck']['outcome'] == o['Ares']['outcome'] for o in chk)}/{len(chk)}")
    L.append("")
    L.append("B - A (tower diff = our crown-tower HP - theirs, higher is better for us; win in pp); 95% CI clustered by match")
    L.append(line("PLACEBO all", stats(popp)))
    L.append(line("PLACEBO A=play", stats([x for x in popp if x[1]["A"]["play"]])))
    L.append(line("PLACEBO A=wait", stats([x for x in popp if not x[1]["A"]["play"]])))
    L.append(line("ROCKET_TOWER all", stats(ropp)))
    L.append(line("ROCKET_TOWER A=play", stats([x for x in ropp if x[1]["A"]["play"]])))
    L.append(line("ROCKET_TOWER A=wait", stats([x for x in ropp if not x[1]["A"]["play"]])))
    keys = {(s, o["t0"]) for s, o in popp} & {(s, o["t0"]) for s, o in ropp}
    L.append("")
    L.append(f"matched subset (same seed AND same root tick t0): {len(keys)} opportunities")
    L.append(line("PLACEBO matched", stats([x for x in popp if (x[0], x[1]["t0"]) in keys])))
    L.append(line("ROCKET_TOWER matched", stats([x for x in ropp if (x[0], x[1]["t0"]) in keys])))
    pa = {(s, o["t0"]): o for s, o in popp}
    same_A = sum(pa[k]["Ares"]["outcome"] == o["Ares"]["outcome"] for s, o in ropp if (k := (s, o["t0"])) in pa)
    L.append(f"A-branch cross-check (placebo run vs rocket_tower run, same seed+t0): A outcome identical {same_A}/{len(keys)}")
    mp = sum(1 for s, o in popp if "Bres" in o and o["Bres"]["outcome"] != o["Ares"]["outcome"]) / max(1, len(popp))
    L.append(f"placebo opportunities where the outcome flips B vs A: {100*mp:.1f}%")
    Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
