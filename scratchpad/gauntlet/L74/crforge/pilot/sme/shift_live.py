"""For each short divergence episode (<= 2 frames) of matches in a run: does the recorded frame equal the sim at
t-2..t+2, or is every recorded object held by sim t-1/t or t/t+1 (a read across a step, either way)?
    python3 shift_live.py RUNDIR [MATCH ...]     (default: every match)  -> counts + examples"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import diff, run_batch  # noqa: E402
from sme_live import load_frames, canon_live, sim_canon, runnable  # noqa: E402

run = sys.argv[1]
ms = sys.argv[2:] or [json.loads(l)['match'] for l in open(os.path.join(run, 'results.jsonl'))]
cnt, ex = collections.Counter(), []
for m in ms:
    r = json.load(open(os.path.join(run, m, 'result.json')))
    eps = [e for e in r.get('episodes', []) if e['healed'] and e['frames'] <= 2]
    if not eps:
        continue
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    me = 1 if 'Xbow' in plan['decks'][1] else 0
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'shift'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    for e in eps:
        for t in sorted(t for t in frames if e['start'] <= t <= e['end']):
            rc = canon_live(frames[t], me)
            ks = [k for k in (-2, -1, 1, 2) if t + k in by and not diff(rc, sim_canon(by[t + k], me))]
            cls = 'equal_shift%+d' % ks[0] if ks else None
            if not cls:
                for a, b in ((-1, 0), (0, 1)):
                    if t + a in by and t + b in by:
                        sa, sb = sim_canon(by[t + a], me), sim_canon(by[t + b], me)
                        if all(x in sa[k] or x in sb[k] for k in 'TUPA' for x in rc[k]):
                            cls = 'union_t%+d_t%+d' % (a, b)
                            break
            cls = cls or 'other'
            cnt[cls] += 1
            if cls == 'other' and len(ex) < 12:
                ex.append((m, t, diff(rc, sim_canon(by[t], me))[:4]))
print(dict(cnt))
for x in ex:
    print(x)
