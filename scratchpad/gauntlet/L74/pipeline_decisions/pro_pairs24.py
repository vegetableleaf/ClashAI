"""Pro reference for the --pipeline-decisions A/B: consecutive own plays of the pros within the 1.2 s pending window (<= 24 ticks) and the
older <= 35 reference, from the defence worker's normalised pros (mistakes.py's source, read only; ticks = EXECUTION ticks).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/pipeline_decisions/pro_pairs24.py [PROS_PKL] [OUT.json]
"""
import gzip
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

DEFAULT = r"C:\Users\benpe\ClashBot\.claude\worktrees\agent-af3c232b452e8ef86\scratchpad\gauntlet\L74\defense\data\pros.pkl.gz"
src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
out_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("pro_pairs24.json"))
PH = ((0, 2400), (2400, 3600), (3600, 10 ** 9))
base = lambda c: c.split("@")[0].replace("-", "_").split("_evo")[0].lower()      # noqa: E731

with gzip.open(src) as fh:
    sides = pickle.load(fh)
plays = 0
ph_plays, ph_min = [0, 0, 0], [0.0, 0.0, 0.0]
gaps, pairs24, pairs35 = [], Counter(), Counter()
for m in sides:
    P = sorted((p[1], base(p[2])) for p in m["P"])
    end = m["end"]
    for i, (lo, hi) in enumerate(PH):
        ph_min[i] += max(0, min(end, hi) - lo) / 1200.0
        ph_plays[i] += sum(lo <= t < hi for t, _ in P)
    plays += len(P)
    for (t0, a), (t1, b) in zip(P, P[1:]):
        g = t1 - t0
        gaps.append(g)
        if g <= 35:
            pairs35[f"{a}->{b}"] += 1
        if g <= 24:
            pairs24[f"{a}->{b}"] += 1
n, g = len(sides), np.array(gaps)
def second(pr):
    tot = max(sum(pr.values()), 1)
    return {c: round(sum(v for k, v in pr.items() if k.split("->")[1] == c) / tot, 3) for c in sorted({k.split("->")[1] for k in pr})}


out = dict(sides=n, plays_per_min={p: round(ph_plays[i] / ph_min[i], 2) for i, p in enumerate(("1x", "2x", "OT"))},
           plays_per_match=round(plays / n, 2),
           gap_ticks_quantiles={q: float(np.percentile(g, q)) for q in (5, 10, 25, 50)},
           share_gap_le_24=round(float((g <= 24).mean()), 4), share_gap_le_35=round(float((g <= 35).mean()), 4),
           share_gap_le_20=round(float((g <= 20).mean()), 4),
           pairs_le_24_per_match=round(sum(pairs24.values()) / n, 3), pairs_le_35_per_match=round(sum(pairs35.values()) / n, 3),
           top_pairs_le_24_per_match={k: round(v / n, 3) for k, v in pairs24.most_common(14)},
           second_mix_le_24=second(pairs24), second_mix_le_35=second(pairs35),
           rocket_tornado_le_24_per_match=round(pairs24["rocket->tornado"] / n, 4))
json.dump(out, open(out_path, "w"), indent=1)
print(json.dumps(out, indent=1))
