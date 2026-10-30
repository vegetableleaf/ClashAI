"""RECON engine-scored search (pod; design ../RECON.md section 6). Runs beside the gate's sme_live.py (sme11f), with the
gate's env (recon_run.sh sets it, as f1fix/runH.sh does):

  python3 recon/recon_search.py all --inputs INPUTS.jsonl --frames FRAMEDIR --out OUT [--workers 8] [--only M1,M2]
        [--beam 4] [--ops shift,joint,swap,point,add,drop]

Per match: base plan (sme_live.plan_from on the record, no fitter) -> beam search left to right: at each member's first
divergence d, the legal edits (recon.legal_hypotheses) are run on crforge (sme.run_batch) over [d-125, d+400] and scored
by sme_live.objective; the top B by (objective, - edit cost) survive; an add / drop must move d by >= HEAL ticks. The
final plan is scored by the full comparator (sme_live.analyse + reclassify), with the planted suite (SME_PLANTS).
--ops shift,point --beam 1 is the fitter's move set (a regression check against sme_live.fit_match)."""
import argparse, collections, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402

sme_live.runnable = recon.runnable        # base_run / plant_suite read crforge's plan through this name
HEAL = 20
MAX_ROUNDS = 40
STRUCT = ('add', 'drop')


def key_of(plan):
    return hashlib.sha1(json.dumps(recon.runnable(plan), sort_keys=True).encode()).hexdigest()


def search(rec, frames, out, beam=4, ops=None):
    me, end = rec['my_side'], max(frames)
    tab = recon.Tab()
    plan = recon.base_plan(rec, frames)
    e0 = recon.start_elixir(frames, plan, me, tab)
    recon.with_elixir_base(plan, tab, e0)
    work = os.path.join(out, 'work')
    log = []
    o, an = sme_live.base_run(plan, frames, me, end, work, log)
    if o is None:
        return None, plan, log
    members = [dict(plan=plan, o=o, an=an, edits=[], cost=0, given_up=[])]
    seen = {key_of(plan)}
    for rnd in range(MAX_ROUNDS):
        cands, live = [], False
        for m in members:
            eps = [e for e in sme_live.episodes(m['an']) if e[0] not in m['given_up']]
            if not eps:
                cands.append((full_key(m), m))
                continue
            live = True
            d = eps[0][0]
            skip = [(a, b) for a, b, _ in sme_live.episodes(m['an']) if a in m['given_up']]
            by = {x['t']: x for x in m['o']}
            detail = sme_live.describe_first(by, frames, me, d)
            why = collections.Counter()
            hs = [h for h in recon.legal_hypotheses(m['plan'], frames, d, detail, tab, me, e0, why)
                  if (ops is None or h[0]['op'] in ops) and key_of(h[2]) not in seen]
            lo, hi = max(0, d - recon.WIN - 5), min(end, d + 400)
            outs = run_batch([(recon.runnable(p), hi + 3, lo) for _, _, p in hs], work) if hs else []
            better = []
            for (e, cost, p), ob in zip(hs, outs):
                if ob is None:
                    continue
                k = sme_live.objective(sme_live.analyse(ob, frames, me, lo, hi), hi, skip)
                if k[0] > d + (HEAL if e['op'] in STRUCT else 0):
                    better.append((k, -cost, e, p))
            log.append({'round': rnd, 'd': d, 'legal': len(hs), 'refused': dict(why), 'better': len(better),
                        'best': better and [max(better, key=lambda b: b[:2])[0], recon.describe(m['plan'], max(better, key=lambda b: b[:2])[2])]})
            if not better:
                m = dict(m, given_up=m['given_up'] + [d])
                cands.append((full_key(m), m))
                continue
            better.sort(key=lambda b: b[:2], reverse=True)
            for k, nc, e, p in better[:beam]:
                seen.add(key_of(p))
                o2, an2 = sme_live.base_run(p, frames, me, end, work, log)
                if o2 is not None:
                    m2 = dict(plan=p, o=o2, an=an2, edits=m['edits'] + [recon.describe(m['plan'], e)], cost=m['cost'] - nc,
                              given_up=list(m['given_up']))
                    cands.append((full_key(m2), m2))
        cands.sort(key=lambda c: c[0], reverse=True)
        uniq, ks = [], set()
        for c in cands:
            kk = key_of(c[1]['plan']) + str(c[1]['given_up'])
            if kk not in ks:
                ks.add(kk)
                uniq.append(c[1])
        members = uniq[:beam]
        if not live:
            break
    best = members[0]
    return best, best['plan'], log


