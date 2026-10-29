"""ENG-FIX2 planted checks for sme_live SME_HIDDEN_ASSIGN on FRESH4 210016 (one hidden Golemite, two sim Golemites).
Pod, in runH.sh's env with SME_HIDDEN_ASSIGN=1 SME_HIDDEN=1:
    python3 hassign_test.py PLAN.json FRAMES.jsonl INPUT_RECORD.jsonl -> 'ok N'"""
import copy, json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/f1fix/sme11f'))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
assert sme_live.HIDDEN_ASSIGN, 'run with SME_HIDDEN_ASSIGN=1'
plan, fp, recp = sys.argv[1:4]
rec = json.loads(open(recp).readline())
frames = sme_live.load_frames(fp)
for h in rec['reader_hidden']:
    for t in frames:
        if h['last'] < t <= h['end']:
            frames[t].setdefault('H', []).append([h['side'], h['name'], h['track'].get(str(t)), sme_live.hidden_ref(h['track'], t)])
o = run_batch([(sme_live.runnable(json.load(open(plan))), max(frames) + 3, 0)], '/tmp/hassign_%d' % os.getpid())[0]
by = {x['t']: x for x in o}
me = rec['my_side']
n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


def ok(t, oo=None, f=None):
    return sme_live.hidden_assign(f or frames[t], oo or by[t], me)


H = sorted(t for t in frames if frames[t].get('H') and t in by)
an = sme_live.analyse(o, frames, me)
check(H and all(an['cls'][t] == 'exact' for t in H), 'every hidden frame of 210016 scores exact under the assignment')
check(not any(c in ('torn_hidden',) for c in an['cls'].values()), 'no torn_hidden class with the flag')


def moved(t, pick, dx):
    """by[t] with the sim Golemite chosen by pick(rows) moved dx units in x."""
    oo = copy.deepcopy(by[t])
    gs = [e for e in oo['E'] if e[1] == 'C' and e[2] == 'Golemite' and e[3] == 1]
    e = pick(gs)
    e[4] += dx
    return oo


t_pt = 2070                                    # the frame has its own target point (5470, 8831)
near_pt = lambda gs: min(gs, key=lambda e: abs(e[4] - 5470) + abs(e[5] - 8831))
far_pt = lambda gs: max(gs, key=lambda e: abs(e[4] - 5470) + abs(e[5] - 8831))
check(ok(t_pt), '2070 exact')
check(not ok(t_pt, moved(t_pt, near_pt, 1)), 'PLANT: the assigned sim body 1 unit off the target point -> div')
check(not ok(t_pt, moved(t_pt, far_pt, 1)), 'PLANT: the listed (non-hidden) sim body moved 1 unit -> div')
t_np = 2080                                    # no target point on this frame: reference = the 2072 point
check(frames[t_np]['H'][0][2] is None and ok(t_np), '2080 (reference point only) exact')
check(not ok(t_np, moved(t_np, far_pt, 1)), 'PLANT: the listed sim body moved 1 unit on a reference-only frame -> div')
f_noref = copy.deepcopy(frames[t_np])
f_noref['H'][0][3] = None
check(not ok(t_np, f=f_noref), 'PLANT: no reference point with two candidates -> div')
oo = copy.deepcopy(by[t_np])
oo['E'] = [e for e in oo['E'] if not (e[1] == 'C' and e[2] == 'Golemite' and e is near_pt(
    [g for g in oo['E'] if g[1] == 'C' and g[2] == 'Golemite' and g[3] == 1]))]
check(not ok(t_np, oo), 'PLANT: the hidden body missing in the sim -> div (the listed one is taken, the rest diverges)')
f_tie = copy.deepcopy(frames[t_np])
gs = [e for e in by[t_np]['E'] if e[1] == 'C' and e[2] == 'Golemite' and e[3] == 1]
f_tie['H'][0][3] = [(gs[0][4] + gs[1][4]) / 2, (gs[0][5] + gs[1][5]) / 2]
check(not ok(t_np, f=f_tie), 'PLANT: a reference point equidistant from both -> tie -> div')
print('ok', n)
