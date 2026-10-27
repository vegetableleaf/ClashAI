"""Target-lost events in clean regions: the event's window [t0 - 10, S + 2] lies before the match's first divergence
(bpA results), or the match is exact. python3 lost_clean.py LOST.jsonl RUNDIR"""
import collections, json, os, sys
ev = [json.loads(l) for l in open(sys.argv[1])]
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[2], 'results.jsonl'))}
c = collections.Counter()
late = []
for e in ev:
    r = res.get(e['match'], {})
    fd = r.get('first_div')
    if 'error' in r or e.get('G') is None:
        continue
    clean = fd is None or e['S'] + 2 < fd
    c[(clean, e['late'])] += 1
    if clean and e['late']:
        late.append(e)
print('(clean, late) counts:', dict(c))
byn = collections.Counter(e['name'] for e in late)
print('clean late by unit:', dict(byn))
for e in late[:40]:
    print('  ', e['match'][10:], e['name'], 't0', e['t0'], 'S', e['S'], 'G', e['G'], 'Gprev', e['Gprev'], 'atk', e['atk'], 'load', e['load'])
