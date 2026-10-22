"""W19 HIT CENSUS: does a hit that lands on the same body in the same frame gap deal the same damage live and in the SIM?
Re-runs every stamped strict fight at K = 0 (fights.py's replay, unchanged) and, for each paired non-tower body (and the crown
towers), compares its hp drop over each frame gap live vs SIM while both runs are still in step (the body's hp agreed within
5 at the gap's start). Records equal / different drop sizes with the attackers that targeted the victim at the gap's start
(live phase-3 target rows; SIM target_uid). A drop of a different size on the same gap = a damage-amount difference (card
level, damage law, splash share, shield / reduction); a drop on one side only = timing.
  python hits.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]
Output OUT_DIR/hits.jsonl: per match {match, levels, rows: [[victim, vside, attackers_live, attackers_sim, dl, ds], ...]}."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.w19 import cls as C  # noqa: E402

TOL = 5
OUT = []


def run_fight(eng, m, events, fight, catalog, *a, **k):
    C.CAP.clear()
    r = C._run_fight(eng, m, events, fight, catalog, *a, **k)
    an = events[fight['anchor']]
    if (fight['t0'], an['name'], an['tick']) in C.SELECT and 'rows' in C.CAP and r.get('card') and F.is_clean(r, 'strict'):
        rows, setup = C.CAP['rows'], C.CAP['setup']
        pairs = F.initial_pairs(rows, setup, catalog)
        inv = {s: l for l, s in pairs.items() if s}
        LT = C.live_targets(m, rows)
        nm = lambda bd: (catalog.get(bd['card_id']) or {}).get('display_name', 'tower' if bd['tower'] else str(bd['card_id']))
        for (ta, la, sa), (tb, lb, sb) in zip(rows, rows[1:]):
            LA = {b['id']: b for b in la}; LB = {b['id']: b for b in lb}
            SA = {b['id']: b for b in sa}; SB = {b['id']: b for b in sb}
            for lid, a0 in LA.items():
                sid = lid if a0['tower'] else pairs.get(lid)
                if sid is None or sid not in SA or abs(SA[sid]['hp'] - a0['hp']) > TOL:
                    continue
                dl = a0['hp'] - max(0, LB[lid]['hp']) if lid in LB else None     # None: gone (died / left the frames)
                ds = SA[sid]['hp'] - max(0, SB[sid]['hp']) if sid in SB else None
                if (dl or 0) <= 0 and (ds or 0) <= 0:
                    continue
                atl = sorted(nm(LA[x]) for x, tg in LT.get(ta, {}).items() if tg == lid and x in LA)
                ats = sorted(s['name'] for s in sa if s.get('tgt') == sid and not s['tower']) + \
                    sorted(s['id'] for s in sa if s.get('tgt') == sid and s['tower'])
                if dl == ds and dl is not None and dl <= 20 and not atl and not ats:
                    continue                    # a building's lifetime decay, the same on both sides
                OUT.append((nm(a0) if not a0['tower'] else lid, a0['side'] == m['side'], tuple(atl), tuple(ats), dl, ds))
    return r


def one(job):
    path, sel, out_dir = job
    C.SELECT.clear(); C.SELECT.update(tuple(x) for x in sel); OUT.clear()
    tmp = tempfile.mkdtemp(dir=out_dir); os.makedirs(tmp + '/matches')
    try:
        F.run_match(path, 240, tmp, 0)
        d = json.load(open(f'{tmp}/matches/{Path(path).stem}.json'))
        from collections import Counter
        return Path(path).stem, d['summary'].get('levels'), [list(k) + [v] for k, v in Counter(OUT).items()], None
    except Exception as e:  # noqa: BLE001
        return Path(path).stem, None, [], type(e).__name__ + ':' + str(e)[:200]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def init():
    F.Engine.bodies, F.measure, F.run_fight, F.cut = C.bodies, C.measure, run_fight, C.cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run']); ap.add_argument('--base', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--live', required=True); ap.add_argument('--workers', type=int, default=4)
    ar = ap.parse_args()
    o = Path(ar.out); o.mkdir(parents=True, exist_ok=True)
    os.environ['CLS_ALL'] = '1'; C.ALL_FIGHTS = True
    fl = C.failing(ar.base)
    done = {json.loads(x)['match'] for x in open(o / 'hits.jsonl')} if (o / 'hits.jsonl').exists() else set()
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items()) if k not in done]
    print('fights', sum(len(v) for v in fl.values()), 'matches', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'hits.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, lv, rows, err = fut.result()
            fo.write(json.dumps(dict(match=stem, levels=lv, err=err, rows=rows)) + '\n'); fo.flush()
    print('HITS_DONE', flush=True)


if __name__ == '__main__':
    main()
