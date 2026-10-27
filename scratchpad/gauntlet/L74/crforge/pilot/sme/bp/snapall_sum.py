"""Summarise snapck output on the torn / isolated frames: per class, how many frames equal a crforge in-step state of
step t+1 (fits), by the state's event. python3 snapall_sum.py LIST SNAP.jsonl [SNAP.jsonl ...]"""
import collections, json, sys
cls = {(l.split()[0], int(l.split()[1])): l.split()[2] for l in open(sys.argv[1]) if l.strip()}
c, ev = collections.Counter(), collections.Counter()
nofit = []
for p in sys.argv[2:]:
    for l in open(p):
        r = json.loads(l)
        k = cls.get((r['match'], r['t']), '?')
        fit = bool(r['fits'])
        c[(k, fit)] += 1
        if fit:
            ev[(k, r['fits'][0].split(':')[-1])] += 1
        else:
            nofit.append((k, r['match'][10:], r['t'], r['best'][0] if r['best'] else None, (r['best'] or [None, None])[1]))
for k, v in sorted(c.items()):
    print(k, v)
print('first fitting state by event:', dict(sorted(ev.items())))
for x in sorted(nofit):
    print('  no fit', x)
