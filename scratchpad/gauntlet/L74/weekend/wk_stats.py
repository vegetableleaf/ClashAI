"""Shared summaries for the weekend chain (S3, S4, S9).  CIs = mech_summary.cr_mean (CR1, clusters = matches)."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mechanic_fork"))
from mech_summary import cr_mean, fmt   # noqa: E402

NAMES = {"D1": ("best defender now", "wait"), "D2": ("defend the pushed lane", "spend in the other lane"),
         "D3": ("wait for the efficient card", "cheap play now"), "D4": ("air-capable card", "ground-only card"),
         "D9": ("non-Tornado second card", "Tornado"), "D10": ("prevent (defender)", "delay (the model's spell)")}


def load(dirs):
    rows = []
    for d in dirs.split(","):
        for ln in (Path(d) / "matches.jsonl").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                if not r.get("skipped"):
                    r["_cl"] = f"{d}|{r['tag']}"
                    rows.append(r)
    return rows


def win(x):
    return float(x["outcome"] == "win")


def tdiff(x, k):
    return x[k]["hp_us"] - x[k]["hp_them"]


def verdict(mu, hw):
    if mu is None or hw is None:
        return "no difference"
    return "DO better" if mu - hw > 0 else ("HOLD better" if mu + hw < 0 else "no difference")


def s3(dirs, out):
    rows = load(dirs)
    opps = [(r["_cl"], o) for r in rows for o in r["mech"]["opps"] if "Bres" in o]
    cl = [c for c, _ in opps]
    w = cr_mean([win(o["Bres"]) - win(o["Ares"]) for _, o in opps], cl)
    L = [f"S3 prevent vs delay: {len(rows)} matches, {len(opps)} forked opportunities in {len(set(cl))} matches (at most 3 per match)",
         "B = hold the spell, then the model's best-cell Tesla/Knight/Ice Wizard when affordable; A = the model's own play. Match end, common random numbers.",
         f"win B - A: {fmt(w, 4)}"]
    for k in ("10", "20", "end"):
        L.append(f"tower diff (ours - theirs) B - A @{k}: {fmt(cr_mean([tdiff(o['Bres'], k) - tdiff(o['Ares'], k) for _, o in opps], cl), 0)}")
    sc = [o["Bres"].get("script") or {} for _, o in opps]
    pl = [x for x in sc if x.get("played")]
    L.append(f"B placed a defender in {len(pl)}/{len(sc)}; accepted {sum(bool(x.get('accepted')) for x in pl)}; mean wait {sum(x['waited'] for x in pl) / max(1, len(pl)):.1f} ticks; "
             f"A cards: {dict(sorted(__import__('collections').Counter(o['A_card'] for _, o in opps).items()))}")
    mu, hw = w[0], w[1]
    ok = mu is not None and hw is not None and mu - hw > 0
    L.append("VERDICT: " + ("prevent beats delay: drill D10 confirmed" if ok else
                           f"prevent does not beat delay at 95% (B - A win {mu if mu is None else round(mu, 4)}): D10 not confirmed"))
    Path(out).write_text("\n".join(L) + "\n")
    return ok


def s9(dirs, out, vjson):
    rows = load(dirs)
    by = {}
    for r in rows:
        for o in r["mech"]["opps"]:
            if o.get("arms") and "Ares" in o:
                by.setdefault(o["drill"], []).append((r["_cl"], o))
    L, V = ["S9 drills phase 2: fork scoring (SIM, match end, common random numbers). DO = first option, HOLD = the contrasted option (named per drill).",
            f"matches {len(rows)}; moments reached/expected per match summed: {sum(r['mech'].get('moments', [0, 0])[1] for r in rows)}/{sum(r['mech'].get('moments', [0, 0])[0] for r in rows)}; "
            f"no-arm skips {sum(len(r['mech'].get('no_arm', [])) for r in rows)}"], {}
    for dr in ("D1", "D2", "D3", "D4", "D9", "D10"):
        ops = by.get(dr, [])
        if not ops:
            L.append(f"{dr}: no forked moments")
            continue
        cl = [c for c, _ in ops]
        alt = (lambda o: o["arms"]["alt"]) if dr != "D10" else (lambda o: o["Ares"])
        d = cr_mean([win(o["arms"]["do"]) - win(alt(o)) for _, o in ops], cl)
        do_own = cr_mean([win(o["arms"]["do"]) - win(o["Ares"]) for _, o in ops], cl)
        alt_own = cr_mean([win(alt(o)) - win(o["Ares"]) for _, o in ops], cl) if dr != "D10" else (None, None, 0, 0)
        v = verdict(d[0], d[1])
        V[dr] = {"DO better": "do", "HOLD better": "alt"}.get(v, "none")
        t20 = cr_mean([tdiff(o["arms"]["do"], "20") - tdiff(alt(o), "20") for _, o in ops], cl)
        L.append(f"{dr} DO={NAMES[dr][0]} vs HOLD={NAMES[dr][1]}: n {len(ops)} moments in {len(set(cl))} matches | win DO - HOLD {fmt(d, 4)} | "
                 f"DO - own {fmt(do_own, 4)} | HOLD - own {fmt(alt_own, 4)} | tower diff@20 DO - HOLD {fmt(t20, 0)}")
        L.append(f"{dr} label: {v}")
    Path(out).write_text("\n".join(L) + "\n")
    Path(vjson).write_text(json.dumps(V))
    return V


def gaps(dirs, V):
    """per trained drill: win(winning-family arm) - win(the model's own play), per moment, CR1 CI.  {drill: cr_mean tuple}"""
    by = {}
    for r in load(dirs):
        for o in r["mech"]["opps"]:
            if o.get("arms") and o.get("drill") in V and V[o["drill"]] in ("do", "alt") and "Ares" in o:
                arm = o["arms"].get(V[o["drill"]])
                if arm is not None:
                    by.setdefault(o["drill"], []).append((r["_cl"], win(arm) - win(o["Ares"])))
    return {k: cr_mean([v for _, v in x], [c for c, _ in x]) for k, x in by.items()}


def s10(before, after, vjson, noninf_ok, evline, out):
    V = json.loads(Path(vjson).read_text())
    trained = [k for k, v in V.items() if v in ("do", "alt")]
    gb, ga = gaps(before, V), gaps(after, V)
    L = [evline, f"drills trained: {trained}",
         "drill fork re-run with the trained model (fresh seeds): gap = win(winning-family arm) - win(own play); smaller after = the model now does more of what wins"]
    imp = []
    for k in trained:
        b, a = gb.get(k), ga.get(k)
        if not b or not a or b[0] is None or a[0] is None:
            L.append(f"{k}: gap n/a")
            continue
        imp.append(a[0] < b[0])
        L.append(f"{k} ({V[k]} family): gap before {fmt(b, 4)} | after {fmt(a, 4)}")
    improves = bool(imp) and all(imp) and any(a[0] is not None for a in ga.values())
    L.append(f"non-inferior on the 960: {noninf_ok}; every trained drill's gap smaller: {improves}")
    L.append("VERDICT: " + ("candidate: ask owner to deploy (never auto)" if noninf_ok and improves else "not a candidate (needs non-inferior AND every trained drill's gap smaller)"))
    Path(out).write_text(chr(10).join(L) + chr(10))


if __name__ == "__main__":
    if sys.argv[1] == "s10":
        s10(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1", sys.argv[6], sys.argv[7])
    elif sys.argv[1] == "s3":
        s3(sys.argv[2], sys.argv[3])
    else:
        print(s9(sys.argv[2], sys.argv[3], sys.argv[4]))
