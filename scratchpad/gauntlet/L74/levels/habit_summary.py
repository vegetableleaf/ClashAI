"""Per-run summary of search_s0 --habit-log rows (gap.py / live_eval_pod.sh matches.jsonl):

    python habit_summary.py RUN_DIR_OR_MATCHES_JSONL [...]     (a dir: every */D3/matches.jsonl and */matches.jsonl below)

Per input: matches, X-Bow in the opening hand, offensive X-Bow among the first two plays (all / given in hand), per match
means of Rockets, Rockets on an alive enemy princess (the lower one, bodyless), finisher-forced Rockets / Logs, late
offensive X-Bows / Rockets / Tornados, and the X-Bow board-y histogram (the offensive cut is search_s0.XBOW_BRIDGE_Y)."""
import json
import sys
from collections import Counter
from pathlib import Path


def rows(p):
    p = Path(p)
    files = [p] if p.is_file() else sorted(p.glob('**/matches.jsonl'))
    return [r for f in files for r in map(json.loads, f.read_text().splitlines()) if 'habits' in r]


for arg in sys.argv[1:]:
    hs = [r['habits'] for r in rows(arg)]
    n = len(hs)
    if not n:
        print(arg, 'no habit rows')
        continue
    hand = [h for h in hs if h['xbow_open_hand']]
    mean = lambda k: sum(h[k] for h in hs) / n                                      # noqa: E731
    late = lambda k: sum(h['late'][k] for h in hs) / n                              # noqa: E731
    print(f"{arg}: {n} matches; X-Bow in opening hand {len(hand) / n:.3f}; offensive X-Bow in first 2 plays "
          f"{sum(h['xbow_off_first2'] for h in hs) / n:.3f} (given in hand {sum(h['xbow_off_first2'] for h in hand) / max(1, len(hand)):.3f})")
    print('  per match: ' + ', '.join(f'{k} {mean(k):.2f}' for k in ('xbow', 'xbow_off', 'rocket', 'rocket_princess',
          'rocket_princess_lower', 'rocket_princess_bodyless', 'rocket_lethal', 'log_lethal', 'tornado')))
    print('  late (tick >= 2400) per match: ' + ', '.join(f'{k} {late(k):.2f}' for k in hs[0]['late']))
    print('  X-Bow board y:', dict(sorted(Counter(y for h in hs for y in h['xbow_y']).items())))
