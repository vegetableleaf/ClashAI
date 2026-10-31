"""FREEZE-LIVE step 3 (pod): the engine's PRESS branch at moments where the live head HELD a pressable button (valuable class), from the
reconstructed exact state: the exact plan + one added Hero IW press at tick + 26 (the head's tap -> run delay) vs the plan as it is
(= live: no press). Same estimand as the SIM's iw_press forks (forced press - hold), but non-adaptive (both branches replay the recorded
later plays).  Run:  TAB= SME_THREADS=2 bash fl_env.sh python3 fl_held.py LIST2.jsonl OUT.jsonl [WORKERS]
LIST2 row: {match, plan_path, frames_path, me, held: [[tick, f46x10, elixir], ...]}"""
import copy, json, os, shutil, sys, time
sys.path.insert(0, '/dev/shm')

from freeze_live_cf import recon, sme_live, run_batch, hp_by_side, exposure, CUBE  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

OFFS = (100, 150, 300, 450)


def refused(o, me):
    return {(p[0], p[1]) for x in o for p in x['plays'] if p[3] == me and (p[4] != 0 or not p[2])}


def one(item):
    m = item['match']; t0 = time.time()
    try:
        plan = json.load(open(item['plan_path']))
        frames = sme_live.load_frames(item['frames_path'])
        me, end = item['me'], max(frames)
        # our hero IW plays (index, run)
        iws = [(i, c['run']) for i, c in enumerate(plan['cmds']) if c.get('kind') == 'play' and c.get('side') == me and c.get('card') == 'IceWizard']
        out = {'match': m, 'me': me, 'moments': []}
        jobs, meta = [], []
        for tick, f46, el in item['held']:
            run = int(tick) + 26
            prev = [i for i, r in iws if r + 20 <= run]
            if not prev:
                continue
            p = copy.deepcopy(plan)
            p['cmds'].append({'kind': 'ability', 'given': run - 20, 'run': run, 'side': me, 'unit': 'cmd%d_0' % prev[-1],
                              '_src': {'lo': run, 'hi': run, 'tick': run, 'source': 'fl_held', 'own': False}})
            jobs.append((recon.runnable(p), min(end, run + max(OFFS) + 40) + 3, 0))
            meta.append((tick, f46, el, run))
        if not jobs:
            return out
        work = '/dev/shm/flh_work_%d' % os.getpid()
        shutil.rmtree(work, ignore_errors=True)
        res = run_batch([(recon.runnable(plan), end + 3, 0)] + jobs, work)
        if res[0] is None:
            out['error'] = 'base failed'; return out
        by0 = {x['t']: x for x in res[0]}
        ref0 = refused(res[0], me)
        for (tick, f46, el, run), o1 in zip(meta, res[1:]):
            if o1 is None:
                out['moments'].append({'tick': tick, 'refused': 'run error'}); continue
            by1 = {x['t']: x for x in o1}
            ct = sum(1 for t in range(run, run + 200) if t in by1 and any(e[1] == 'C' and e[2] == CUBE and e[3] == me for e in by1[t]['E']))
            row = {'tick': tick, 'f46': f46, 'elixir': el, 'run': run, 'cube_ticks': ct, 'exposure': exposure(by1, run, me), 'hp': {},
                   # my plays the press branch refuses that the live history accepted (the press costs 2 elixir; the recorded plays do not adapt)
                   'ref_extra': sorted(t for (c, t) in refused(o1, me) - ref0 if run <= t <= run + max(OFFS))}
            for d in OFFS:
                a, b = by0.get(run + d), by1.get(run + d)
                if a is None or b is None:
                    continue
                ta, _ = hp_by_side(a); tb, _ = hp_by_side(b)
                row['hp'][d] = [sum(v for k, v in tb.items() if k[0] == me and k[1] != 9000),   # with the press
                                sum(v for k, v in ta.items() if k[0] == me and k[1] != 9000)]   # live (no press)
            out['moments'].append(row)
        out['secs'] = round(time.time() - t0, 1)
        shutil.rmtree(work, ignore_errors=True)
        return out
    except Exception:
        import traceback
        return {'match': m, 'error': traceback.format_exc()[-500:]}


def main():
    lst = [json.loads(l) for l in open(sys.argv[1])]
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    with open(sys.argv[2], 'a') as w, ProcessPoolExecutor(nw) as ex:
        for r in ex.map(one, lst):
            w.write(json.dumps(r) + '\n'); w.flush()
            print(r['match'], r.get('error') or (len(r['moments']), r.get('secs')), flush=True)


if __name__ == '__main__':
    main()
