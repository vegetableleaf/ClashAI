"""RECON-8 (pod): a Golden Knight ability press tried at several run ticks; the SIM GK next to the REC GK on every REC frame of the window.
  SME_TGT=1 bash recon/envR.sh python3 recon/r8_press.py PLAN.json FRAMES.jsonl SIDE CMD RUN1,RUN2,.. T0 T1 [--add]
CMD = index of the ability command to move (its run / given are set to R / R - 20); with --add a new ability is APPENDED instead (CMD = the GK play's index
whose unit it names, 'cmdN_0'); with RUN 0 the plan is run as it is.  Prints, per variant, the exact-frame count in [T0, T1] and the per-frame (dx, dy)."""
import copy, json, math, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
import recon  # noqa: E402
GK = 26000074


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    plan = json.load(open(a[0])); frames = sme_live.load_frames(a[1])
    side, cmd, runs, t0, t1 = int(a[2]), int(a[3]), [int(x) for x in a[4].split(',')], int(a[5]), int(a[6])
    add = '--add' in sys.argv
    out = '/dev/shm/r8_press_%d' % os.getpid()
    jobs, plans = [], []
    for r in runs:
        p = copy.deepcopy(plan)
        if r < 0:   # RUN -1: the command is dropped (kind skip keeps the indices)
            p['cmds'][cmd] = {'kind': 'skip', 'given': 0, 'run': 0, 'side': side, '_src': {}}
        elif r:
            if add:
                p['cmds'].append({'kind': 'ability', 'given': r - 20, 'run': r, 'side': side, 'unit': 'cmd%d_0' % cmd, '_src': {'lo': r, 'hi': r, 'tick': r, 'source': 'gk_dash', 'own': False}})
            else:
                p['cmds'][cmd]['run'] = r; p['cmds'][cmd]['given'] = r - 20
        plans.append(p)
        end = max(frames) if '--full' in sys.argv else min(max(frames), t1)
        jobs.append((recon.runnable(p), end + 3, 0))
    res = run_batch(jobs, out)
    for r, o, p in zip(runs, res, plans):
        if o is None:
            print('run', r, 'FAILED'); continue
        by = {x['t']: x for x in o}
        line, exact = [], 0
        for t in range(t0, t1 + 1):
            if t not in frames or t not in by:
                continue
            rec = [(e[1], e[2]) for e in frames[t]['E'] if e[3] == GK and e[0] == side]
            sim = [(e[4], e[5]) for e in by[t]['E'] if e[1] == 'C' and e[2] == 'GoldenKnight' and e[3] == side]
            if not rec or not sim:
                line.append('%d:-' % t); continue
            d = min(((s[0] - q[0], s[1] - q[1]) for q in rec for s in sim), key=lambda v: abs(v[0]) + abs(v[1]))
            exact += d == (0, 0)
            line.append('%d:%s' % (t, 'ok' if d == (0, 0) else '(%d,%d)' % d))
        print('run', r, 'exact frames', exact, '|', ' '.join(line))
        if '--full' in sys.argv:   # the whole-record score (comparator = analyse + reclassify, as recon_search / form_diag), me = the other side
            me = 1 - side
            an = sme_live.reclassify(p, frames, me, sme_live.analyse(o, frames, me), o, os.path.join(out, 'w%d' % r))
            print('   full:', json.dumps({k: an[k] for k in ('frames', 'counts', 'first', 'missing_in_sim')}))
    shutil.rmtree(out, ignore_errors=True)   # RAM disk work dir


if __name__ == '__main__':
    main()
