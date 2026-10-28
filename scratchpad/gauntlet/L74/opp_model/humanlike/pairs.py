"""P2-SCORE split items (b) + (d): closed-loop matches with EXPLICIT decks + levels per game, on search_s0's own Runner and
match code (no production edit). A worker patches search_s0.setup_job so that "seed" i plays row i of a JSONL job table.

    # pod (env as run_closed.sh: ROYALE_ENGINE=crforge, CRFORGE_*, PYTHONPATH=CB:...); from the code copy CB:
    python -I .../humanlike/pairs.py run --jobs JOBS.jsonl --out DIR --opp-ckpt OPP [--opp-T .1] [--opp-extra "..."]
           [--ckpt CLXIII] [--extra "--record-board ..."] [--g2] [--mvm] [--workers 40] [--chunk 12] [--python PY]
    job row: {"key": str, "seed": int, "learner_side": 0|1, "learner_deck": [engine names] | null (= icebow),
              "opp_deck": [engine names] (or "learner_slugs" / "opp_slugs": HF card keys, converted in the worker), "levels": {"learner": {"cards": [8], "tower": t}, "opp": {...}} | null,
              "opp_tower": "Cannoneer" | ... | null}
  default: the learner seat = --ckpt on gap.py's D3 live stack (the deployed decision options; --g2 adds the W18 tap
           handicap) vs the opponent model -> predict_live.py (D1 P_hat);
  --mvm:   model vs model (B-HF / C-HF): BOTH seats are the opponent model with the opponent seat's cfg (its own policy object
           per seat, no live stack, no G2), decks + levels from HF deck pairs (hf_pairs in predict_live.py's sibling).
Output: DIR/pairs/D3/chunk_NNNNN/matches.jsonl (search_s0 rows; tag = "pairs:ROW:KEY:SEED") + DIR/run.json."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).absolute().parent           # not resolve(): a code copy may symlink scratchpad/ (ROOT = the copy)
ROOT = HERE.parents[4]
GAP = ROOT / 'scratchpad/gauntlet/L74/gap'
CLXIII = 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
CENSUS = 'scratchpad/gauntlet/L74/mix/decks_live_eval.json'      # loaded by search_s0 (unused: setup_job is replaced)
G2 = ['--tap-loss', '1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890', '--tap-slow', '0.151:17']   # o4_gate v2 G2 (W18), = run_closed.sh


_MAP = None


def engine_deck(slugs):
    """HF / RoyaleAPI card keys in deck order ('mortar-ev1', 'goblins-hero', 'the-log') -> engine names ('Mortar@evolution', ...)
    through newsim/census.aliases over mix/live_pool.engine_names() (live_pool.to_engine's mapping, order kept); None if a card
    has no engine spelling."""
    global _MAP
    if _MAP is None:
        sys.path[:0] = [str(ROOT / 'scratchpad/gauntlet/L74/mix'), str(ROOT)]
        import live_pool as LP
        from scratchpad.gauntlet.L74.newsim import census
        _MAP = (census.aliases(LP.engine_names()), census.key, LP.split_slug)
    mapping, key, split = _MAP
    out = []
    for c in slugs:
        b, f = split(c)
        nm = mapping.get(key(b))
        if nm is None:
            return None
        out.append(nm + ('@hero' if f == 'hero' else '@evolution' if f else ''))
    return out


def worker():
    """search_s0 worker (livecal.worker: no stall rule, one plain worker) with setup_job reading PAIRS_JOBS."""
    sys.path[:0] = [str(ROOT), str(GAP), str(ROOT / 'scratchpad/gauntlet/L74/livecal')]
    from pipeline import search_s0 as S
    from pipeline import e1_eval as E
    from pipeline.dataset_gen import card_key
    from pipeline.royale_env import UnsupportedDeck
    import livecal
    rows = [json.loads(x) for x in open(os.environ['PAIRS_JOBS'], encoding='utf-8')]
    mvm = os.environ.get('PAIRS_MVM') == '1'
    orig = S._init_worker

    def init(args):
        orig(args)
        from pipeline.rl_royale import _live_level_table
        R = S._W['runner']
        R.live_levels = _live_level_table('all16')     # a row without levels: all16 (= gap.py --levels all16, run_closed.sh)
        if mvm:                                   # both seats = the opponent model on the opponent seat's cfg
            _, ocfg = R.opps['gen']
            R.learner = E.load_policy(S.REPO / S._W['opp_meta']['opp_gen'], args['device'])[0]   # its own object
            R.lcfg = dict(ocfg)
    S._init_worker = init

    def setup_job(run, census, opp_id, seed):
        i = int(seed)
        r = dict(rows[i])
        for k in ('learner', 'opp'):                 # HF jobs (hf_ref.py jobs) carry card keys: converted here, on the pod
            if r.get(k + '_slugs'):
                r[k + '_deck'] = engine_deck(r[k + '_slugs'])
                if r[k + '_deck'] is None:
                    return None
        ldeck = list(r.get('learner_deck') or E.ICEBOW_ENGINE_DECK)
        LD[i] = ldeck
        opp, ocfg = run.opps[opp_id]
        for pol, deck in ((opp, r['opp_deck']), (run.learner, ldeck if mvm else ())):
            if any(card_key(n) not in pol.gid for n in deck):
                return None                       # a card the model never saw: skipped (counted by the caller)
        spec = {'tag': f"pairs:{i}:{r['key']}:{r['seed']}", 'opp': {'id': opp_id}, 'learner_deck': ldeck,
                'opp_deck': list(r['opp_deck']), 'learner_side': int(r['learner_side']), 'seed': int(r['seed'])}
        if r.get('levels'):
            spec['levels'] = r['levels']
        else:
            from pipeline.rl_royale import draw_live_levels
            spec['levels'] = draw_live_levels(run.live_levels, ldeck, spec['opp_deck'], f"{r['seed']}:{','.join(spec['opp_deck'])}")
        if r.get('opp_tower'):
            spec['opp_tower'] = r['opp_tower']
        try:
            return E.SelfPlayMatch(run.make_env(), spec, 0, {**run.lcfg, 'entry_index': 0}, {**ocfg, 'entry_index': 0},
                                   run.learner, opp), r['key']
        except (UnsupportedDeck, KeyError):
            return None
    S.setup_job = setup_job
    LD = {}
    run_one = S._run_job

    def run_job(job):                             # the row also names the learner seat's deck (card.sim_records mvm)
        rec = run_one(job)
        if not rec.get('skipped') and int(job[2]) in LD:
            rec['learner_deck'] = LD[int(job[2])]
        return rec
    S._run_job = run_job
    return livecal.worker()


def run(a):
    sys.path[:0] = [str(ROOT), str(GAP), str(ROOT / 'scratchpad/gauntlet/L74/livecal')]
    import gap
    jobs = Path(a.jobs).resolve()
    n = sum(1 for x in open(jobs, encoding='utf-8') if x.strip())
    out = Path(a.out)
    (out / 'pairs' / 'D3').mkdir(parents=True, exist_ok=True)
    extra = shlex.split(a.extra) + shlex.split(a.opp_extra) + (G2 if a.g2 and not a.mvm else [])
    chunks = [list(range(i, min(n, i + a.chunk))) for i in range(0, n, a.chunk)]
    env = dict(os.environ, PAIRS_JOBS=str(jobs), PAIRS_MVM='1' if a.mvm else '0', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1')
    (out / 'run.json').write_text(json.dumps(dict(jobs=str(jobs), n=n, ckpt=a.ckpt, opp_ckpt=a.opp_ckpt, opp_T=a.opp_t, extra=extra,
                                                  mvm=a.mvm, g2=bool(a.g2 and not a.mvm), chunk=a.chunk), indent=1))

    def one(k):
        dest = out / 'pairs' / 'D3' / f'chunk_{k:05d}'          # card.sim_records / xbow_count.rows glob ROOT/*/D3/*/
        if (dest / 'matches.jsonl').exists() and sum(1 for _ in open(dest / 'matches.jsonl')) >= len(chunks[k]):
            return k, 'kept'
        job = dict(seeds=chunks[k], checkpoint=a.ckpt, opponent=dict(path=a.opp_ckpt, temperature=float(a.opp_t)), fast=False)
        cmd = gap.command('D3', job, ROOT / CENSUS, dest, a.python, extra)
        cmd[1:3] = [str(HERE / 'pairs.py'), '--worker']
        with open(str(dest) + '.log', 'w') as log:
            r = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        return k, r.returncode
    with ThreadPoolExecutor(a.workers) as ex:
        for k, rc in ex.map(one, range(len(chunks))):
            print(f'chunk {k} {rc}', flush=True)
    print('PAIRS DONE', n, 'rows', len(chunks), 'chunks')


def rows_of(out):
    """All result rows of a pairs run, de-duplicated by tag."""
    seen, res = set(), []
    for f in sorted(Path(out).glob('pairs/D3/chunk_*/matches.jsonl')):
        for x in open(f, encoding='utf-8'):
            if x.strip():
                r = json.loads(x)
                if r.get('tag') not in seen and 'outcome' in r:
                    seen.add(r.get('tag'))
                    res.append(r)
    return res


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker()
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('run',))
    ap.add_argument('--jobs', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ckpt', default=CLXIII)
    ap.add_argument('--opp-ckpt', required=True)
    ap.add_argument('--opp-t', default='0.1')
    ap.add_argument('--opp-extra', default='')
    ap.add_argument('--extra', default='--habit-log --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample '
                                       '--crown-log --record-board')                     # = run_closed.sh EX minus --live-levels
    ap.add_argument('--g2', action='store_true')
    ap.add_argument('--mvm', action='store_true')
    ap.add_argument('--workers', type=int, default=40)
    ap.add_argument('--chunk', type=int, default=12)
    ap.add_argument('--python', default=sys.executable)
    run(ap.parse_args())


if __name__ == '__main__':
    sys.exit(main())
