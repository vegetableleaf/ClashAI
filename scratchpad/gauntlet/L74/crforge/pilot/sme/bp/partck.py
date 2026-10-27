"""For a div frame t: recorded objects held by neither sim t nor t+1, against one-step extrapolations of sim objects:
position pos_t + (pos_t - pos_t-1), hp hp_t - (hp_t-1 - hp_t). python3 partck.py RUN MATCH T"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable, canon_live, repr_rows
run, m, t = sys.argv[1], sys.argv[2], int(sys.argv[3])
me = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v9/inputs_rngfree.jsonl')}[m]
plan = json.load(open(os.path.join(run, m, 'plan.json')))
frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
o = run_batch([(runnable(plan), t + 3, t - 2)], '/workspace/pilot/bp/work/part_%d' % os.getpid())[0]
by = {s['t']: s for s in o}
rows = {k: {e[0]: e for e in repr_rows(by[k])} for k in (t - 1, t, t + 1)}
r = canon_live(frames[t], me)
held = lambda k, x, kk: any((e[3], e[4], e[5]) + ((e[6],) if k in 'TU' else ()) == x for e in rows[kk].values() if e[1] == {'T': 'T', 'U': 'C', 'P': 'P', 'A': 'A'}[k])  # noqa: E731
for k in 'TUPA':
    for x in r[k]:
        if held(k, x, t) or held(k, x, t + 1):
            continue
        cls = {'T': 'T', 'U': 'C', 'P': 'P', 'A': 'A'}[k]
        best = None
        for i, e in rows[t].items():
            if e[1] != cls or e[3] != x[0]:
                continue
            p = rows[t - 1].get(i)
            vx, vy = (e[4] - p[4], e[5] - p[5]) if p else (0, 0)
            dh = (p[6] - e[6]) if p and k in 'TU' else 0
            pred = (e[4] + vx, e[5] + vy) + ((e[6] - dh,) if k in 'TU' else ())
            d = abs(e[4] - x[1]) + abs(e[5] - x[2])
            if best is None or d < best[0]:
                best = (d, e[2], (e[4], e[5]) + ((e[6],) if k in 'TU' else ()), pred, i in rows[t + 1])
        print(k, x, 'nearest sim t:', best[1:] if best else None)
print('elixir rec', frames[t]['el'], 'sim t-1/t/t+1', [by[k]['S'][me][0] for k in (t - 1, t, t + 1)])
