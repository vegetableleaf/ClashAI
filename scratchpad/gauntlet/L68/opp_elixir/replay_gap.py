"""How soon can the same side re-play the same card? (sets the swarm-join window: bodies of a card within
that window of its last play cannot be a new play). All corpus_v6 replays, accepted log plays."""
import collections, glob, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
gaps = []
for deck in ("icebow", "hogeq"):
    for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json"))):
        last = {}
        for e in sorted((e for e in json.load(open(f))["log"] if e.get("accepted")), key=lambda e: e["tick"]):
            k = (e["side"], e["card"])
            if k in last:
                gaps.append(e["tick"] - last[k])
            last[k] = e["tick"]
gaps.sort()
n = len(gaps)
print("same-side same-card re-play gaps:", n)
for q in (0, 0.0001, 0.001, 0.01, 0.05, 0.5):
    print(f"  quantile {q}: {gaps[int(q * (n - 1))]} ticks")
for w in (20, 40, 60, 80, 100, 120):
    print(f"  re-plays within {w} ticks: {sum(g <= w for g in gaps)} ({100 * sum(g <= w for g in gaps) / n:.3f}%)")
