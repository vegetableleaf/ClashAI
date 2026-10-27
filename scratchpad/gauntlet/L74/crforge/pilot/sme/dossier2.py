"""Body-position dossier, all matches (ticket A2c round 4): mechanism features of each first divergence.
    SME_TGT=1 SME_LIB=... SME_BUILD=<SmeRun built with SME_TGT support> python3 dossier2.py RUNDIR LIST TGTDIR OUT.jsonl
LIST: lines "<match> <onset>". TGTDIR: tgt_frames.py output (reader gen / target_gen / state per body).
For the onset t0 and the previous recorded frame tp (exact or torn, so every body is paired by position there):
every body whose position differs at t0 gets its recorded and sim motion tp -> t0, its sim target (id -> row) and its
recorded target (gen -> the sim id of the body at the same point at tp) at tp and t0, its recorded state, the nearest
bodies at tp, the area effects / projectiles within 2500 at tp..t0, and its sim creation line."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

FRAMES = '/workspace/pilot/sme_live/frames2'


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def one(run, m, t0, tgtdir):
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    frames = load_frames(os.path.join(FRAMES, m + '.jsonl'))
    tg = load_frames(os.path.join(tgtdir, m + '.jsonl'))
    ts = sorted(frames)
    tp = max(t for t in ts if t < t0)
    o = run_batch([(runnable(plan), t0 + 45, max(0, tp - 60))], os.path.join(run, m, 'dossier2'))[0]
    by = {s['t']: s for s in o}
    born = {}
    for s in o:
        for e in s['E']:
            born.setdefault(e[0], s['t'])
    S = lambda t: [e for e in by[t]['E'] if e[1] in 'TC']  # noqa: E731
    # pair recorded gens to sim ids at tp by exact (side, x, y)
    simpos_tp = {}
    for e in S(tp):
        simpos_tp.setdefault((e[3], e[4], e[5]), []).append(e)
    gen2sim, rec_tp = {}, {}
    for r in tg.get(tp, {'G': []})['G']:
        side, x, y, card, gen, tgen, st = r
        rec_tp[gen] = r
        c = simpos_tp.get((side, x, y))
        if c and len(c) == 1:
            gen2sim[gen] = c[0][0]
    rec_t0 = {r[4]: r for r in tg.get(t0, {'G': []})['G']}
    sim_tp = {e[0]: e for e in S(tp)}
    sim_t0 = {e[0]: e for e in S(t0)}
    name = lambda i: (sim_t0.get(i) or sim_tp.get(i) or [None, None, '?'])[2] if i is not None and i >= 0 else '-'  # noqa: E731
    out = []
    for gen, r0 in rec_t0.items():
        sid = gen2sim.get(gen)
        if sid is None or sid not in sim_t0 or gen not in rec_tp:
            continue
        rp, s0, sp = rec_tp[gen], sim_t0[sid], sim_tp[sid]
        off = (r0[1] - s0[4], r0[2] - s0[5])
        if off == (0, 0):
            continue
        # sim speed over the 10 ticks before tp
        hist = [by[t] for t in range(tp - 10, tp + 1) if t in by]
        pts = [next((e for e in h['E'] if e[0] == sid), None) for h in hist]
        pts = [p for p in pts if p]
        speed = man((pts[0][4], pts[0][5]), (pts[-1][4], pts[-1][5])) / max(1, len(pts) - 1) if len(pts) > 1 else None
        # sim per-tick track tp..t0
        track = []
        for t in range(tp, t0 + 1):
            e = next((e for e in by[t]['E'] if e[0] == sid), None)
            track.append((t, e[4], e[5], e[12] if e and len(e) > 12 else None) if e else (t, None))
        rt_tp = gen2sim.get(rp[5]) if rp[5] is not None else None
        rt_t0 = gen2sim.get(r0[5]) if r0[5] is not None else None
        near = sorted((man((e[4], e[5]), (sp[4], sp[5])), e[2], e[3]) for e in S(tp) if e[0] != sid and
                      man((e[4], e[5]), (sp[4], sp[5])) < 1500)[:5]
        fx = sorted({(e[1] + ':' + e[2]) for t in range(tp, t0 + 1) for e in by[t]['E'] if e[1] in 'AP' and
                     man((e[4], e[5]), (sp[4], sp[5])) < 2500})
        out.append({'row': s0[2], 'side': s0[3], 'src': s0[8], 'born': born.get(sid), 'age': t0 - born.get(sid, t0),
                    'at': [s0[4], s0[5]], 'off': off, 'rec_move': [r0[1] - rp[1], r0[2] - rp[2]],
                    'sim_move': [s0[4] - sp[4], s0[5] - sp[5]], 'speed': speed,
                    'sim_tgt': [name(sp[12]) if len(sp) > 12 else None, name(s0[12]) if len(s0) > 12 else None],
                    'sim_tgt_id': [sp[12] if len(sp) > 12 else None, s0[12] if len(s0) > 12 else None],
                    'rec_tgt': [name(rt_tp) if rt_tp is not None else ('-' if rp[5] is None else 'unpaired'),
                                name(rt_t0) if rt_t0 is not None else ('-' if r0[5] is None else 'unpaired')],
                    'rec_tgt_id': [rt_tp, rt_t0], 'rec_state': [rp[6], r0[6]],
                    'near_tp': near, 'fx': fx, 'track': track})
    unpaired = len(rec_t0) - sum(1 for g in rec_t0 if g in gen2sim)
    return {'match': m, 't0': t0, 'tp': tp, 'gap': t0 - tp, 'bodies': out, 'rec_unpaired_at_t0': unpaired}


def main():
    run, lst, tgtdir, outp = sys.argv[1:5]
    with open(outp, 'w') as w:
        for line in open(lst):
            if not line.strip():
                continue
            m, t0 = line.split()[:2]
            try:
                r = one(run, m, int(t0), tgtdir)
            except Exception as e:  # noqa: BLE001
                import traceback
                r = {'match': m, 'error': repr(e), 'trace': traceback.format_exc()[-800:]}
            w.write(json.dumps(r) + '\n'); w.flush()
            print(m, len(r.get('bodies', [])), r.get('error', ''), flush=True)


if __name__ == '__main__':
    main()
