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
MAX_ROUNDS = int(os.environ.get('RECON_ROUNDS', '40'))   # RECON-7 opt-in (absent = 40, byte-identical): 2 of the 82 failures after RECON-5 stopped at round 39 with a healing shift still ahead
STRUCT = ('add', 'drop')
CYC = int(os.environ.get('RECON_CYC', '0'))   # RECON-5 opt-in: absent = byte-identical to v3
FORM = int(os.environ.get('RECON_FORM', '0'))  # RECON-6 opt-in: absent = byte-identical to RECON-5 / v3 (forms.form_repairs as extra start members)


def key_of(plan):
    return hashlib.sha1(json.dumps(recon.runnable(plan), sort_keys=True).encode()).hexdigest()


def full_run(plan, frames, me, end, work, log):
    """sme_live.base_run, but an ability base_run turned into a skip (its play was refused in THAT plan) is tried again
    in every later plan: base_run's skip is in place and was inherited by every child, so an edit that un-refuses the
    play (e.g. restores the cycle) still ran without the press (RECON-2: 031310 / 222707 planted drops, hero press)."""
    for c in plan['cmds']:
        if c['kind'] == 'skip' and c.get('_src', {}).get('run_skip'):
            c['kind'] = 'ability'
    before = {id(c) for c in plan['cmds'] if c['kind'] == 'skip'}
    o, an = sme_live.base_run(plan, frames, me, end, work, log)
    for c in plan['cmds']:
        if c['kind'] == 'skip' and id(c) not in before:
            c['_src'] = dict(c.get('_src', {}), run_skip=True)
    return o, an


def search(rec, frames, out, beam=4, ops=None, start=None):
    """start: a plan to search from instead of the base plan (plant_recall.py: an exact plan with one planted error)."""
    me, end = rec['my_side'], max(frames)
    tab = recon.Tab()
    plan = start or recon.base_plan(rec, frames)
    e0 = recon.start_elixir(frames, plan, me, tab)
    recon.with_elixir_base(plan, tab, e0)
    work = os.path.join(out, 'work')
    log = []
    inits, start_edits = [], []
    if CYC and not start:
        # RECON-5, own side: a tap of ours that no extracted play explains is a missed play (our action log). When our own cycle
        # fails and the restored plan fits it, the restore IS the base plan; otherwise it is one more engine-scored start.
        rt = recon.restore_taps(rec, plan, me)
        if rt:
            if not plan['_cycle_base'][me] and rt[1]['_cycle_base'][me]:
                start_edits, plan = [rt[0]], rt[1]
                recon.with_elixir_base(plan, tab, e0)
            else:
                inits.append((rt[0], 1, rt[1]))
        # RECON-5 (opt-in): an opponent whose extracted plays fit no deal ran on the IDENTITY deal (opp_deal_fit None), whose first
        # refused play was the early divergence of the opponent_no_fitting_deal records. Part A: the deal that runs the most plays;
        # part B: deck-constrained repairs (cyc.py) scored by the engine as extra starting members.
        for sd in (0, 1):
            if sd != me and not plan['_cycle_base'][sd]:
                seq = [plan['decks'][sd].index(plan['cmds'][k]['card']) for _, k in recon.seq_of(plan, sd)]
                ident = dict(plan, cmds=[dict(c) for c in plan['cmds']], deals=list(plan['deals']))      # v3's own start (the identity deal) stays a candidate: no regression by construction
                inits.append(('identity deal (v3 start)', 0, ident))
                plan['deals'][sd], ran = recon.best_prefix_deal(seq)
                for desc, c, pp in recon.cycle_repairs(plan, frames, sd, tab, e0):
                    inits.append((desc, c, pp))
    if FORM and not start:
        # RECON-6: the count rule (forms.py) explains the observed Hero / EV1 forms of the opponent's plays only with deleted plays (an invented
        # play, or a Mirror copy read as the copied card): each such repair is an extra starting member, scored by the engine like a cycle repair.
        import forms
        for sd in (0, 1):
            if sd != me:
                for desc, c, pp in forms.form_repairs(rec, plan, sd, tab, e0):
                    inits.append((desc, c, pp))
    o, an = full_run(plan, frames, me, end, work, log)
    if o is None:
        return None, plan, log
    members = [dict(plan=plan, o=o, an=an, edits=list(start_edits), cost=3 * len(start_edits), given_up=[])]
    seen = {key_of(plan)}
    if inits:
        cl = []
        for desc, c, pp in inits:
            if key_of(pp) in seen:
                continue
            seen.add(key_of(pp))
            o2, an2 = full_run(pp, frames, me, end, work, log)
            if o2 is None:
                cl.append([desc, None])
                continue
            m2 = dict(plan=pp, o=o2, an=an2, edits=[] if c == 0 else [desc], cost=c * recon.COST['add'], given_up=[])
            cl.append([desc, list(full_key(m2))])
            members.append(m2)
        log.append({'round': -1, 'cyc': cl})
        members.sort(key=lambda m: full_key(m), reverse=True)
        members = members[:beam]
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
            better.sort(key=lambda b: b[:2], reverse=True)   # stable: better[0] = the max(...) the log named before
            log.append({'round': rnd, 'd': d, 'legal': len(hs), 'refused': dict(why), 'better': len(better),
                        'best': better and [better[0][0], recon.describe(m['plan'], better[0][2])],
                        'top': [recon.describe(m['plan'], b[2]) for b in better[:40]]})
            if not better:
                m = dict(m, given_up=m['given_up'] + [d])
                cands.append((full_key(m), m))
                continue
            for k, nc, e, p in better[:beam]:
                seen.add(key_of(p))
                o2, an2 = full_run(p, frames, me, end, work, log)
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
    rec, frames_path, out, beam, ops = args[:5]
    start = args[5] if len(args) > 5 else None
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
        best, plan, log = search(rec, frames, mo, beam, ops, start)
        if best is None:
            res = {'match': rec['match'], 'error': 'base plan failed', 'log': log}
        else:
            me = rec['my_side']
            an = sme_live.reclassify(plan, frames, me, best['an'], best['o'], os.path.join(mo, 'work'))
            by = {x['t']: x for x in best['o']}
            res = {'match': rec['match'], 'flags': rec['flags'], 'frames': an['frames'], 'counts': an['counts'],
                   'first_div': an['first'], 'first_detail': sme_live.describe_first(by, frames, me, an['first']),
                   'edits': best['edits'], 'edit_cost': best['cost'], 'given_up': best['given_up'], 'log': log}
            if sme_live.CLS_TICKS:   # RECON-4 (SME_CLS_TICKS=1): every non-exact frame by class, for the ASSIGN off / on frame guard
                res['cls_ticks'] = {c: sorted(t for t, x in an['cls'].items() if x == c) for c in sorted(set(an['cls'].values()) - {'exact'})}
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
