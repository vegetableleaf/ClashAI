"""Round 6.2 planted checks of torn_cmd at triple elixir (SME_TORN_CMD=1 SME_TORN_CMD3=1 + run env):
    python3 cmd_test6.py RUNDIR LIST INPUTS
Per onset frame t0 classed torn_cmd, each planted change must take it out of torn_cmd (its class is printed):
  el+1 / el-1   our elixir 1 off (the regen arithmetic breaks);
  half          our elixir 0.5 elixir lower still (not a whole card cost);
  body+1        one recorded unit (hp > 0) moved 1 unit (the board must equal sim t)."""
import copy, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse, TORN_CMD, TORN_CMD3  # noqa: E402

assert TORN_CMD and TORN_CMD3, 'set SME_TORN_CMD=1 SME_TORN_CMD3=1'
run, lst, inputs = sys.argv[1:4]
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
todo = [(l.split()[0], int(l.split()[1])) for l in open(lst) if l.strip()]
plans = {m: json.load(open(os.path.join(run, m, 'plan.json'))) for m, _ in todo}
outs = run_batch([(runnable(plans[m]), t0 + 4, max(0, t0 - 3)) for m, t0 in todo], os.path.join(run, 'cmdtest6'))
n = {'onsets': len(todo), 'torn_cmd': 0}
for (m, t0), o in zip(todo, outs):
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))
    cls = lambda f: analyse(o, {t0: f}, ME[m], t0, t0)['cls'][t0]  # noqa: E731
    c = cls(frames[t0])
    out = [m[10:], t0, c]
    if c == 'torn_cmd':
        n['torn_cmd'] += 1
        plant = {}
        for name, dv in (('el+1', 1), ('el-1', -1), ('half', -5000)):
            f = copy.deepcopy(frames[t0]); f['el'] += dv; plant[name] = f
        f = copy.deepcopy(frames[t0])
        k = next((j for j, r in enumerate(f['E']) if r[3] != -1 and r[4] > 0), None)
        if k is not None:
            f['E'][k][1] += 1; plant['body+1'] = f
        for name, f in plant.items():
            c2 = cls(f)
            n[name + '_n'] = n.get(name + '_n', 0) + 1
            n[name + '_caught'] = n.get(name + '_caught', 0) + (c2 != 'torn_cmd')
            out += [name, c2]
    print(*out, flush=True)
shutil.rmtree(os.path.join(run, 'cmdtest6'), ignore_errors=True)
print(n)
