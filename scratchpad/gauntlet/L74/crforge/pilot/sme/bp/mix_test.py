"""Planted checks for SME_BP_MIXPH (A2c-BP). Run with the run's env plus SME_BP_MIXPH=1.
    python3 mix_test.py RUN_ON RUN_OFF OUT.txt
Frames that are torn_mixed in RUN_ON and div in RUN_OFF (same match, same tick) are re-analysed with one planted change
each; every planted change must leave the frame div:
  ph1   one hp -1 placeholder body moved 1 unit
  live1 one live body (hp > 0) moved 1 unit
  el1   our elixir + 1
  ph_xy one hp -1 placeholder body moved 1,000 units
  hp1   one live body (hp > 0) given hp + 1"""
import copy, json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
import sme_live
from sme import run_batch
from sme_live import load_frames, runnable, analyse
assert sme_live.MIX_PH, 'set SME_BP_MIXPH=1'
on, off, outp = sys.argv[1:4]
R = lambda r: {x['match']: x for x in map(json.loads, open(os.path.join(r, 'results.jsonl')))}  # noqa: E731
a, b = R(on), R(off)
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v9/inputs_rngfree.jsonl')}
cases = []
for m, r in a.items():
    if 'error' in r or m not in b or 'error' in b[m]:
        continue
    # torn ticks of a run list every torn class; a frame newly torn in ON (not torn in OFF) is the rule's
    new = sorted(set(r.get('torn_ticks', [])) - set(b[m].get('torn_ticks', [])))
    cases += [(m, t) for t in new]
w = open(outp, 'w')
tot = {}
for m, t in cases:
    plan = json.load(open(os.path.join(on, m, 'plan.json')))
    frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
    o = run_batch([(runnable(plan), t + 8, max(0, t - 8))], '/workspace/pilot/bp/work/mixt_%d' % os.getpid())[0]
    me = ME[m]
    base = analyse(o, frames, me, t - 6, t + 6)['cls'].get(t)
    res = {'match': m, 't': t, 'base': base}
    f = frames[t]
    ph = [i for i, e in enumerate(f['E']) if e[4] == -1]
    live = [i for i, e in enumerate(f['E']) if e[4] > 0 and e[3] != -1]
    for name, mod in (('ph1', lambda g, i: g['E'][i].__setitem__(1, g['E'][i][1] + 1)),
                      ('live1', lambda g, i: g['E'][i].__setitem__(1, g['E'][i][1] + 1)),
                      ('ph_xy', lambda g, i: g['E'][i].__setitem__(2, g['E'][i][2] + 1000)),
                      ('hp1', lambda g, i: g['E'][i].__setitem__(4, g['E'][i][4] + 1)),
                      ('el1', None)):
        idx = ph if name.startswith('ph') else live if name in ('live1', 'hp1') else [None]
        if not idx:
            res[name] = 'n/a'
            continue
        g = copy.deepcopy(f)
        g['E'] = [list(e) for e in g['E']]
        if mod is None:
            g['el'] += 1
        else:
            mod(g, idx[0])
        fr2 = dict(frames)
        fr2[t] = g
        res[name] = analyse(o, fr2, me, t - 6, t + 6)['cls'].get(t)
        tot.setdefault(name, [0, 0])
        tot[name][1] += 1
        tot[name][0] += res[name] == 'div'
    w.write(json.dumps(res) + '\n')
w.write('caught (div) / planted: ' + json.dumps(tot) + '\n')
print(open(outp).read())
