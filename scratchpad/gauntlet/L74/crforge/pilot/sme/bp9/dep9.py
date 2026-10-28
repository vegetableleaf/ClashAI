"""dep9.py VAR_ROWS.jsonl TRACEDIR OUT.log -- A2c-9R lead 1: does a unit's deploy end, birth or death in the step make the game's
ground walkers re-search? Joins bp6's fr2 rows (a fresh search from the start cell to the held goal whose pure step differs from
crforge's step; outcome at the next frame: crforge = held route, var = fresh route) with per-tick trigger sets read from AimRun5
traces (C rows: state 4 = deploying). Trigger at crforge tick t+d, d in {0, 1} (the game one tick earlier than crforge at d=1).
Rows: clean and exact the frame before only."""
import collections, glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
rows_p, td, outp = sys.argv[1], sys.argv[2], sys.argv[3]


def triggers(m):
    f = glob.glob(os.path.join(td, 'live_play_' + m + '.o.jsonl'))
    if not f: return m, None
    trig = collections.defaultdict(set)  # t -> {(kind, side)}
    side = {}
    prev = None
    for l in open(f[0]):
        o = json.loads(l)
        cur = {c[0]: c for c in o['C']}
        t = o['t']
        for i, c in cur.items(): side[i] = c[2]
        if prev is not None:
            for i, c in cur.items():
                if i not in prev: trig[t].add(('born', c[2]))
                elif prev[i][7] == 4 and c[7] != 4: trig[t].add(('depend', c[2]))
            for i, c in prev.items():
                if i not in cur: trig[t].add(('gone', c[2]))
        prev = cur
    return m, (dict(trig), side)


rows = collections.defaultdict(list)
for l in open(rows_p):
    if '"fr2"' not in l: continue
    x = json.loads(l)
    if x['pre'] and x['clean']: rows[x['m']].append(x)
with ProcessPoolExecutor(32) as ex:
    T = dict(ex.map(triggers, sorted(rows)))
c = collections.Counter()
hits = []
for m, rs in rows.items():
    if T.get(m) is None: continue
    trig, side = T[m]
    for x in rs:
        s = side.get(x['id'])
        for d in (0, 1):
            for kind, ks in trig.get(x['t'] + d, ()):
                key = (kind, 'same' if ks == s else 'other', d)
                c[key + (x['out'],)] += 1
                if x['out'] != 'crforge' or x['tgt']: hits.append((key, x['m'], x['t'], x['id'], x['name'], x['out']))
        c[('all', '', 0, x['out'])] += 1
with open(outp, 'w') as f:
    keys = sorted({k[:3] for k in c})
    for k in keys:
        f.write('%-8s %-5s d=%d  crforge %7d  var %4d  neither %4d  gone %4d\n' % (k + tuple(c[k + (o,)] for o in ('crforge', 'var', 'neither', 'gone'))))
    for h in sorted(set(hits)): f.write('HIT %s\n' % (h,))
print(open(outp).read()[:4000])
