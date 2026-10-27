"""Planted checks for mech_torn.cross_ok (A2c-M). The true frame must pass; every planted change must fail.
python3 mech_torn_test.py PLAN.json FRAMES.jsonl ME T   (192935: me 1, T 382)"""
import copy, json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable
from mech_torn import cross_ok

plan_p, fr_p, me, t = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
f = load_frames(fr_p)[t]
o = {s['t']: s for s in run_batch([(runnable(json.load(open(plan_p))), t + 2, t - 1)], '/workspace/mech/work/mt%d' % os.getpid())[0]}
a, b = o[t], o[t + 1]
ok = cross_ok(f, a, b, me)
print('true frame', ok)
assert ok
# the crossed body: a recorded row at a t point whose hp is not that body's t hp
ta = {(e[3], e[4], e[5]): e for e in a['E'] if e[1] in 'TC'}
cr = [i for i, e in enumerate(f['E']) if (e[0], e[1], e[2]) in ta and e[4] != ta[(e[0], e[1], e[2])][6]]
other = sorted({e[6] for e in b['E'] if e[1] in 'TC'})
plants = {}
for i in cr:
    for name, fn in (('hp+1', lambda e: e.__setitem__(4, e[4] + 1)), ('hp-1', lambda e: e.__setitem__(4, e[4] - 1)),
                     ('x+1', lambda e: e.__setitem__(1, e[1] + 1)), ('y-1', lambda e: e.__setitem__(2, e[2] - 1)),
                     ('hp of another body at t+1', lambda e: e.__setitem__(4, next(h for h in other if h not in (e[4], ta[(e[0], e[1], e[2])][6]))))):
        g = copy.deepcopy(f)
        fn(g['E'][i])
        plants['%s row %d' % (name, i)] = g
g = copy.deepcopy(f); g['el'] += 1; plants['our elixir +1'] = g
g = copy.deepcopy(f); g['P'].append([1 - me, 9000, 16000, -1]); plants['extra projectile'] = g
g = copy.deepcopy(f)
mv = next(i for i, e in enumerate(g['E']) if i not in cr and e[3] != -1)
g['E'][mv][1] += 1; plants['another body moved 1'] = g
caught = 0
for name, g in plants.items():
    r = cross_ok(g, a, b, me)
    caught += not r
    print('%-32s %s' % (name, 'caught' if not r else 'MISSED'))
print('caught %d / %d' % (caught, len(plants)))
assert caught == len(plants)
