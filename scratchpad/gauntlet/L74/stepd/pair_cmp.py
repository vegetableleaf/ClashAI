"""Paired promotion-eval delta of B vs A (heroiw/validate.paired_drift: within census x learner side, 10,000 draws) per seed
set and pooled.
    python pair_cmp.py A_TEMPLATE B_TEMPLATE        templates hold {s} for the seed, e.g. .../c3_ctl_{s}/D3/matches.jsonl
Seed sets: std = 741200 + 742000, fresh = 743000 + 744000."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "heroiw"))
from validate import paired_drift  # noqa: E402

SETS = {"std": (741200, 742000), "fresh": (743000, 744000)}


def load(tpl, seeds):
    out = []
    for s in seeds:
        p = Path(tpl.format(s=s))
        if not p.is_file():
            return None
        out += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return out if len(out) == 480 * len(seeds) else None


def main(a, b):
    got = {}
    for name, seeds in SETS.items():
        ra, rb = load(a, seeds), load(b, seeds)
        if ra is None or rb is None:
            print(f"{name}: incomplete (A {'ok' if ra else 'missing'}, B {'ok' if rb else 'missing'})")
            continue
        got[name] = (ra, rb)
        d = paired_drift(ra, rb, expected=len(ra))
        print(f"{name}: A {sum(r['outcome'] == 'win' for r in ra)}/{len(ra)}  B {sum(r['outcome'] == 'win' for r in rb)}/{len(rb)}"
              f"  B - A {d['delta_pp']:+.2f} pp [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]")
    if len(got) == 2:
        ra = got["std"][0] + got["fresh"][0]
        rb = got["std"][1] + got["fresh"][1]
        d = paired_drift(ra, rb, expected=len(ra))
        print(f"pooled: B - A {d['delta_pp']:+.2f} pp [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]")


if __name__ == "__main__":
    main(*sys.argv[1:3])
