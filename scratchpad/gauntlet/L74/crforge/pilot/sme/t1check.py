"""Is a body-position onset frame a read of a later game tick? (ticket A2c round 4)
    SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=repr_v1.json SME_LIB=... SME_BUILD=... python3 t1check.py RUNDIR LIST OUT.jsonl
LIST: "<match> <onset>" lines. For the onset frame t0 and the frame after it: the diff against sim t0, t0+1 and t0+2,
by object class, plus what is left of the t0+1 diff (kind, card, offset)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch, diff  # noqa: E402
from sme_live import load_frames, runnable, canon_live, sim_canon, fill_placeholder, HP_PH  # noqa: E402

FRAMES = '/workspace/pilot/sme_live/frames2'
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v2/inputs_rngfree.jsonl')}


def d_at(frames, by, me, t, k):
    if t + k not in by:
        return None
    r = canon_live(frames[t], me)
    s = sim_canon(by[t + k], me)
    if HP_PH:
        r = fill_placeholder(r, s)
    return diff(r, s)


def main():
    run, lst, outp = sys.argv[1:4]
    with open(outp, 'w') as w:
        for line in open(lst):
            m, t0 = line.split()[:2]
            t0 = int(t0)
            me = ME[m]
            plan = json.load(open(os.path.join(run, m, 'plan.json')))
            frames = load_frames(os.path.join(FRAMES, m + '.jsonl'))
            ts = sorted(frames)
            nxt = [t for t in ts if t > t0][:3]
            o = run_batch([(runnable(plan), max(nxt + [t0]) + 4, max(0, t0 - 3))], os.path.join(run, m, 't1check'))[0]
            by = {s['t']: s for s in o}
            rows = {}
            for t in [t0] + nxt:
                rows[t] = {k: (len(d) if d is not None else None) for k, d in
                           (('k0', d_at(frames, by, me, t, 0)), ('k1', d_at(frames, by, me, t, 1)), ('k2', d_at(frames, by, me, t, 2)))}
            left = d_at(frames, by, me, t0, 1) or []
            names_r = {(e[0], e[1], e[2], e[4]): e[3] for e in frames[t0]['E']}
            left_d = [[x[0], list(x[1]) if isinstance(x[1], tuple) else x[1], names_r.get(x[1]) if 'rec' in x[0] else None,
                       list(x[2]) if isinstance(x[2], tuple) else x[2]] for x in left]
            w.write(json.dumps({'match': m, 't0': t0, 'gap_prev': t0 - max(t for t in ts if t < t0), 'me': me,
                                'per_frame': rows, 'left_t0_vs_sim_t0p1': left_d}) + '\n')
            w.flush()
            print(m, t0, rows[t0], len(left_d), flush=True)


if __name__ == '__main__':
    main()
