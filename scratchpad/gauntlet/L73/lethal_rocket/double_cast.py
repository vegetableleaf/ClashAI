"""Double-casts in a SIM run's fire logs (fire_log_s0.py): two lethal-rule fires (Rocket or Log) at the SAME enemy princess
in one match while the first is still in flight (second fire within the first's hit ticks + 26 look-ahead + 20 margin:
Rocket 112, Log 103 ticks of model-board time).  python double_cast.py <sim dir> <arm> [<sim dir> <arm> ...]"""
import glob, json, sys
from collections import defaultdict

WINDOW = {'lethal_rocket': (66 + 26 + 20) * .05, 'lethal_log': (57 + 26 + 20) * .05}
args = sys.argv[1:]
for O, arm in zip(args[::2], args[1::2]):
    fires = defaultdict(list)
    for s in ('evo', 'lad'):
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                fires[(s, x['tag'])].append(x)
    pairs = []
    for k, v in fires.items():
        v.sort(key=lambda x: x['t_sec'])
        for a, b in zip(v, v[1:]):
            if a['target']['lane'] == b['target']['lane'] and b['t_sec'] - a['t_sec'] <= WINDOW[a['why']]:
                pairs.append((k, a['why'], round(a['t_sec'], 2), b['why'], round(b['t_sec'], 2), a['target']['lane']))
    print(f'{O} {arm}: fires {sum(map(len, fires.values()))} in {len(fires)} matches; double-casts {len(pairs)} in '
          f'{len({p[0] for p in pairs})} matches')
    for p in sorted(pairs)[:40]:
        print('   ', p)
