"""Per candidate game: base vs retarget vs block outcome, and the log_air touches.  python cases.py <arms dir> <base dir>"""
import glob, json, sys
A, B = sys.argv[1], sys.argv[2]


def rows(p):
    out = {}
    for f in glob.glob(p):
        for l in open(f):
            r = json.loads(l)
            out[r['tag']] = (r['outcome'], r['tower_hp_diff'], r['end_tick'])
    return out


for s in ('evo', 'lad', 'air'):
    base = rows(f'{B}/base_{s}*/matches.jsonl')
    for arm in ('retarget', 'block'):
        res = rows(f'{A}/{arm}_{s}_b*/matches.jsonl')
        for t, v in sorted(res.items()):
            print(s, arm, t, 'base', base.get(t), '->', v)
        for f in glob.glob(f'{A}/fires_{arm}_{s}_b*/fires_*.jsonl'):
            for l in open(f):
                x = json.loads(l)
                if x.get('why') == 'log_air':
                    print('   touch', s, arm, x['tag'], 't=%.0f' % x['t_sec'], 'play', x['play'], x.get('cell_kind'), x.get('kind'), 'ground_elixir', x.get('ground_value'))
