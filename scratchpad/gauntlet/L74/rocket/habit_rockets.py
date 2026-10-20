"""W10: Rocket habit counts in SIM rows that lack the opponent telemetry (e.g. CLX vs E4, O0 rows): per match unforced
princess Rockets (habits.rocket_princess - rocket_lethal) and the win rate by that count (ASSOCIATION).
    python habit_rockets.py NAME=DIR ..."""
import glob
import json
import sys
from pathlib import Path


def rows(root):
    fs = sorted(glob.glob(str(Path(root) / '*/D3/matches.jsonl'))) or sorted(glob.glob(str(Path(root) / 'D3/*/matches.jsonl')))
    for f in fs:
        for line in open(f, encoding='utf-8'):
            if line.strip():
                yield json.loads(line)


for spec in sys.argv[1:]:
    name, root = spec.split('=', 1)
    ms = [(r['habits']['rocket_princess'] - r['habits']['rocket_lethal'], r['habits']['rocket'], r['outcome'] == 'win')
          for r in rows(root) if r.get('habits') and not r.get('wall_truncated')]
    n = len(ms)
    print(f"{name}: n {n} | win {sum(w for *_, w in ms) / n:.3f} | Rockets/match {sum(a for _, a, _ in ms) / n:.2f} | "
          f"unforced princess Rockets/match {sum(u for u, *_ in ms) / n:.3f}")
    for lab, f in (('0', lambda u: u == 0), ('1', lambda u: u == 1), ('2+', lambda u: u >= 2)):
        sub = [w for u, _, w in ms if f(u)]
        if sub:
            print(f"   unforced {lab}: win {sum(sub) / len(sub):.3f} (n {len(sub)})")
