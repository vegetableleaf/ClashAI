"""TARGET-VAL (M1c): per-unit target agreement, live reader vs crforge, on SME-exact frames (pod; reader-agnostic).
    env <runR.sh gate env> SME_TGT=2 SME_BUILD=/workspace/tval/build SME_THREADS=10 \
      python3 tval_score.py RESULTS.jsonl RUNDIR FRAMESDIR READERDIR OUT.jsonl [MATCH ...]
RESULTS / RUNDIR = a gate run (results.jsonl + <match>/plan.json); FRAMESDIR = the SME recorded frames (exact ticks);
READERDIR = per-match rows in the per-unit interface: {"t", "G": [[side, x, y, name, id, raw_tgt, acq_tgt, prog, tower]],
"P": [[side, x, y, card, src_id, tgt_id]]} (raw = the reader's reference; acq = after LiveCues.units' filter).
Engine side: SmeRun SME_TGT=2 rows (T/C: [..., raw_ref, CfCore.acquired, attacking, flags]; P: [..., owner, target]).
Exact frames = recorded ticks before the match's first divergence, not torn (prefix-exact: the lock history is equal
too). Bodies pair by unique exact (side, x, y); targets map through the same frame's pairing. One JSON line per match."""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_DIR', '/workspace/smeR/sme'))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

BLD_ONLY = ('Giant', 'Hog', 'Balloon', 'Golem', 'Ram', 'WallBreaker', 'LavaHound', 'Lava', 'ElectroGiant', 'GoblinGiant',
            'RoyalGiant', 'BattleRam', 'SkeletonBarrel', 'GoblinBarrel')
SIEGE = ('XBow', 'Xbow', 'Mortar')
WIN = 6  # retarget-timing window (ticks) searched for the reader's target on the engine side


def klass(e):
    n, fl = e[2], e[15]
    if fl & 4 or e[1] == 'T':
        return 'tower'
    if any(n.startswith(s) for s in SIEGE):
        return 'siege'
    if fl & 1:
        return 'building'
    if any(s in n for s in BLD_ONLY):
        return 'bld_only'
    return 'air' if fl & 2 else 'troop'


def pairing(sim, rows, key):
    a, b = {}, {}
    for e in sim:
        a.setdefault(key(e), []).append(e)
    for r in rows:
        b.setdefault((r[0], r[1], r[2]), []).append(r)
    out = {}
    for k, v in b.items():
        if len(v) == 1 and len(a.get(k, ())) == 1:
            out[k] = (a[k][0], v[0])
        elif len(v) == len(a.get(k, ())) > 1:  # co-located bodies (a hero and its companion): pair by unique name
            na = {}
            for e in a[k]:
                na.setdefault(e[2], []).append(e)
            for r in v:
                c = na.get(r[3]) or ()
                if len(c) == 1 and sum(x[3] == r[3] for x in v) == 1:
                    out[k + (r[3],)] = (c[0], r)
    return out


