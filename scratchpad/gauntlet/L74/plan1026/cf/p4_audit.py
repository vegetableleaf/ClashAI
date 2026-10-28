"""P4 incentive audit tables from CF_DUMP jsonl files (cf_diag on for the full set of splits; older pilot dumps give the
trigger x kind rows by tick phase only).

    python p4_audit.py DUMP.jsonl [DUMP2.jsonl ...] [--from-update U] [--min-n 8] [--json OUT.json] > tables.md

Every number is a WITHIN-SAMPLE difference "alternative minus the policy's own action (candidate 0 = chosen)" in the K-mean
return Q (K CRN-paired continuations; value units, +-1 = a win), averaged over samples with a 90% CLUSTER bootstrap interval
over MATCHES (samples of one match are correlated; 2,000 resamples). Lenses (cf_diag): Q at the main horizon and at the sweep
horizons ("qh"), the terminal return of the audited samples (q_end of continuation 0; candidate 0 vs alternative), the Phi and
critic parts of Q (dg), the tower / elixir snapshot differences (dg snap: princess hp lost = fractions summed over the 2
princesses, king hp lost, crowns conceded, elixir) and the plays landed since the root (dg np).
Splits: all, phase (1x < 2400 ticks, 2x < 3600, OT), score (ahead / even / behind from the root snapshot), close OT, our Tesla in
hand, opponent type, trigger-specific (target class, clump value, redirect distance / counters in hand)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

HEAVY = {"giant", "royalgiant", "golem", "pekka", "megaknight", "electrogiant", "goblingiant", "elixirgolem", "lavahound",
         "runegiant", "ramrider"}
HOGLIKE = {"hogrider", "battleram", "royalhogs", "wallbreakers", "skeletonbarrel"}
COUNTERS = {"log", "tesla", "knight", "icewizard", "valkyrie", "skeletons", "icespirit", "fireball", "zap"}
SNAP = ("own_p_lost", "own_k_lost", "own_k_on", "own_crowns_lost", "foe_p_lost", "foe_k_lost", "foe_k_on", "foe_crowns_lost",
        "own_elixir", "foe_elixir")


def load(files, from_update=0, min_tick=0):
    out, mid = [], 0
    for fn in files:
        for ln, line in enumerate(open(fn, encoding="utf-8")):
            r = json.loads(line)
            if r.get("update", 0) < from_update:
                continue
            mid += 1
            cf = r["cf"]
            for s in cf["samples"]:
                if s["tick"] >= min_tick:
                    out.append({**s, "mid": mid, "opp": cf.get("opp"), "outcome": r.get("outcome"), "file": Path(fn).name})
    return out


def mean_k(v):
    v = [x for x in v if x is not None]
    return float(np.mean(v)) if v else None


def qmain(c):
    return mean_k(c["q"])


def paired_k(a, b, getter):
    """mean over k of getter(a)[k] - getter(b)[k], k where both exist."""
    x, y = getter(a), getter(b)
    if x is None or y is None:
        return None
    d = [p - q for p, q in zip(x, y) if p is not None and q is not None]
    return float(np.mean(d)) if d else None


def metric(s, alt, which):
    """The within-sample difference alt - chosen for ``which`` (see module doc), or None."""
    ch = s["cands"][0]
    if which == "q":
        return paired_k(alt, ch, lambda c: c["q"])
    if which.startswith("qh"):
        h = which[2:]
        return paired_k(alt, ch, lambda c: (c.get("qh") or {}).get(h))
    if which == "qend":
        if not s.get("audit"):
            return None
        e = lambda c: (c["q"][0] if c["terminal"][0] else c.get("q_end"))
        a, b = e(alt), e(ch)
        return None if a is None or b is None else float(a - b)
    if which.startswith("dg_"):
        key, field = which[3:].split(":")
        def g(c):
            d = (c.get("dg") or {}).get(key)
            if d is None:
                return None
            if field in ("phi", "v"):
                return d[field]
            if field.startswith("np"):
                i = int(field[2:])
                return [None if x is None else x[i] for x in d["np"]]
            i = SNAP.index(field)
            return [None if x is None else x[i] for x in d["snap"]]
        return paired_k(alt, ch, g)
    raise KeyError(which)


def boot_ci(vals, mids, n=2000, seed=0):
    vals, mids = np.asarray(vals, float), np.asarray(mids)
    if len(vals) == 0:
        return None
    u, inv = np.unique(mids, return_inverse=True)
    sums, cnt = np.bincount(inv, vals), np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(u), (n, len(u)))
    m = sums[idx].sum(1) / cnt[idx].sum(1)
    return [float(np.percentile(m, 5)), float(np.percentile(m, 95))]


def state(s):
    """(crowns ours, crowns theirs, tower hp margin = foe lost - own lost) from the root snapshot, or None."""
    c = s.get("ctx")
    if not c:
        return None
    sn = c["snap"]
    return sn[7], sn[3], (sn[4] + sn[5]) - (sn[0] + sn[1])


def splits(s):
    out = [("all", "all")]
    t = s["tick"]
    out.append(("phase", "1x" if t < 2400 else "2x" if t < 3600 else "OT"))
    st = state(s)
    if st is not None:
        ours, theirs, mg = st
        lab = "ahead" if ours > theirs or (ours == theirs and mg > 0.25) else "behind" if ours < theirs or (
            ours == theirs and mg < -0.25) else "even"
        out.append(("score", lab))
        if t >= 3600 and ours == theirs and abs(mg) <= 0.25:
            out.append(("close_ot", "close OT (even crowns, |hp margin| <= .25)"))
        hand = set(s["ctx"]["hand"])
        out.append(("tesla", "tesla in hand" if "tesla" in hand else "tesla not in hand"))
        el = s["ctx"]["snap"][8]
        out.append(("elixir", "elixir >= 8" if el >= 8 else "elixir < 8"))
    o = s.get("opp")
    if o:
        out.append(("opp", (o["opp"].get("type") or "?")))
        b = (o.get("style") or {}).get("bank")
        if b is not None:
            out.append(("opp_bank", "bank>=2" if b >= 2.0 else "bank<2"))
    tg = s.get("target")
    if tg and tg.get("name"):
        n = tg["name"]
        out.append(("target", "heavy " + n if n in HEAVY else "hoglike " + n if n in HOGLIKE else "other " + n))
        out.append(("target_class", "heavy" if n in HEAVY else "hoglike" if n in HOGLIKE else "other"))
    if s["trigger"] == "tornado_redirect" and tg:
        out.append(("dist", "dist < 6" if tg.get("d", 99) < 6 else "dist 6+"))
        if s.get("ctx"):
            out.append(("counter", "counter in hand" if set(s["ctx"]["hand"]) & COUNTERS else "no counter in hand"))
    for c in s["cands"][1:]:
        m = c.get("meta") or {}
        if "value" in m and c["kind"] in ("combo", "rocket_clump"):
            v = m["value"]
            out.append(("value_" + c["kind"], "<4" if v < 4 else "4-6" if v < 6 else "6-8" if v < 8 else "8+"))
    return out


def table(samples, which, min_n, order=None):
    """rows: (trigger, kind, split, label) -> (n, mean, ci)."""
    cells = defaultdict(lambda: ([], []))
    for s in samples:
        sp = splits(s)
        for c in s["cands"][1:]:
            v = metric(s, c, which)
            if v is None:
                continue
            for k, lab in sp:
                cells[(s["trigger"], c["kind"], k, lab)][0].append(v)
                cells[(s["trigger"], c["kind"], k, lab)][1].append(s["mid"])
    rows = []
    for key, (v, m) in sorted(cells.items()):
        if len(v) >= min_n:
            rows.append((*key, len(v), float(np.mean(v)), boot_ci(v, m)))
    return rows


def md(rows, head):
    lines = [f"### {head}", "", "| trigger | alternative | split | label | n | mean dQ | 90% CI |", "|---|---|---|---|---|---|---|"]
    for t, k, sp, lab, n, mu, ci in rows:
        flag = "" if ci is None or ci[0] <= 0 <= ci[1] else " *"
        lines.append(f"| {t} | {k} | {sp} | {lab} | {n} | {mu:+.3f}{flag} | [{ci[0]:+.3f}, {ci[1]:+.3f}] |" if ci else
                     f"| {t} | {k} | {sp} | {lab} | {n} | {mu:+.3f} | - |")
    return "\n".join(lines) + "\n"


def profile(samples, min_n, hs=("150", "300", "450", "600", "750"), group=("all",)):
    """Q difference by horizon (sample-paired: only samples that have every column), + terminal, per trigger x kind, on the
    audited samples whose main horizon covers every sweep stop; an unaudited-sample column set is also given without terminal."""
    out = []
    by = defaultdict(list)
    for s in samples:
        for c in s["cands"][1:]:
            by[(s["trigger"], c["kind"])].append((s, c))
    for (t, k), lst in sorted(by.items()):
        for audited in (True, False):
            sel = [(s, c) for s, c in lst if (s.get("audit") or not audited)]
            cols = {}
            for h in ("q",) + tuple("qh" + h for h in hs) + (("qend",) if audited else ()):
                cols[h] = [(metric(s, c, h), s["mid"]) for s, c in sel]
            keep = [i for i in range(len(sel)) if all(cols[h][i][0] is not None for h in cols)]
            if len(keep) < min_n:
                continue
            row = {"trigger": t, "kind": k, "audited": audited, "n": len(keep), "cols": {}}
            for h in cols:
                v = [cols[h][i][0] for i in keep]
                m = [cols[h][i][1] for i in keep]
                row["cols"][h] = (float(np.mean(v)), boot_ci(v, m))
            out.append(row)
    return out


def md_profile(rows):
    cols = None
    lines = ["### Horizon profile: mean dQ (alt - chosen), same samples in every column (terminal = audited samples only)", ""]
    hdr = None
    for r in rows:
        if hdr is None or list(r["cols"]) != hdr:
            hdr = list(r["cols"])
            lines += ["", "| trigger | alternative | audited | n | " + " | ".join(hdr) + " |", "|---|---|---|---|" + "---|" * len(hdr)]
        cells = []
        for h in hdr:
            mu, ci = r["cols"][h]
            cells.append(f"{mu:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else f"{mu:+.3f}")
        lines.append(f"| {r['trigger']} | {r['kind']} | {'yes' if r['audited'] else 'no'} | {r['n']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def decomposition(samples, min_n):
    """dQ at the main stop split into Phi (tower_phat) and critic parts, and the snapshot / play-count differences."""
    out = []
    by = defaultdict(list)
    for s in samples:
        for c in s["cands"][1:]:
            by[(s["trigger"], c["kind"])].append((s, c))
    names = ["q", "dg_stop:phi", "dg_stop:v"] + ["dg_stop:" + f for f in SNAP] + ["dg_stop:np0", "dg_stop:np1"]
    for (t, k), lst in sorted(by.items()):
        row = {"trigger": t, "kind": k, "cols": {}}
        for w in names:
            v = [(metric(s, c, w), s["mid"]) for s, c in lst]
            v = [x for x in v if x[0] is not None]
            if len(v) >= min_n:
                row["cols"][w] = (len(v), float(np.mean([x[0] for x in v])), boot_ci([x[0] for x in v], [x[1] for x in v]))
        if len(row["cols"]) > 1:
            out.append(row)
    return out


def md_decomp(rows):
    short = {"q": "dQ", "dg_stop:phi": "dPhi", "dg_stop:v": "dCritic", "dg_stop:own_p_lost": "d own princess lost",
             "dg_stop:own_k_lost": "d own king lost", "dg_stop:foe_p_lost": "d FOE princess lost",
             "dg_stop:foe_k_lost": "d foe king lost", "dg_stop:own_crowns_lost": "d own crowns lost",
             "dg_stop:foe_crowns_lost": "d foe crowns lost", "dg_stop:own_elixir": "d own elixir",
             "dg_stop:foe_elixir": "d foe elixir", "dg_stop:np0": "d own plays", "dg_stop:np1": "d FOE plays",
             "dg_stop:own_k_on": "d own king on", "dg_stop:foe_k_on": "d foe king on"}
    keys = [k for k in short if any(k in r["cols"] for r in rows)]
    lines = ["### Where dQ comes from (main stop, alt - chosen): Phi (towers) vs critic vs snapshot and play-count differences", "",
             "| trigger | alternative | " + " | ".join(short[k] for k in keys) + " |", "|---|---|" + "---|" * len(keys)]
    for r in rows:
        cells = []
        for k in keys:
            if k in r["cols"]:
                n, mu, ci = r["cols"][k]
                cells.append(f"{mu:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else f"{mu:+.3f}")
            else:
                cells.append("-")
        n = r["cols"]["q"][0] if "q" in r["cols"] else 0
        lines.append(f"| {r['trigger']} | {r['kind']} (n {n}) | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def slope_by_trigger(samples):
    from pipeline import cf_credit as CF
    by = defaultdict(list)
    for s in samples:
        by[s["trigger"]].append(s)
    lines = ["### Critic slope of the terminal return on the horizon return (audited samples; PLAN band [0.7, 1.3])", "",
             "| trigger | levels slope (n) | within-sample diffs slope (n) |", "|---|---|---|"]
    allr = CF.slope_audit(samples)
    for t, lst in sorted(by.items()):
        r = CF.slope_audit(lst)
        f = lambda d: "-" if d["slope"] is None else f"{d['slope']:.2f} +- {d['se']:.2f} ({d['n']})"
        lines.append(f"| {t} | {f(r['levels'])} | {f(r['diffs'])} |")
    f = lambda d: "-" if d["slope"] is None else f"{d['slope']:.2f} +- {d['se']:.2f} ({d['n']})"
    lines.append(f"| ALL | {f(allr['levels'])} | {f(allr['diffs'])} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--from-update", type=int, default=2)
    ap.add_argument("--min-n", type=int, default=15)
    ap.add_argument("--min-tick", type=int, default=0)
    ap.add_argument("--json", default=None)
    ap.add_argument("--sections", default="main,profile,decomp,slope")
    a = ap.parse_args()
    S = load(a.files, a.from_update, a.min_tick)
    sec = set(a.sections.split(","))
    cnt = defaultdict(int)
    for s in S:
        cnt[s["trigger"]] += 1
    print(f"# P4 audit tables: {len(S)} samples from {', '.join(Path(f).name for f in a.files)} (updates >= {a.from_update})\n")
    print("samples per trigger: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) + "\n")
    res = {}
    if "main" in sec:
        rows = table(S, "q", a.min_n)
        res["main"] = rows
        print(md([r for r in rows if r[2] in ("all", "phase", "score", "close_ot", "tesla")], "dQ at the main horizon: all / phase / score"))
        print(md([r for r in rows if r[2] not in ("all", "phase", "score", "close_ot", "tesla")], "dQ at the main horizon: trigger-specific splits"))
    if "profile" in sec:
        pr = profile(S, a.min_n)
        res["profile"] = pr
        print(md_profile(pr))
    if "decomp" in sec:
        dc = decomposition(S, a.min_n)
        res["decomp"] = dc
        print(md_decomp(dc))
    if "slope" in sec:
        print(slope_by_trigger(S))
    if a.json:
        Path(a.json).write_text(json.dumps(res, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")


if __name__ == "__main__":
    main()
