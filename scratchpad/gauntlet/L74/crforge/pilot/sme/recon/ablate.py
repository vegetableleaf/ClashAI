"""RECON precision (RECON.md section 7 item 3; pod): every structural edit a recon_search run KEPT (an added play / press:
source recon_add) is removed again from the final plan and the whole match is re-scored by the full comparator
(base_run + reclassify). needed = without it the match is worse (fewer exact frames or an earlier first div); unneeded =
the same; harmful = without it the match is better. An unneeded or harmful add is a phantom the full-match check
contradicts.
  python3 recon/ablate.py --inputs I.jsonl --frames FRAMEDIR --runs RUN1,RUN2 --out OUTDIR [--workers 4]  (-> OUTDIR/ablate.jsonl)"""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import recon_search  # noqa: E402,F401  (sets sme_live.runnable = recon.runnable)
import sme_live  # noqa: E402


def frames_of(rec, path):
    frames = sme_live.load_frames(path)
    if sme_live.HIDDEN:   # as recon_search.do_match
        for h in rec.get('reader_hidden') or ():
            for t in frames:
                if h['last'] < t <= h['end']:
                    frames[t].setdefault('H', []).append([h['side'], h['name'], (h['track'] or {}).get(str(t))]
                                                         + ([sme_live.hidden_ref(h['track'], t)] if sme_live.HIDDEN_ASSIGN else []))
    return frames


def score(plan, frames, me, work):
    o, an = sme_live.base_run(plan, frames, me, max(frames), work, [])
    if o is None:
        return None
    an = sme_live.reclassify(plan, frames, me, an, o, work)
    return {'counts': an['counts'], 'first': an['first'], 'frames': an['frames']}


def job(args):
    rec, fp, plan, work = args
    frames, me = frames_of(rec, fp), rec['my_side']
    os.makedirs(work, exist_ok=True)
    full = score(plan, frames, me, work)
    out = []
    for k, c in enumerate(plan['cmds']):
        if c['_src'].get('source') != 'recon_add':
            continue
        p = recon.apply_edit(plan, {'op': 'drop', 'i': k})
        if p is None:
            out.append({'cmd': k, 'error': 'unit_ref'}); continue
        s = score(p, frames, me, work)
        ex = lambda r: r['counts'].get('exact', 0)
        fd = lambda r: r['first'] if r['first'] is not None else 10 ** 9
        v = 'error' if s is None or full is None else ('needed' if (ex(s), fd(s)) < (ex(full), fd(full)) else
                                                        'unneeded' if (ex(s), fd(s)) == (ex(full), fd(full)) else 'harmful')
        out.append({'cmd': k, 'side': c['side'], 'kind': c['kind'], 'card': c.get('card', c.get('unit')), 'run': c['run'],
                    'x': c.get('x'), 'y': c.get('y'), 'without': s, 'verdict': v})
    return {'match': rec['match'], 'with': full, 'adds': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--frames', required=True); ap.add_argument('--runs', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    recs = {json.loads(l)['match']: json.loads(l) for l in open(a.inputs)}
    jobs = []
    for run in a.runs.split(','):
        for line in open(os.path.join(run, 'recon_results.jsonl')):
            m = json.loads(line)['match']
            pf = os.path.join(run, m, 'recon_plan.json')
            if m not in recs or not os.path.exists(pf):
                continue
            plan = json.load(open(pf))
            if any(c['_src'].get('source') == 'recon_add' for c in plan['cmds']):
                jobs.append((recs[m], os.path.join(a.frames, m + '.jsonl'), plan, os.path.join(a.out, 'abl_work', m)))
    print('jobs', len(jobs), flush=True)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'ablate.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(job, jobs):
            w.write(json.dumps(res) + '\n'); w.flush()
            print(res['match'][-6:], res['with'], [(x.get('card'), x.get('run'), x.get('verdict')) for x in res['adds']], flush=True)


if __name__ == '__main__':
    main()
