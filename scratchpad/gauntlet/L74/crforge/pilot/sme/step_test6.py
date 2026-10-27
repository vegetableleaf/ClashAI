"""Round 6.1 planted checks of torn_step with the elixir clock (SME_TORN_STEP=1 SME_STEP_CLOCK=1 + run env):
    python3 step_test6.py RUNDIR LIST INPUTS
Per onset frame t0 that the rule classes torn_step, each planted change must take it out of torn_step (the class it
gets is printed: div, or an older rule's torn_mixed):
  el_t   our elixir set to sim t's value (the clock gone; with < 2 movers nothing else says "step t+1");
  el+1   our elixir 1 off;
  body+1 one recorded body (a sim t->t+1 mover if any, else a live unit, hp > 0) moved 1 unit;
  hp0->5 a recorded body read at hp 0 given hp 5 (if any)."""
import copy, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse, repr_rows, TORN_STEP, STEP_CLOCK  # noqa: E402

assert TORN_STEP and STEP_CLOCK, 'set SME_TORN_STEP=1 SME_STEP_CLOCK=1'
run, lst, inputs = sys.argv[1:4]
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
todo = [(l.split()[0], int(l.split()[1])) for l in open(lst) if l.strip()]
plans = {m: json.load(open(os.path.join(run, m, 'plan.json'))) for m, _ in todo}
outs = run_batch([(runnable(plans[m]), t0 + 4, max(0, t0 - 3)) for m, t0 in todo], os.path.join(run, 'steptest6'))
n = {'onsets': len(todo), 'torn_step': 0}
for (m, t0), o in zip(todo, outs):
    me = ME[m]
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))
    by = {s['t']: s for s in o}
    cls = lambda f: analyse(o, {t0: f}, me, t0, t0)['cls'][t0]  # noqa: E731
    c = cls(frames[t0])
    out = [m[10:], t0, c]
    if c == 'torn_step':
        n['torn_step'] += 1
        a = {e[0]: e for e in repr_rows(by[t0])}
        b = {e[0]: e for e in repr_rows(by[t0 + 1])}
        mv = [b[i] for i in a if i in b and a[i][1] in 'TC' and a[i][4:6] != b[i][4:6]]
        out.append('movers=%d' % len(mv))
        plant = {}
        f = copy.deepcopy(frames[t0]); f['el'] = by[t0]['S'][me][0]; plant['el_t'] = f
        f = copy.deepcopy(frames[t0]); f['el'] += 1; plant['el+1'] = f
        f = copy.deepcopy(frames[t0])
        k = next((j for j, r in enumerate(f['E']) if mv and (r[0], r[1], r[2]) == (mv[0][3], mv[0][4], mv[0][5])),
                 next((j for j, r in enumerate(f['E']) if r[3] != -1 and r[4] > 0), None))
        if k is not None:
            f['E'][k][1] += 1; plant['body+1'] = f
        f = copy.deepcopy(frames[t0])
        k = next((j for j, r in enumerate(f['E']) if r[4] == 0), None)
        if k is not None:
            f['E'][k][4] = 5; plant['hp0->5'] = f
        for name, f in plant.items():
            c2 = cls(f)
            if name == 'el_t' and len(mv) >= 2:
                name += '(2+ movers: not a clock case)'
            else:
                n[name + '_n'] = n.get(name + '_n', 0) + 1
                n[name + '_caught'] = n.get(name + '_caught', 0) + (c2 != 'torn_step')
            out += [name, c2]
    print(*out, flush=True)
shutil.rmtree(os.path.join(run, 'steptest6'), ignore_errors=True)
print(n)
