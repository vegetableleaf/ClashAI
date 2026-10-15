"""Paired comparison on the LIVE-MIRRORED SIM eval (live_eval_pod.sh outputs): every candidate's D3 vs the base (default: the
live model f1u65), 960 paired games (seeds 741200 + 742000, keys (census, seed)), + per-archetype split (beatdown vs rest).
    python live_cmp.py LIVEEVAL_DIR [--base f1u65] [NAME ...]      (default: every *_741200 dir with a 742000 twin)
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path[:0] = ["C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/heroiw", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend"]
from validate import paired_drift  # noqa: E402
import archetypes as A  # noqa: E402


def load(d, name, arm="D3"):
    rows = []
    for s in (741200, 742000):
        p = Path(d) / f"{name}_{s}" / arm / "matches.jsonl"
        if not p.is_file():
            return None
        rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("names", nargs="*"); ap.add_argument("--base", default="f1u65")
    a = ap.parse_args()
    names = a.names or sorted({p.name[:-7] for p in Path(a.dir).glob("*_741200")})
    base = load(a.dir, a.base)
    if base is None:
        sys.exit(f"base {a.base} not complete in {a.dir}")
    bw = sum(r["outcome"] == "win" for r in base)
    print(f"base {a.base}: {bw}/{len(base)} ({100*bw/len(base):.1f}%)  [live-mirrored pool, D3]")
    beat = {(r["census"], r["seed"]): bool({A.canon(c) for c in r["opp_deck"]} & (A.TANK | {"threemusketeers"})) for r in base}
    bk = {(r["census"], r["seed"]): r for r in base}
    for n in names:
        if n == a.base:
            continue
        rows = load(a.dir, n)
        if rows is None:
            print(f"{n:16} incomplete"); continue
        w = sum(r["outcome"] == "win" for r in rows)
        try:
            d = paired_drift(base, rows, expected=len(base))
        except ValueError:                                   # a seed set still running (partial matches.jsonl)
            print(f"{n:16} incomplete ({len(rows)} rows)"); continue
        split = []
        for lab, keep in (("beatdown", True), ("rest", False)):
            x = [(r["outcome"] == "win") - (bk[(r["census"], r["seed"])]["outcome"] == "win")
                 for r in rows if beat[(r["census"], r["seed"])] == keep]
            m = sum(x) / len(x); se = math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1) / len(x))
            split.append(f"{lab} {100*m:+.1f}±{196*se:.1f}")
        print(f"{n:16} {w}/{len(rows)} ({100*w/len(rows):.1f}%)  vs {a.base} {d['delta_pp']:+.2f} pp "
              f"[{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]   {' | '.join(split)}")


if __name__ == "__main__":
    main()
