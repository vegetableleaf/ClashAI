"""Is a recorded frame t a state of crforge's own step t+1 (A2c-BP, coordinator item 1)? SnapRun writes the whole state
at every in-step observer event of step t+1 (after the pre-pass, each hit, launch, impact, spawn, removal, the post-hooks
pass); each such state, plus lines t and t+1, is compared with the frame by the SME comparison (diff, placeholder fill).
Our elixir is compared apart: the reader reads it before the board, so it may be the value of any earlier state.
    python3 snapck.py RUNDIR OUT.jsonl MATCH:T [MATCH:T ...]   (or @FILE with one MATCH T per line)"""
import json, os, subprocess, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import diff
from sme_live import load_frames, runnable, canon_live, sim_canon, fill_placeholder
run, outp = sys.argv[1], sys.argv[2]
items = []
for a in sys.argv[3:]:
    if a.startswith('@'):
        items += [tuple(l.split()[:2]) for l in open(a[1:]) if l.strip()]
    else:
        items.append(tuple(a.split(':')))
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v9/inputs_rngfree.jsonl')}
WD = '/workspace/pilot/bp/work/snap_%d' % os.getpid()
os.makedirs(WD, exist_ok=True)
w = open(outp, 'w')
for m, t in items:
    t = int(t)
    if not m.startswith('live_play_'):
        m = 'live_play_' + m
    me = ME[m]
    plan = runnable(json.load(open(os.path.join(run, m, 'plan.json'))))
    pf = os.path.join(WD, 'p.json')
    json.dump(plan, open(pf, 'w'))
    of = os.path.join(WD, 'o.jsonl')
    open(os.path.join(WD, 'jobs.txt'), 'w').write('%s %d %s %d\n' % (pf, t + 2, of, t - 1))
    env = dict(os.environ, SNAP_TICKS=str(t + 1))
    r = subprocess.run(['java', '-Xmx8g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_snap', 'SnapRun',
                        '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), '1'], capture_output=True, text=True, env=env)
    lines = {o['t']: o for o in map(json.loads, open(of))}
    snaps = [json.loads(l) for l in open(of + '.snap.jsonl')] if os.path.exists(of + '.snap.jsonl') else []
    cands = [('line_t', lines[t])] + [('%d:%s' % (s['k'], s['ev']), s) for s in snaps] + [('line_t1', lines[t + 1])]
    f = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)[t]
    board, els = [], []
    best = None
    for k, (name, s) in enumerate(cands):
        sc = sim_canon(s, me)
        rc = fill_placeholder(canon_live(f, me), sc)
        d = [x for x in diff(rc, sc) if not x[0].startswith('S')]
        if not d:
            board.append(k)
        if s['S'][me][0] == f['el']:
            els.append(k)
        if os.environ.get('SNAP_VERBOSE'):
            print('   ', name, len(d), d[:3], 'el', s['S'][me][0])
        if best is None or len(d) < best[0]:
            best = (len(d), name, d[:4])
    fit = [k for k in board if any(e <= k for e in els)]
    res = dict(match=m, t=t, n_states=len(cands), board_exact_at=[cands[k][0] for k in board],
               elixir_at=[cands[k][0] for k in els], fits=[cands[k][0] for k in fit], best=best if not board else None)
    w.write(json.dumps(res, default=str) + '\n')
    w.flush()
    print(json.dumps(res, default=str)[:600])
