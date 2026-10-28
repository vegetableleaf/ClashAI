"""Planted checks for round 8.4 (SME_HIDDEN, sme_live.hidden_ok) on every hidden-interval frame of the unflagged-or-not
matches that have a reader_hidden entry. Run in /workspace/pilot/sme8 with the run8.sh env + SME_HIDDEN=1:
    python3 hidden_test.py RUNDIR INPUTS
Per frame: the unplanted frame must pass; each planted change must fail."""
import copy, json, os, sys
sys.path.insert(0, '/workspace/pilot/sme8')
import sme_live
from sme import run_batch
from sme_live import load_frames, runnable, hidden_ok
run, inputs = sys.argv[1:3]
tot = {}
for l in open(inputs):
    rec = json.loads(l)
    hs = rec.get('reader_hidden') or []
    if not hs:
        continue
    m, me = rec['match'], rec['my_side']
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    fr = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
    lo, hi = min(h['last'] for h in hs) + 1, max(h['end'] for h in hs)
    o = {s['t']: s for s in run_batch([(runnable(plan), hi + 1, lo)], '/workspace/pilot/a2c8/ht%d' % os.getpid())[0]}
    for h in hs:
        for t in sorted(t for t in fr if h['last'] < t <= h['end'] and t in o):
            f = dict(fr[t], H=[[h['side'], h['name'], h['track'].get(str(t))]])
            tracked = f['H'][0][2] is not None
            res = {'base': hidden_ok(f, o[t], me)}
            idx = [i for i, e in enumerate(o[t]['E']) if e[2] == h['name'] and e[3] == h['side']]
            if idx and tracked:
                s2 = copy.deepcopy(o[t]); s2['E'][idx[0]][4] += 1
                res['sim hidden row x+1 (tracked)'] = not hidden_ok(f, s2, me)
            if idx:
                s3 = copy.deepcopy(o[t]); s3['E'].append(list(s3['E'][idx[0]]))
                res['second sim row same name'] = not hidden_ok(f, s3, me)
                f4 = dict(f, H=[[h['side'], h['name'] + 'X', f['H'][0][2]]])
                res['other name'] = not hidden_ok(f4, o[t], me)
                f5 = dict(f, H=[[1 - h['side'], h['name'], f['H'][0][2]]])
                res['other side'] = not hidden_ok(f5, o[t], me)
            if f['E']:
                f6 = copy.deepcopy(f); f6['E'][0][1] += 1
                res['a recorded body x+1'] = not hidden_ok(f6, o[t], me)
            f7 = dict(f, el=f['el'] + 10000)
            res['our elixir +1'] = not hidden_ok(f7, o[t], me)
            for k, v in res.items():
                a = tot.setdefault((m, k), [0, 0]); a[0] += v; a[1] += 1
for (m, k), (a, n) in sorted(tot.items()):
    print('%s %-30s %d / %d' % (m, k, a, n))
