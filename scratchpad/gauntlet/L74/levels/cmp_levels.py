"""One checkpoint, the same paired seeds, level 11 vs live levels (habit_eval.sh outputs):

    python cmp_levels.py DIR_L11 DIR_LIVE      (each a gap.py --out dir with D3/matches.jsonl)

Checks every pair met the same opponent deck and side, then prints both win rates, the paired delta
(validate.paired_drift: 10,000 bootstrap draws within census and side) and the live-levels win rate by opponent tower level."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'heroiw')]
from validate import paired_drift  # noqa: E402


def load(d):
    return [json.loads(x) for x in (Path(d) / 'D3' / 'matches.jsonl').read_text().splitlines() if x.strip()]


a, b = load(sys.argv[1]), load(sys.argv[2])
ka = {(r['census'], r['seed']): (r['opp_deck'], r['learner_side']) for r in a}
kb = {(r['census'], r['seed']): (r['opp_deck'], r['learner_side']) for r in b}
assert ka == kb, 'the two runs did not meet the same opponents'
d = paired_drift(a, b, expected=len(a))
w = lambda rs: sum(r['outcome'] == 'win' for r in rs)                     # noqa: E731
print(f"level 11: {w(a)}/{len(a)}; live levels: {w(b)}/{len(b)}; live - L11 {d['delta_pp']:+.2f} pp "
      f"[{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}] ({d['pairs']} pairs)")
by = defaultdict(list)
for r in b:
    by[r['levels']['opp']['tower']].append(r)
print('live levels, by opponent tower level:', {k: f'{w(v)}/{len(v)}' for k, v in sorted(by.items())})