def full_key(m):
    """Whole-match ranking: (first div outside given-up episodes, - div frames, - edit cost)."""
    end = max(m['an']['cls']) if m['an']['cls'] else 0
    skip = [(a, b) for a, b, _ in sme_live.episodes(m['an']) if a in m['given_up']]
    k = sme_live.objective(m['an'], end, skip)
    first = next((t for t in sorted(m['an']['cls']) if m['an']['cls'][t] == 'div'), end + 1)
    return (first, k[1], -m['cost'])


def do_match(args):
    rec, frames_path, out, beam, ops = args
    mo = os.path.join(out, rec['match'])
    os.makedirs(mo, exist_ok=True)
    try:
        frames = sme_live.load_frames(frames_path)
        if sme_live.HIDDEN:   # as sme_live.do_match (round 8.4 / ENG-FIX2)
            for h in rec.get('reader_hidden') or ():
                for t in frames:
                    if h['last'] < t <= h['end']:
                        frames[t].setdefault('H', []).append([h['side'], h['name'], (h['track'] or {}).get(str(t))]
                                                             + ([sme_live.hidden_ref(h['track'], t)] if sme_live.HIDDEN_ASSIGN else []))
        best, plan, log = search(rec, frames, mo, beam, ops)
        if best is None:
            res = {'match': rec['match'], 'error': 'base plan failed', 'log': log}
        else:
            me = rec['my_side']
            an = sme_live.reclassify(plan, frames, me, best['an'], best['o'], os.path.join(mo, 'work'))
            by = {x['t']: x for x in best['o']}
            res = {'match': rec['match'], 'flags': rec['flags'], 'frames': an['frames'], 'counts': an['counts'],
                   'first_div': an['first'], 'first_detail': sme_live.describe_first(by, frames, me, an['first']),
                   'edits': best['edits'], 'edit_cost': best['cost'], 'given_up': best['given_up'], 'log': log}
            if sme_live.PLANTS:
                import plant_suite
                res['plants'] = plant_suite.run(plan, frames, me, an, best['o'], os.path.join(mo, 'work'))
        json.dump(plan, open(os.path.join(mo, 'recon_plan.json'), 'w'), indent=0)
    except Exception as e:  # one bad match must not stop the batch
        import traceback
        res = {'match': rec['match'], 'error': repr(e), 'trace': traceback.format_exc()[-1500:]}
    json.dump(res, open(os.path.join(mo, 'recon_result.json'), 'w'), indent=1, default=str)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['all', 'one'])
    ap.add_argument('--inputs', required=True); ap.add_argument('--frames', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=8); ap.add_argument('--only'); ap.add_argument('--beam', type=int, default=4)
    ap.add_argument('--ops')
    a = ap.parse_args()
    ops = set(a.ops.split(',')) if a.ops else None
    recs = [json.loads(l) for l in open(a.inputs)]
    if a.only:
        keep = set(a.only.split(','))
        recs = [r for r in recs if r['match'] in keep or r['match'][-6:] in keep]
    os.makedirs(a.out, exist_ok=True)
    jobs = [(r, os.path.join(a.frames, r['match'] + '.jsonl'), a.out, a.beam, ops) for r in recs]
    with open(os.path.join(a.out, 'recon_results.jsonl'), 'a') as w, \
            ProcessPoolExecutor(a.workers if a.mode == 'all' else 1) as ex:
        for res in ex.map(do_match, jobs):
            w.write(json.dumps(res, default=str) + '\n'); w.flush()
            print(res['match'], res.get('error') or (res.get('counts'), res.get('first_div'), res.get('edits')), flush=True)


if __name__ == '__main__':
    main()
