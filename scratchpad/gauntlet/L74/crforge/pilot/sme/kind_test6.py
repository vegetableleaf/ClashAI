"""Round 6.6 planted checks of the reader-kind tower rule (SME_KIND_T=1 + run env):
    python3 kind_test6.py RUNDIR LIST INPUTS
Per onset frame t0 holding a card -1 row of a troop kind (14/15), its class with the rule, and with that row
moved 1 unit (pos+1) or its hp 1 off (hp+1): each planted change must leave the frame not exact."""
import copy, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse, KIND_T  # noqa: E402

assert KIND_T, 'set SME_KIND_T=1'
run, lst, inputs = sys.argv[1:4]
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
todo = [(l.split()[0], int(l.split()[1])) for l in open(lst) if l.strip()]
frs = {m: load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl')) for m, _ in todo}
todo = [(m, t0) for m, t0 in todo if any(e[3] == -1 and e[5] in (14, 15) for e in frs[m][t0]['E'])]
plans = {m: json.load(open(os.path.join(run, m, 'plan.json'))) for m, _ in todo}
outs = run_batch([(runnable(plans[m]), t0 + 4, max(0, t0 - 3)) for m, t0 in todo], os.path.join(run, 'kindtest6'))
n = {'frames': len(todo)}
for (m, t0), o in zip(todo, outs):
    cls = lambda f: analyse(o, {t0: f}, ME[m], t0, t0)['cls'][t0]  # noqa: E731
    f0 = frs[m][t0]
    c = cls(f0)
    n[c] = n.get(c, 0) + 1
    out = [m[10:], t0, c]
    k = next(j for j, e in enumerate(f0['E']) if e[3] == -1 and e[5] in (14, 15))
    for name, col, dv in (('pos+1', 1, 1), ('hp+1', 4, 1)):
        f = copy.deepcopy(f0); f['E'][k][col] += dv
        c2 = cls(f)
        n[name + '_n'] = n.get(name + '_n', 0) + 1
        n[name + '_caught'] = n.get(name + '_caught', 0) + (c2 != 'exact')
        out += [name, c2]
    print(*out, flush=True)
shutil.rmtree(os.path.join(run, 'kindtest6'), ignore_errors=True)
print(n)
