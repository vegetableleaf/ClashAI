"""Planted checks for SME_BP_SNAP (A2c-BP). python3 snap_test.py RUN_ON RUN_OFF OUT.txt  (run env, SME_HP_PLACEHOLDER=1)
Frames torn in RUN_ON and not in RUN_OFF are re-tested with one planted change each; every change must make the frame
fail the in-step test: live1 a live body moved 1 unit; hp1 a live body hp + 1; el1 our elixir + 1; ph1 a hp -1
placeholder body moved 1 unit; proj1 a projectile moved 1 unit."""
import copy, json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
import bp_snap
from sme import run_batch
from sme_live import load_frames, runnable
on, off, outp = sys.argv[1:4]
R = lambda r: {x['match']: x for x in map(json.loads, open(os.path.join(r, 'results.jsonl')))}  # noqa: E731
a, b = R(on), R(off)
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v9/inputs_rngfree.jsonl')}
cases = [(m, t) for m, r in a.items() if 'error' not in r and m in b and 'error' not in b[m]
         for t in sorted(set(r.get('torn_ticks', [])) - set(b[m].get('torn_ticks', [])))]
w = open(outp, 'w')
tot = {}
for m, t in cases:
    plan = runnable(json.load(open(os.path.join(on, m, 'plan.json'))))
    wd = '/workspace/pilot/bp/work/snapt_%d' % os.getpid()
    o = run_batch([(plan, t + 3, t)], wd)[0]
    by = {x['t']: x for x in o}
    states = [by[t]] + bp_snap.snapshots(plan, [t + 1], t + 3, wd).get(t + 1, []) + [by[t + 1]]
    f = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)[t]
    me = ME[m]
    res = {'match': m, 't': t, 'base': bp_snap.in_step(f, states, me)}
    live = [i for i, e in enumerate(f['E']) if e[4] > 0 and e[3] != -1]
    ph = [i for i, e in enumerate(f['E']) if e[4] == -1]
    for name, idx, mod in (('live1', live, lambda g, i: g['E'][i].__setitem__(1, g['E'][i][1] + 1)),
                           ('hp1', live, lambda g, i: g['E'][i].__setitem__(4, g['E'][i][4] + 1)),
                           ('ph1', ph, lambda g, i: g['E'][i].__setitem__(1, g['E'][i][1] + 1)),
                           ('proj1', list(range(len(f['P']))), lambda g, i: g['P'][i].__setitem__(1, g['P'][i][1] + 1)),
                           ('el1', [None], None)):
        if not idx:
            res[name] = 'n/a'
            continue
        g = copy.deepcopy(f)
        g['E'] = [list(e) for e in g['E']]
        g['P'] = [list(p) for p in g['P']]
        if mod is None:
            g['el'] += 1
        else:
            mod(g, idx[0])
        ok = bp_snap.in_step(g, states, me)
        res[name] = 'caught' if not ok else 'MISSED'
        tot.setdefault(name, [0, 0])
        tot[name][1] += 1
        tot[name][0] += not ok
    w.write(json.dumps(res) + '\n')
w.write('caught / planted: ' + json.dumps(tot) + '\n')
w.close()
print(open(outp).read())
