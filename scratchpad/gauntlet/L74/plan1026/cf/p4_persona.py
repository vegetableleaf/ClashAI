"""Persona fork test (HUMANLIKE.md 10.2 (c)): does the sign of the fork contrast at post-failed-X-Bow states depend on the
opponent persona?  Input = CF_DUMP jsonl files recorded with cf_diag (match "opp": league spec + drawn style).

    python p4_persona.py DUMP.jsonl [...] [--decks DECKS.json ...] [--trigger xbow_after_fail] [--from-update 2] [--json OUT]

Contrasts per sample (Q = K-mean return, within-sample, so CRN-paired): again - wait (xbow_reach vs wait), rocket - wait
(rocket_princess vs wait), rocket - again. "wait" is the wait alternative, or the chosen action when the policy itself waited.
Personas: opponent type (self-play copy / human-timing exploiter ...), the drawn style dims (bank, aggression, lane bias,
temperature, spell delay) split at their range middle, and the opponent deck archetype (archetypes.classify of the deck named
in the spec; --decks maps deck names to card lists). For every dimension: each level's mean and 90% cluster-bootstrap CI (clusters
= matches) and the DIFFERENCE between the two halves with its CI; 'sign change' = the two levels' means have opposite signs with
both CIs excluding 0."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_audit as A                                                       # noqa: E402

CONTRASTS = (("again-wait", "again", "wait"), ("rocket-wait", "rocket", "wait"), ("rocket-again", "rocket", "again"))
MID = {"bank": 2.0, "aggression": 0.0, "lane_bias": 0.0, "temperature": 1.0, "spell_delay": 2}


def resolve(s, name):
    ch = s["cands"][0]
    by = {c["kind"]: c for c in s["cands"][1:]}
    if name == "wait":
        return by.get("wait") or (ch if not ch["play"] else None)
    if name == "again":
        return by.get("xbow_reach")
    if name == "rocket":
        return by.get("rocket_princess")


def contrast(s, a, b):
    ca, cb = resolve(s, a), resolve(s, b)
    if ca is None or cb is None:
        return None
    return A.paired_k(ca, cb, lambda c: c["q"])


def personas(s, decks, classify):
    o = s.get("opp")
    out = [("all", "all")]
    if not o:
        return out
    out.append(("type", o["opp"].get("type") or "?"))
    st = o.get("style") or {}
    for k, mid in MID.items():
        if k in st:
            out.append((k, f"{k} >= {mid}" if st[k] >= mid else f"{k} < {mid}"))
    if decks and o.get("opp_deck") in decks:
        out.append(("archetype", classify(decks[o["opp_deck"]])))
    return out


def load_decks(paths):
    """deck name -> engine card list: census decks are named r<rank> (decks_rl.json 'decks'), live-train decks by their 'name'."""
    d = {}
    for p in paths:
        x = json.load(open(p, encoding="utf-8"))
        for r in x.get("decks", []):
            if r.get("engine"):
                d[r.get("name") or f"r{r['rank']}"] = r["engine"]
        for r in x.get("extra", []):
            if r.get("engine"):
                d[r["name"]] = r["engine"]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--trigger", default="xbow_after_fail")
    ap.add_argument("--from-update", type=int, default=2)
    ap.add_argument("--decks", nargs="*", default=[])
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    from pipeline import archetypes as AR
    decks = load_decks(a.decks)
    S = [s for s in A.load(a.files, a.from_update) if s["trigger"] == a.trigger]
    print(f"# Persona fork test: trigger {a.trigger}, {len(S)} samples, {len({s['mid'] for s in S})} matches "
          f"(opponent meta present in {sum(1 for s in S if s.get('opp'))})\n")
    res = {}
    for cname, ca, cb in CONTRASTS:
        cells = defaultdict(lambda: ([], []))
        for s in S:
            v = contrast(s, ca, cb)
            if v is None:
                continue
            for dim, lab in personas(s, decks, AR.classify):
                cells[(dim, lab)][0].append(v)
                cells[(dim, lab)][1].append(s["mid"])
        print(f"## {cname}  (mean dQ, 90% cluster CI; * = CI excludes 0)\n")
        print("| dimension | level | n | mean | 90% CI |\n|---|---|---|---|---|")
        rows = {}
        for (dim, lab), (v, m) in sorted(cells.items()):
            if len(v) < a.min_n:
                continue
            ci = A.boot_ci(v, m)
            rows[(dim, lab)] = (v, m, float(np.mean(v)), ci)
            star = "" if ci[0] <= 0 <= ci[1] else " *"
            print(f"| {dim} | {lab} | {len(v)} | {np.mean(v):+.3f}{star} | [{ci[0]:+.3f}, {ci[1]:+.3f}] |")
        print("\nHalf-vs-half differences (level A minus level B), 90% CI; sign change flagged:\n")
        print("| dimension | A | B | diff | 90% CI | sign change |\n|---|---|---|---|---|---|")
        dims = sorted({d for d, _ in rows if d != "all"})
        out = []
        for d in dims:
            levels = sorted(l for (dd, l) in rows if dd == d)
            for i in range(len(levels)):
                for j in range(i + 1, len(levels)):
                    (v1, m1, mu1, ci1), (v2, m2, mu2, ci2) = rows[(d, levels[i])], rows[(d, levels[j])]
                    # difference CI: bootstrap matches jointly (clusters shared across levels are rare: independent resampling is conservative enough)
                    rng = np.random.default_rng(0)
                    def bm(v, m):
                        v, m = np.asarray(v), np.asarray(m)
                        u, inv = np.unique(m, return_inverse=True)
                        s_, c_ = np.bincount(inv, v), np.bincount(inv).astype(float)
                        idx = rng.integers(0, len(u), (2000, len(u)))
                        return s_[idx].sum(1) / c_[idx].sum(1)
                    dd = bm(v1, m1) - bm(v2, m2)
                    ci = [float(np.percentile(dd, 5)), float(np.percentile(dd, 95))]
                    flip = (mu1 * mu2 < 0) and (ci1[0] > 0 or ci1[1] < 0) and (ci2[0] > 0 or ci2[1] < 0)
                    out.append((d, levels[i], levels[j], mu1 - mu2, ci, flip))
                    star = "" if ci[0] <= 0 <= ci[1] else " *"
                    print(f"| {d} | {levels[i]} | {levels[j]} | {mu1 - mu2:+.3f}{star} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {'YES' if flip else 'no'} |")
        print()
        res[cname] = {"levels": {f"{d}|{l}": [len(r[0]), r[2], r[3]] for (d, l), r in rows.items()}, "diffs": out}
    if a.json:
        Path(a.json).write_text(json.dumps(res, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")


if __name__ == "__main__":
    main()
