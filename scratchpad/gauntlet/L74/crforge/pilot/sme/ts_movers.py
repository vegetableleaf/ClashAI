"""Round 4.1 audit: per torn_step frame, how many sim bodies move in step t+1 and on which sides (run env +
SME_TORN_STEP=1): python3 ts_movers.py RUNDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse, repr_rows, TORN_STEP  # noqa: E402

assert TORN_STEP
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v2/inputs_rngfree.jsonl')}
run = sys.argv[1]
hist, per = collections.Counter(), []
for l in open(os.path.join(run, 'results.jsonl')):
    r = json.loads(l)
    if not r.get('counts', {}).get('torn_step'):
        continue
    m = r['match']
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'tsm'))[0]
    by = {x['t']: x for x in o}
    an = analyse(o, frames, ME[m])
    for t, c in an['cls'].items():
        if c != 'torn_step':
            continue
        a = {e[0]: e for e in repr_rows(by[t]) if e[1] in 'TC'}
        b = {e[0]: e for e in repr_rows(by[t + 1]) if e[1] in 'TC'}
        mv = [a[i] for i in a if i in b and a[i][4:6] != b[i][4:6]]
        k = (min(len(mv), 3), len({e[3] for e in mv}))
        hist[k] += 1
        per.append((m[10:], t, len(mv), sorted({e[2] for e in mv})[:4]))
print('(movers capped at 3, sides moving): frames', sorted(hist.items()))
for p in per:
    if p[2] < 2:
        print(*p)
