"""RECON-6 diagnostic (pod): what stands at a match's first divergence. Runs a final plan (recon_plan.json) on crforge and prints, for the
first div frame d, the SIM bodies and the live bodies that differ, with the command that made each SIM body and its form (the body's
unit name), then the SIM's play list around d.
  python3 recon/form_diag.py PLAN.json FRAMES.jsonl MYSIDE [--noslot CARD,...] [--out DIR]
--noslot clears the slot flag of the named deck cards on BOTH sides (a hero / evo form probe, not a fix)."""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
import recon  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan'); ap.add_argument('frames'); ap.add_argument('me', type=int)
    ap.add_argument('--noslot', default=''); ap.add_argument('--out', default='/tmp/form_diag')
    ap.add_argument('--noopp', action='store_true')   # clear every slot flag of the opponent (a form probe)
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    frames = sme_live.load_frames(a.frames)
    for card in [c for c in a.noslot.split(',') if c]:
        for s in (0, 1):
            for k, c in enumerate(plan['decks'][s]):
                if c == card:
                    plan['slots'][s][k] = 0
    if a.noopp:
        plan['slots'][1 - a.me] = [0] * 8
    end = max(frames)
    o = run_batch([(recon.runnable(plan), end + 3, 0)], os.path.join(a.out, 'work'))[0]
    an = sme_live.reclassify(plan, frames, a.me, sme_live.analyse(o, frames, a.me), o, os.path.join(a.out, 'work'))
    print(json.dumps({k: an[k] for k in ('frames', 'counts', 'first', 'missing_in_sim')}))
    d = an['first']
    if d is None:
        return
    by = {x['t']: x for x in o}
    print('first detail', json.dumps(sme_live.describe_first(by, frames, a.me, d))[:1500])
    for x in sme_live.describe_first(by, frames, a.me, d) or []:
        pass
    # SIM bodies at d that are sim-only, with the making command
    sim_only = {tuple(x[1][:3]) for x in sme_live.describe_first(by, frames, a.me, d) if x[0] == 'U_sim_only'}
    for e in by[d]['E']:
        if e[1] == 'C' and (e[3], e[4], e[5]) in sim_only:
            src = e[8]
            cmd = next((c for k, c in enumerate(plan['cmds']) if 'cmd%d' % k == src), None)
            print('SIM-only', e[2], e[3:7], 'src', src, {k: cmd.get(k) for k in ('card', 'run', 'x', 'y', 'side')} if cmd else None)
    print('plays near d:')
    for x in o:
        for p in x['plays']:
            if d - 400 <= x['t'] <= d + 5:
                print('  ', x['t'], p)


if __name__ == '__main__':
    main()