def score(m, obs, frames, rd, res):
    by = {o['t']: o for o in obs}
    first, torn = res.get('first_div'), set(res.get('torn_ticks') or ())
    ticks = sorted(t for t in frames if (first is None or t < first) and t not in torn and t in rd and t in by
                   and 'G' in rd[t])
    eng = {}  # tick -> id -> (raw, acq)
    for t, o in by.items():
        eng[t] = {e[0]: (e[12], e[13]) for e in o['E'] if e[1] in 'TC' and len(e) >= 16}
    C, D, prev_acq = {}, [], {}
    inc = lambda k, n=1: C.__setitem__(k, C.get(k, 0) + n)  # noqa: E731
    for t in ticks:
        S = [e for e in by[t]['E'] if e[1] in 'TC']
        name = {e[0]: e[2] for e in S}
        tower_ids = {e[0] for e in S if e[1] == 'T'}
        pos = {e[0]: (e[4], e[5]) for e in S}
        P = pairing(S, rd[t]['G'], lambda e: (e[3], e[4], e[5]))
        inc('frames'); inc('rd_rows', len(rd[t]['G'])); inc('paired', len(P))
        g2s = {r[4]: e[0] for e, r in P.values()}
        mp = lambda g: -1 if g is None else g2s.get(g, 'U')  # noqa: E731
        acq_rows = []
        for e, r in P.values():
            if len(e) < 16:
                continue
            k = klass(e)
            sh = mp(prev_acq.get(r[4])) if r[4] in prev_acq else None
            prev_acq[r[4]] = r[6]
            mets = [('raw', e[12], mp(r[5])), ('acq', e[13], mp(r[6]))]
            if len(r) > 9:  # acq2 = a PROPOSED reader-side rule (the reader rows' 10th column), scored the same way
                mets.append(('acq2', e[13], mp(r[9])))
            for met, ev, rv in mets:
                ok = ev == rv
                inc(f'{met}|{k}|n'); inc(f'{met}|{k}|ok', ok)
                if met != 'raw' and (ev != -1 or rv != -1):
                    inc(f'{met}_active|{k}|n'); inc(f'{met}_active|{k}|ok', ok)
                if met == 'acq':
                    acq_rows.append((e, rv))
                    if sh is not None:
                        inc('ctl_shift|n'); inc('ctl_shift|ok', ev == sh)
                if ok:
                    continue
                if rv == 'U':
                    why = 'tgt_unpaired'
                elif met != 'raw' and e[12] == mp(r[5]):
                    why = 'acq_filter_eng_keeps' if ev != -1 and rv == -1 else \
                          'acq_filter_rd_keeps' if ev == -1 else 'acq_filter_other'
                elif ev in tower_ids and rv == -1:
                    why = 'eng_tower_rd_none'
                elif rv in tower_ids and ev == -1:
                    why = 'rd_tower_eng_none'
                else:
                    j = 0 if met == 'raw' else 1
                    d = next((d for a in range(1, WIN + 1) for d in (-a, a)
                              if e[0] in eng.get(t + d, {}) and eng[t + d][e[0]][j] == rv), None)
                    why = f'timing{d:+d}' if d is not None else ('eng_none' if ev == -1 else 'rd_none' if rv == -1
                                                                 else 'diff_target')
                inc(f'{met}|why|{why}')
                tg = ev if ev != -1 else rv
                dist = None
                if tg in pos:
                    dist = round(((pos[tg][0] - e[4]) ** 2 + (pos[tg][1] - e[5]) ** 2) ** 0.5 / 1000, 3)
                D.append([m, t, met, why, k, e[2], name.get(ev, ev), name.get(rv, rv), dist, e[14]])
        # planted control: rotate the reader's acq targets among this frame's targeted attackers
        tg = [rv for _, rv in acq_rows if rv not in (-1, 'U')]
        if len(set(tg)) > 1:
            rot = iter(tg[1:] + tg[:1])
            for e, rv in acq_rows:
                if rv not in (-1, 'U'):
                    inc('ctl_rot|n'); inc('ctl_rot|ok', e[13] == next(rot))
        # projectiles
        PP = pairing([e for e in by[t]['E'] if e[1] == 'P' and len(e) >= 14], rd[t].get('P') or [],
                     lambda e: (e[3], e[4], e[5]))
        inc('proj_rd', len(rd[t].get('P') or [])); inc('proj_paired', len(PP))
        for e, r in PP.values():
            k = 'proj_' + ('spell' if e[12] not in name and e[12] not in g2s.values() else 'attack')
            for met, ev, rv in (('src', e[12], mp(r[4])), ('tgt', e[13], mp(r[5]))):
                inc(f'{met}|{k}|n'); inc(f'{met}|{k}|ok', ev == rv)
                if ev != rv and len(D) < 10 ** 6:
                    D.append([m, t, met, 'proj', k, e[2], name.get(ev, ev), name.get(rv, rv), None, None])
    return C, D


def main():
    resf, rundir, frdir, rddir, outp = sys.argv[1:6]
    only = set(sys.argv[6:])
    todo = []
    for l in open(resf):
        r = json.loads(l)
        m = r['match']
        pp = os.path.join(rundir, m, 'plan.json')
        if r.get('flags') or r.get('error') or not os.path.exists(pp) or (only and m not in only):
            continue
        todo.append((m, r, json.load(open(pp))))
    work = outp + '.work'
    with open(outp, 'w') as w, open(outp + '.dis.jsonl', 'w') as wd:
        for i in range(0, len(todo), 10):
            chunk = todo[i:i + 10]
            frs = [load_frames(os.path.join(frdir, m + '.jsonl')) for m, _, _ in chunk]
            outs = run_batch([(runnable(p), max(f) + 1, 0) for (m, r, p), f in zip(chunk, frs)], work)
            for (m, r, p), f, obs in zip(chunk, frs, outs):
                rd = {x['t']: x for x in map(json.loads, open(os.path.join(rddir, m + '.jsonl')))}
                if obs is None:
                    w.write(json.dumps({'match': m, 'error': 'engine run failed'}) + '\n'); continue
                C, D = score(m, obs, f, rd, r)
                strict = set(r['counts']) == {'exact'}
                w.write(json.dumps({'match': m, 'strict': strict, 'first_div': r.get('first_div'), 'C': C}) + '\n')
                for d in D:
                    wd.write(json.dumps(d) + '\n')
                w.flush()
                print(m, strict, C.get('frames'), C.get('acq|troop|ok'), '/', C.get('acq|troop|n'), flush=True)
            del outs


if __name__ == '__main__':
    main()
