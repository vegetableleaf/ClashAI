"""Round 4.1 check of the torn_step rule on the body-position onsets (run on the pod, SME_TORN_STEP=1 + run env):
    python3 step_test.py RUNDIR LIST
Per onset frame t0: its class with the rule, and the class when one recorded body that moves in step t0+1 is moved 1
unit (planted: must not be torn_step), and when the frame's elixir is set 1 off (must not be torn_step)."""
import copy, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse, repr_rows, TORN_STEP  # noqa: E402

assert TORN_STEP, 'set SME_TORN_STEP=1'
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v2/inputs_rngfree.jsonl')}
run, lst = sys.argv[1:3]
n = {'torn_step': 0, 'planted_caught': 0, 'planted_n': 0, 'el_caught': 0}
for line in open(lst):
    m, t0 = line.split()[:2]
    t0 = int(t0)
    me = ME[m]
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))
    o = run_batch([(runnable(plan), t0 + 4, max(0, t0 - 3))], os.path.join(run, m, 'steptest'))[0]
    by = {s['t']: s for s in o}
    c = analyse(o, {t0: frames[t0]}, me, t0, t0)['cls'][t0]
    out = [m[10:], t0, c]
    if c == 'torn_step':
        n['torn_step'] += 1
        a = {e[0]: e for e in repr_rows(by[t0])}
        b = {e[0]: e for e in repr_rows(by[t0 + 1])}
        mv = [b[i] for i in a if i in b and a[i][1] in 'TC' and a[i][4:6] != b[i][4:6]]
        f = copy.deepcopy(frames[t0])
        k = next(j for j, r in enumerate(f['E']) if (r[0], r[1], r[2]) == (mv[0][3], mv[0][4], mv[0][5]))
        f['E'][k][1] += 1
        c2 = analyse(o, {t0: f}, me, t0, t0)['cls'][t0]
        n['planted_n'] += 1
        n['planted_caught'] += c2 == 'div'
        f = copy.deepcopy(frames[t0])
        f['el'] += 1
        c3 = analyse(o, {t0: f}, me, t0, t0)['cls'][t0]
        n['el_caught'] += c3 == 'div'
        out += ['planted', c2, 'elixir+1', c3]
    print(*out, flush=True)
print(n)
