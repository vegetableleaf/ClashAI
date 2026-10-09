"""Double-casts in a SIM run's fire logs (fire_log_s0.py).  python double_cast.py <sim dir> <arm> [<sim dir> <arm> ...]
(1) fire-based (every run): two lethal-rule FIRES at the same enemy princess in one match, the second within the first's
    hit ticks + 26 look-ahead + 20 margin (Rocket 112, Log 103 ticks). Split into same-card pairs (Rocket then Rocket
    1.5 s later: the first was never cast -- one Rocket per deck, it is still in hand; refused / unlanded plays at the
    300 s tower-drain end) and cross-card pairs (Rocket then Log, Log then Rocket = the verifier's double-cast).
(2) landing-based (runs with lands_*.jsonl): two ACCEPTED lethal casts at the same princess (lane of the cast cell)
    within the first's window of landing ticks -- the definitive count."""
import glob, json, sys
from collections import defaultdict

WIN = {'lethal_rocket': 66 + 26 + 20, 'lethal_log': 57 + 26 + 20}
args = sys.argv[1:]
for O, arm in zip(args[::2], args[1::2]):
    fires, lands = defaultdict(list), defaultdict(list)
    for s in ('evo', 'lad'):
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                fires[(s, x['tag'])].append(x)
        for f in glob.glob(f'{O}/fires_{arm}_{s}/lands_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                lands[(s, x['tag'])].append(x)
    same, cross = [], []
    for k, v in fires.items():
        v.sort(key=lambda x: x['t_sec'])
        for a, b in zip(v, v[1:]):
            if a['target']['lane'] == b['target']['lane'] and (b['t_sec'] - a['t_sec']) / .05 <= WIN[a['why']]:
                (same if a['why'] == b['why'] else cross).append((k, a['why'], round(a['t_sec'], 2), b['why'],
                                                                  round(b['t_sec'], 2), a['target']['lane']))
    print(f'{O} {arm}: fires {sum(map(len, fires.values()))} in {len(fires)} matches; fire-based double-casts: '
          f'cross-card {len(cross)} in {len({p[0] for p in cross})} matches, same-card {len(same)} '
          f'(first never cast)')
    for p in sorted(cross):
        print('    cross', p)
    if lands:
        acc = {k: sorted((x for x in v if x['accepted']), key=lambda x: x['land']) for k, v in lands.items()}
        dbl = [(k, a['why'], a['land'], b['why'], b['land']) for k, v in acc.items() for a, b in zip(v, v[1:])
               if ((a['cell'] % 36) < 18) == ((b['cell'] % 36) < 18) and b['land'] - a['land'] <= WIN[a['why']]]
        print(f'  landing-based: lethal casts {sum(map(len, lands.values()))}, accepted '
              f'{sum(map(len, acc.values()))}; ACCEPTED double-casts {len(dbl)} {dbl[:10]}')
