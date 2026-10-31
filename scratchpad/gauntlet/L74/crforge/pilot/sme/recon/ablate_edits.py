"""RECON-5 step 1 (pod): ablation of EVERY kept edit of a recon final plan, not only the adds (ablate.py).
The final plan (RUN/<match>/recon_plan.json) is diffed against the base plan (recon.base_plan on the same input record); each
difference is reverted ALONE and the whole match is re-scored by the full comparator (recon_search.full_run + reclassify):
  add      an added command (source recon_add)  -> removed             drop   a base command absent from the final plan -> re-inserted
  point    x / y differs from the base command  -> base point          shift  run differs                               -> base run
  repress  unit differs (a press re-bound)      -> base unit (+ run)
Verdict as ablate.py: needed = without the edit the match is worse ((exact frames, first div) smaller), unneeded = equal, harmful
= better. A flagged-but-exact record is CONFIRMED when its kind (a)-(drop) edits are all needed (shifts reported apart).
  python3 recon/ablate_edits.py --inputs I.jsonl --frames FRAMEDIR --runs RUNDIR --matches M1,M2 --out OUTDIR [--workers 4]
  -> OUTDIR/ablate_edits.jsonl, one row per match: {match, with, edits: [{kind, desc, without, verdict}]}"""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import recon_search  # noqa: E402
import sme_live  # noqa: E402
from ablate import frames_of  # noqa: E402

REPAIR = 60       # a dropped and an added play of one card within this many ticks are one re-dated / re-pointed play


def key(c):
    s = c.get('_src', {})
    return (c['side'], c['kind'] if c['kind'] != 'skip' else 'ability', c.get('card'), s.get('tick'), s.get('source'), s.get('lo'), s.get('hi'))


def score(plan, frames, me, work):
    o, an = recon_search.full_run(plan, frames, me, max(frames), work, [])
    if o is None:
        return None
    an = sme_live.reclassify(plan, frames, me, an, o, work)
    return {'counts': an['counts'], 'first': an['first']}


def revert_edits(base, final):
    """-> [(kind, description, plan with that one difference reverted)]. kind: add / drop / replace (a base play dropped AND the
    same card added within REPAIR ticks = one re-dated / re-pointed play) / point / shift / repress / noop (the revert leaves the
    runnable plan unchanged: not an edit)."""
    bkeys = {}
    for k, c in enumerate(base['cmds']):
        bkeys.setdefault(key(c), []).append(k)
    used, f2b, adds = set(), {}, []          # f2b: final index -> base index
    for k, c in enumerate(final['cmds']):
        j = next((j for j in bkeys.get(key(c)) or [] if j not in used), None)
        if j is None:
            adds.append(k)
        else:
            used.add(j)
            f2b[k] = j
    b2f = {j: k for k, j in f2b.items()}
    gone = [j for j in range(len(base['cmds'])) if j not in used]
    pairs, free_adds = [], list(adds)
    for j in list(gone):                      # pair a dropped play with the nearest added play of its card and side
        b = base['cmds'][j]
        cand = [k for k in free_adds if final['cmds'][k]['kind'] == b['kind'] == 'play' and final['cmds'][k]['side'] == b['side']
                and (final['cmds'][k].get('card') == b.get('card') or final['cmds'][k].get('card') == 'Mirror') and abs(final['cmds'][k]['run'] - b['run']) <= REPAIR]
        if cand:
            k = min(cand, key=lambda k: abs(final['cmds'][k]['run'] - b['run']))
            free_adds.remove(k); gone.remove(j); pairs.append((j, k))
    out = []

    def put_back(plan_, j):
        """plan_ with base command j inserted (ability unit re-mapped to the final index of the base play it names), or None."""
        bc = dict(base['cmds'][j])
        if bc.get('unit'):
            n, u = bc['unit'][3:].split('_')
            if int(n) not in b2f:
                return None
            bc['unit'] = 'cmd%d_%s' % (b2f[int(n)], u)
        pos = sum(1 for c in plan_['cmds'] if c['run'] <= bc['run'])
        return recon.apply_edit(plan_, {'op': 'add', 'pos': pos, 'cmd': bc})

    for k in free_adds:
        c = final['cmds'][k]
        out.append(('add', 'add s%d %s R%d (%s,%s)' % (c['side'], c.get('card', c.get('unit')), c['run'], c.get('x'), c.get('y')),
                    recon.apply_edit(final, {'op': 'drop', 'i': k})))
    for j, k in pairs:
        c, b = final['cmds'][k], base['cmds'][j]
        p = recon.apply_edit(final, {'op': 'drop', 'i': k})
        p = put_back(p, j) if p else None
        out.append(('replace', 'replace s%d %s base R%d (%s,%s) -> R%d (%s,%s)' % (c['side'], c['card'], b['run'], b['x'], b['y'], c['run'], c['x'], c['y']), p))
    for j in gone:
        b = base['cmds'][j]
        out.append(('drop', 'drop s%d %s R%d (%s,%s)' % (b['side'], b.get('card', b.get('unit')), b['run'], b.get('x'), b.get('y')),
                    put_back(final, j)))
    for k, j in sorted(f2b.items()):
        c, b = final['cmds'][k], base['cmds'][j]
        if c['kind'] == 'play' and (c['x'], c['y']) != (b['x'], b['y']):
            out.append(('point', 'point s%d %s (%s,%s) was (%s,%s)' % (c['side'], c['card'], c['x'], c['y'], b['x'], b['y']),
                        recon.apply_edit(final, {'op': 'point', 'i': k, 'x': b['x'], 'y': b['y']})))
        if c['kind'] != 'play' and c.get('unit') and c['unit'] != b['unit']:
            n, u = c['unit'][3:].split('_')
            bn, bu = b['unit'][3:].split('_')
            if f2b.get(int(n)) == int(bn) and u == bu:   # same press target after the index shift of an add / drop
                pass
            elif int(bn) in b2f:
                out.append(('repress', 'repress s%d press %s R%d was %s R%d' % (c['side'], c['unit'], c['run'], b['unit'], b['run']),
                            recon.apply_edit(final, {'op': 'repress', 'i': k, 'run': b['run'], 'n': b2f[int(bn)], 'u': int(bu)})))
                continue
        if c['run'] != b['run']:
            out.append(('shift', 'shift s%d %s R%d was R%d' % (c['side'], c.get('card', c.get('unit')), c['run'], b['run']),
                        recon.apply_edit(final, {'op': 'shift', 'i': k, 'run': b['run']})))
    return out


