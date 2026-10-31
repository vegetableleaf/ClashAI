"""RECON-8 (pod): for every Golden Knight ability press of a plan, how well the SIM's GK matches the REC GK around it as extracted, with the press DROPPED,
and with the press moved to every run tick in [lo - SHIFT, hi + 2].  A diagnostic only: nothing here edits an input or a rule.
  SME_THREADS=4 bash recon/envR.sh python3 recon/r8_scan.py LIST OUT.jsonl
LIST: lines "match plan.json frames.jsonl" (plan = a gate plan.json or a recon_plan.json; frames = the match's frames).
Score of a press = the number of REC frames in [t - 4, t + 60] (t = the press's extracted tick) whose GK (the press's side) the SIM reproduces to the unit (the
nearest SIM / REC GK pair, as r8_press); the window's frame count is n.  Rows: match, cmd, side, source, lo, hi, tick, n, asis, drop, best_shift (run, score)."""
import copy, json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
import recon  # noqa: E402
GK = 26000074
SHIFT = 14


def gk_score(o, frames, side, lo, hi):
    by = {x['t']: x for x in o}
    n = ok = 0
    for t in range(lo, hi + 1):
        if t not in frames or t not in by:
            continue
        rec = [(e[1], e[2]) for e in frames[t]['E'] if e[3] == GK and e[0] == side]
        if not rec:
            continue
        sim = [(e[4], e[5]) for e in by[t]['E'] if e[1] == 'C' and e[2] == 'GoldenKnight' and e[3] == side]
        n += 1
        ok += any(s == q for s in sim for q in rec)
    return n, ok


def main():
    done = set()
    if os.path.exists(sys.argv[2]):   # resumable: a (match, cmd) already in OUT is skipped
        done = {(r['match'], r['cmd']) for r in map(json.loads, open(sys.argv[2]))}
    out = open(sys.argv[2], 'a')
    for line in open(sys.argv[1]):
        if not line.strip():
            continue
        m, pp, fp = line.split()
        plan = json.load(open(pp)); frames = sme_live.load_frames(fp)
        abil = [(k, c) for k, c in enumerate(plan['cmds']) if c['kind'] == 'ability' and (c.get('_src') or {}).get('source') in ('gk_dash', 'gk_buff')]
        for k, c in abil:
            if (m, k) in done:
                continue
            src = c.get('_src') or {}
            lo, hi, tick = src.get('lo', c['run']), src.get('hi', c['run']), src.get('tick', c['run'])
            side = c['side']
            w0, w1 = tick - 4, tick + 60
            variants = [('asis', None), ('drop', -1)] + [('run', r) for r in range(lo - SHIFT, hi + 3) if r != c['run']]
            jobs = []
            for name, r in variants:
                p = copy.deepcopy(plan)
                if r == -1:
                    p['cmds'][k] = {'kind': 'skip', 'given': 0, 'run': 0, 'side': side, '_src': {}}
                elif r is not None:
                    p['cmds'][k]['run'] = r; p['cmds'][k]['given'] = r - 20
                jobs.append((recon.runnable(p), min(max(frames), w1) + 3, 0))
            wd = '/dev/shm/r8_scan_%d' % os.getpid()   # RAM disk: the pod's disk is full and a batch of 18 runs writes ~200 MB
            res = run_batch(jobs, wd)
            shutil.rmtree(wd, ignore_errors=True)
            sc = {}
            for (name, r), o in zip(variants, res):
                if o is not None:
                    sc[(name, r)] = gk_score(o, frames, side, w0, w1)
            n = sc.get(('asis', None), (0, 0))[0]
            asis = sc.get(('asis', None), (0, 0))[1]
            drop = sc.get(('drop', -1), (0, 0))[1]
            runs = {r: v[1] for (nm, r), v in sc.items() if nm == 'run'}
            br = max(runs.items(), key=lambda kv: kv[1]) if runs else None
            row = {'match': m, 'cmd': k, 'side': side, 'source': src.get('source'), 'lo': lo, 'hi': hi, 'tick': tick, 'run': c['run'], 'n': n, 'asis': asis,
                   'drop': drop, 'best_run': br[0] if br else None, 'best_run_score': br[1] if br else None, 'runs': runs}
            out.write(json.dumps(row) + '\n'); out.flush()
            print(m[-13:], 'cmd', k, row['source'], 'tick', tick, 'run', c['run'], 'n', n, 'asis', asis, 'drop', drop, 'best shift', row['best_run'], row['best_run_score'], flush=True)


if __name__ == '__main__':
    main()
