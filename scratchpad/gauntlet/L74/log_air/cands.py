"""Candidate games (base played an only_air Log) in the VM-backup base results.  python cands.py <backup log_air/sim dir>"""
import glob, json, os, sys
from collections import Counter
O = sys.argv[1]
for s in ('evo', 'lad', 'air'):
    base, cand, plays = {}, set(), Counter()
    for d in (f'base_{s}', f'base_{s}_b9'):
        p = f'{O}/{d}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                base[r['tag']] = r['outcome']
        for f in glob.glob(f'{O}/fires_{d}/fires_*.jsonl'):
            for line in open(f):
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                if x.get('play'):
                    if x['tag'] in base or True:
                        plays[x['kind']] += 1
                    if x['kind'] == 'only_air':
                        cand.add(x['tag'])
    done = {t for t in cand if t in base}
    print(s, 'base games', len(base), dict(Counter(base.values())), 'Log plays by corridor class', dict(plays),
          'candidates (finished)', sorted(int(t.split(':')[-1]) for t in done))
