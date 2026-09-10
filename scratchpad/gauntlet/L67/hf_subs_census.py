"""L67m: which CARD SUBSTITUTIONS does the meta actually play against our deck? Census before curation.

The owner approved mining 7-of-8 decks for hogeq, with the condition that placements must not be confounded:
a substituted card's plays have to land on OUR corresponding slot (his example: a pro's electro-spirit
placements correspond to our ice-spirit). That mapping is only defensible for substitutions that are actually
role-equivalent, so this counts what the substitutions ARE before any alias table is written.

Reported per deck: for every side whose deck differs from ours in exactly one card, the (our card -> their
card) pair and its frequency. A pair that dominates and is role-equivalent (a 1-elixir spirit for a 1-elixir
spirit) is a candidate alias; a long tail of unrelated cards is not, and those replays should be dropped
rather than aliased.

usage: python scratchpad/gauntlet/L67/hf_subs_census.py [--deck hogeq]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import polars as pl

HF = Path("scratchpad/gauntlet/L67/hf/replays")
DECKS = {
    "hogeq": frozenset({"hog-rider", "firecracker", "mighty-miner", "tesla", "the-log", "earthquake",
                        "skeletons", "ice-spirit"}),
    "icebow": frozenset({"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log",
                         "skeletons"}),
}


def base(k: str) -> str:
    return re.sub(r"-ev\d+$", "", k)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default="hogeq")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    want = DECKS[a.deck]

    subs = collections.Counter()
    exact = 0
    sides = 0
    files = sorted(HF.glob("*.parquet"))
    for i, f in enumerate(files):
        try:
            df = pl.read_parquet(f, columns=["payload_json"])
        except Exception as exc:                                    # noqa: BLE001
            print(f"  read failed {f.name}: {exc}", flush=True)
            continue
        for raw in df["payload_json"].to_list():
            try:
                b = json.loads(raw)["battle"]
            except Exception:                                       # noqa: BLE001
                continue
            for side in ("team", "opponent"):
                pls = (b.get(side) or {}).get("players") or []
                if len(pls) != 1:
                    continue
                ks = {base(c["card_key"]) for c in pls[0].get("deck", [])}
                if len(ks) != 8:
                    continue
                sides += 1
                if ks == want:
                    exact += 1
                elif len(ks & want) == 7:
                    ours = next(iter(want - ks))
                    theirs = next(iter(ks - want))
                    subs[(ours, theirs)] += 1
        if i % 10 == 9:
            print(f"  {i+1}/{len(files)} files: exact {exact}, one-card-off {sum(subs.values())}", flush=True)

    print(f"\nDECK {a.deck}: {sides} sides scanned, {exact} EXACT, {sum(subs.values())} one-card-off")
    print("top substitutions (OUR card -> THEIR card):")
    for (ours, theirs), n in subs.most_common(20):
        print(f"  {ours:16s} -> {theirs:20s} {n:5d}")
    by_slot = collections.Counter()
    for (ours, _t), n in subs.items():
        by_slot[ours] += n
    print("\nwhich of OUR cards gets substituted:")
    for k, n in by_slot.most_common():
        print(f"  {k:16s} {n:5d}")
    if a.out:
        a.out.write_text(json.dumps({"deck": a.deck, "sides": sides, "exact": exact,
                                     "subs": {f"{o}->{t}": n for (o, t), n in subs.most_common()}},
                                    indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
