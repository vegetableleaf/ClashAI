"""RECON-5 part A in isolation (pod): the BASE plan of every record whose opponent plays fit no deal, run with (1) the identity deal
v3 / the gate hand crforge and (2) the best-prefix deal; nothing else changes (no search, no edit). One engine run each.
  python3 recon/r5_partA.py --inputs I.jsonl --frames FRAMEDIR --out OUTDIR [--workers 3]  (-> OUTDIR/partA.jsonl)   (env as runR.sh; use runR.sh's env)
Row: match, first div and counts under both deals, executed opponent plays under both (count of plays whose card is in hand)."""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import recon_search  # noqa: E402
import sme_live  # noqa: E402
from ablate import frames_of  # noqa: E402


def run(plan, frames, me, work):
    o, an = recon_search.full_run(plan, frames, me, max(frames), work, [])
    if o is None:
        return None
    an = sme_live.reclassify(plan, frames, me, an, o, work)
    return {'counts': an['counts'], 'first': an['first']}


def job(a):
    rec, fp, work = a
    frames, me = frames_of(rec, fp), rec['my_side']
    os.makedirs(work, exist_ok=True)
    plan = recon.base_plan(rec, frames)
    opp = 1 - me
    if plan['_cycle_base'][opp]:
        return None
    seq = [plan['decks'][opp].index(plan['cmds'][k]['card']) for _, k in recon.seq_of(plan, opp)]
    ident = run(plan, frames, me, work)
    p2 = dict(plan, deals=list(plan['deals']))
    p2['deals'][opp], n = recon.best_prefix_deal(seq)
    best = run(p2, frames, me, work)
    return {'match': rec['match'], 'n_plays': len(seq), 'ran_best': n, 'identity': ident, 'best_prefix': best}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--frames', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(a.inputs)]
    os.makedirs(a.out, exist_ok=True)       # runR.sh passes a directory: rows go to OUT/partA.jsonl
    jobs = [(r, os.path.join(a.frames, r['match'] + '.jsonl'), os.path.join(a.out, 'work', r['match'])) for r in recs]
    with open(os.path.join(a.out, 'partA.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(job, jobs):
            if res:
                w.write(json.dumps(res) + '\n'); w.flush()
                print(res['match'][-13:], 'identity', res['identity'], 'best', res['best_prefix'], flush=True)


if __name__ == '__main__':
    main()
