"""Summarise lost_census output: per unit row, events with a game re-acquire frame (G), how many the game re-acquired
before crforge (late), and the crforge wait S - t0. Only events on frames where the sim body sat exactly at the reader body.
    python3 lost_sum.py LOST.jsonl [FLAGS_INPUTS]"""
import collections, json, sys
ev = [json.loads(l) for l in open(sys.argv[1])]
by = collections.defaultdict(lambda: [0, 0, collections.Counter()])
late = []
for e in ev:
    if e.get('G') is None:
        continue
    k = e['name']
    by[k][0] += 1
    by[k][2][e['S'] - e['t0']] += 1
    if e['late']:
        by[k][1] += 1
        late.append(e)
print('events with a game re-acquire frame:', sum(v[0] for v in by.values()), '| crforge later than the game:', len(late))
for k, (n, l, w) in sorted(by.items(), key=lambda kv: -kv[1][0]):
    print('%-28s n=%4d late=%3d  crforge waits %s' % (k, n, l, dict(sorted(w.items()))))
print('late events:')
for e in late:
    print('  ', e['match'][10:], e['name'], 't0', e['t0'], 'S', e['S'], 'G', e['G'], 'Gprev', e['Gprev'], 'atk', e['atk'], 'load', e['load'])
