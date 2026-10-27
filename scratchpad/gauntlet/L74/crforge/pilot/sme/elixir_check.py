"""Own-elixir timing around our own plays, live vs sim: for every play of our side with run tick R (final plan), the
recorded frame at R+k (k=-1..2): is its elixir the sim's at R+k, the sim's minus the card cost (deducted early), or
other? Also the play's tap tick (live 'play' event / record own_taps) and the extractor's window, per class.
    python3 elixir_check.py RUNDIR INPUTS.jsonl"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
recs = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
tab = collections.defaultdict(collections.Counter)
early = collections.Counter()
lag_early, lag_ok = collections.Counter(), collections.Counter()
ex = []
for m, rec in recs.items():
    p = os.path.join(run, m, 'plan.json')
    if rec['flags'] or not os.path.exists(p):
        continue
    plan = json.load(open(p))
    me = rec['my_side']
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'elx'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    taps = sorted(rec['own_taps'], key=lambda t: t['tick'])
    for c in plan['cmds']:
        if c['side'] != me or c['kind'] != 'play':
            continue
        R = c['run']
        cost = None
        if R + 1 in by and R in by:
            cost = by[R][ 'S'][me][0] + 178 * 0 - by[R + 1]['S'][me][0]  # drop over the step (regen in it)
        tap = max((t['tick'] for t in taps if t['name'] == c['card'] and t['tick'] <= R), default=None)
        for k in (-1, 0, 1, 2):
            t = R + k
            if t not in frames or t not in by or cost is None:
                continue
            r, s = frames[t]['el'], by[t]['S'][me][0]
            if r == s:
                cls = 'equal'
            elif abs((s - r) - (by[R]['S'][me][0] - by[R + 1]['S'][me][0] + (by[R + 1]['S'][me][0] - by[R]['S'][me][0]))) < 1 and False:
                cls = 'x'
            elif k <= 0 and 9000 <= s - r <= 100000:
                cls = 'rec lower by %d' % round((s - r) / 1000)
            else:
                cls = 'other %+d' % (r - s)
            tab[k][cls] += 1
            if k == 0 and cls != 'equal':
                early[c['card']] += 1
                if tap is not None:
                    lag_early[R - tap] += 1
                if len(ex) < 6:
                    ex.append((m, c['card'], R, tap, r, s, c['_src']))
            elif k == 0 and tap is not None:
                lag_ok[R - tap] += 1
for k in sorted(tab):
    print('recorded elixir at run tick %+d:' % k, dict(tab[k].most_common(8)))
print('early (k=0) by card:', early.most_common())
print('run - tap ticks, early plays:', sorted(lag_early.items()))
print('run - tap ticks, plays equal at k=0:', sorted(lag_ok.items()))
for x in ex:
    print(x)
