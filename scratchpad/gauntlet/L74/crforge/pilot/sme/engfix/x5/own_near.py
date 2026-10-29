"""ENG-FIX5: a record's own taps and plays (and own_delay) near tick T. python own_near.py INPUTS.jsonl MATCH T [W]"""
import json, sys
m, T = sys.argv[2], int(sys.argv[3]); W = int(sys.argv[4]) if len(sys.argv) > 4 else 60
for l in open(sys.argv[1]):
    r = json.loads(l)
    if not r['match'].endswith(m):
        continue
    print('my_side', r['my_side'], 'own_delay', r.get('own_delay'), 'build', r.get('game_build'))
    for t in r['own_taps']:
        if abs(t['tick'] - T) <= W:
            print(' tap', t)
    for p in r['plays']:
        if abs(p['tick'] - T) <= W:
            print(' play', {k: p[k] for k in p if k in ('side', 'kind', 'card', 'tick', 'run_ticks', 'source', 'x', 'y', 'given')})
