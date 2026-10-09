"""Is a game identical between base and retarget when log_air never touched it? (the paired design that runs retarget only
on the games where base played an only_air Log).  python det_check.py <sim dir>"""
import glob, json, os, sys
O = sys.argv[1]
rows = {}
for arm in ('base', 'retarget'):
    for s in ('evo', 'lad', 'air'):
        p = f'{O}/{arm}_{s}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r['arm'] == 'plain':
                    rows[(arm, s, r['tag'])] = r
touched, only_air_base = set(), set()
for arm in ('base', 'retarget'):
    for s in ('evo', 'lad', 'air'):
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                if arm == 'retarget' and x.get('why') == 'log_air':
                    touched.add((s, x['tag']))
                if arm == 'base' and x.get('play') and x.get('kind') == 'only_air':
                    only_air_base.add((s, x['tag']))
keys = sorted({(s, t) for (a, s, t) in rows if a == 'base'} & {(s, t) for (a, s, t) in rows if a == 'retarget'})
same = diff = 0
bad = []
for k in keys:
    a, b = rows[('base',) + k], rows[('retarget',) + k]
    sig = lambda r: (r['outcome'], r['tower_hp_diff'], r['end_tick'], r['plays_accepted'], r['opp_plays_accepted'], r['decisions'])
    if k in touched:
        continue
    if sig(a) == sig(b):
        same += 1
    else:
        diff += 1
        bad.append((k, sig(a), sig(b)))
print(f'paired {len(keys)}; touched by retarget {len([k for k in keys if k in touched])}; untouched identical {same}, untouched different {diff}')
print('base games with an only_air Log play:', len([k for k in keys if k in only_air_base]), ' of those touched by retarget:',
      len([k for k in keys if k in only_air_base and k in touched]), ' touched but base had none:', len([k for k in keys if k in touched and k not in only_air_base]))
for b in bad[:5]:
    print(' ', b)