def job(args):
    rec, fp, plan, work = args
    frames, me = frames_of(rec, fp), rec['my_side']
    os.makedirs(work, exist_ok=True)
    base = recon.base_plan(rec, frames)
    full = score(plan, frames, me, work)
    rows = []
    for kind, desc, p in revert_edits(base, plan):
        if p is None:
            rows.append({'kind': kind, 'desc': desc, 'verdict': 'error'})
            continue
        if recon.runnable(p) == recon.runnable(plan):
            rows.append({'kind': 'noop', 'desc': desc, 'verdict': 'noop'})
            continue
        s = score(p, frames, me, work)
        ex = lambda r: r['counts'].get('exact', 0)                    # noqa: E731
        fd = lambda r: r['first'] if r['first'] is not None else 10 ** 9   # noqa: E731
        v = 'error' if s is None or full is None else ('needed' if (ex(s), fd(s)) < (ex(full), fd(full)) else
                                                        'unneeded' if (ex(s), fd(s)) == (ex(full), fd(full)) else 'harmful')
        rows.append({'kind': kind, 'desc': desc, 'without': s, 'verdict': v})
    return {'match': rec['match'], 'with': full, 'edits': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--frames', required=True); ap.add_argument('--runs', required=True)
    ap.add_argument('--matches', required=True); ap.add_argument('--out', required=True); ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    recs = {json.loads(l)['match']: json.loads(l) for l in open(a.inputs)}
    want = a.matches.split(',')
    jobs = []
    for m in recs:
        if any(m == w or m.endswith(w) for w in want):
            pf = os.path.join(a.runs, m, 'recon_plan.json')
            jobs.append((recs[m], os.path.join(a.frames, m + '.jsonl'), json.load(open(pf)), os.path.join(a.out, 'abl_work', m)))
    print('jobs', len(jobs), flush=True)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'ablate_edits.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(job, jobs):
            w.write(json.dumps(res) + '\n'); w.flush()
            print(res['match'][-6:], res['with'], [(e['kind'], e['desc'], e['verdict']) for e in res['edits']], flush=True)


if __name__ == '__main__':
    main()
