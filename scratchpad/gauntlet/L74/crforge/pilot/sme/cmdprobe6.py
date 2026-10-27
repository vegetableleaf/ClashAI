"""Set chosen commands to chosen run ticks and score the whole match (ticket A2c round 6.0 probes).
    SME_... python3 cmdprobe6.py RUNDIR INPUTS M:K:R[:Y][,K:R[:Y]...] ...   (M = match suffix, K = command index, R = run
    tick, Y = an optional play y)
Prints the baseline and each variant: first true divergence and frame counts."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, analyse  # noqa: E402

FRAMES = '/workspace/pilot/sme_live/frames2'


def main():
    run, inputs = sys.argv[1:3]
    me_of = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
    jobs, meta, frs = [], [], {}
    for arg in sys.argv[3:]:
        m, rest = arg.split(':', 1)
        m = 'live_play_' + m
        plan = json.load(open(os.path.join(run, m, 'plan.json')))
        frs[m] = load_frames(os.path.join(FRAMES, m + '.jsonl'))
        p = json.loads(json.dumps(plan))
        for kr in rest.split(','):
            k, R, *y = map(int, kr.split(':'))   # optional K:R:Y also sets the play's y
            p['cmds'][k]['given'] += R - p['cmds'][k]['run']
            p['cmds'][k]['run'] = R
            if y:
                p['cmds'][k]['y'] = y[0]
        for q, tag in ((plan, 'base'), (p, rest)):
            jobs.append((runnable(q), max(frs[m]) + 3, 0))
            meta.append((m, tag))
    work = os.path.join(run, 'cmdprobe6_work')
    outs = run_batch(jobs, work)
    for (m, tag), o in zip(meta, outs):
        if o is None:
            print(m[10:], tag, 'refused', flush=True)
            continue
        a = analyse(o, frs[m], me_of[m])
        print(m[10:], tag, 'first', a['first'], a['counts'], 'missing', a['missing_in_sim'], flush=True)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
