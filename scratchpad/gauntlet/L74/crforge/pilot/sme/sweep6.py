"""Single-command run-tick sweep at every onset (ticket A2c round 6.0; abp.py over all matches, batched, small traces).
    SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_TORN_STEP=1 SME_REPR=... SME_LIB=... SME_BUILD=... \
    python3 sweep6.py RUNDIR LIST INPUTS OUT.jsonl [SHIFTS]
For each onset t0 every command run in [t0-130, t0+15] is moved by each shift (default -3..+3, run and given together;
a command after t0 also back to t0-3);
the sim is scored on [t0-135, t0+400]. A row per variant whose first divergence moves past t0 (None = none to t0+400)."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse  # noqa: E402

FRAMES = '/workspace/pilot/sme_live/frames2'


def main():
    run, lst, inputs, outp = sys.argv[1:5]
    shifts = [int(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 else [-3, -2, -1, 1, 2, 3]
    me_of = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
    todo = [(l.split()[0], int(l.split()[1])) for l in open(lst) if l.strip()]
    work = os.path.join(run, 'sweep6_work')
    with open(outp, 'w') as w:
        for b in range(0, len(todo), 8):
            jobs, meta, frs = [], [], {}
            for m, t0 in todo[b:b + 8]:
                plan = json.load(open(os.path.join(run, m, 'plan.json')))
                frs[m] = load_frames(os.path.join(FRAMES, m + '.jsonl'))
                for k, c in enumerate(plan['cmds']):
                    if c['kind'] == 'skip' or not t0 - 130 <= c['run'] <= t0 + 15:
                        continue
                    # a command dated after the onset is also tried at every tick back to 3 before the onset
                    for dR in sorted(set(shifts) | set(range(t0 - 3 - c['run'], 0))):
                        p = json.loads(json.dumps(plan))
                        p['cmds'][k]['run'] += dR
                        p['cmds'][k]['given'] += dR
                        jobs.append((runnable(p), t0 + 400, max(0, t0 - 135)))
                        meta.append((m, t0, k, dR, c))
            outs = run_batch(jobs, work) if jobs else []
            for (m, t0, k, dR, c), o in zip(meta, outs):
                if o is None:
                    continue
                a = analyse(o, frs[m], me_of[m], max(0, t0 - 135), t0 + 400)
                if a['first'] is None or a['first'] > t0:
                    w.write(json.dumps({'match': m, 't0': t0, 'cmd': k, 'dR': dR, 'card': c.get('card') or 'ability:' + c.get('unit', ''),
                                        'side': c['side'], 'run': c['run'], 'lo': c['_src']['lo'], 'hi': c['_src']['hi'],
                                        'src': c['_src'].get('source'), 'first': a['first'], 'div': a['counts'].get('div', 0)}) + '\n')
            w.flush()
            shutil.rmtree(work, ignore_errors=True)
            print('batch', b, len(jobs), flush=True)


if __name__ == '__main__':
    main()
