"""X-BOW LOCK CENSUS (W18 question): in every stamped strict fight anchored on an own X-Bow play, the X-Bow's first target
after its deploy live (phase-3 rows) vs SIM (target_uid), and whether it ends the window on a crown tower; split by whether an
enemy unit / building stood 8-11.5 tiles from the X-Bow (tower-front blocker) when its deploy ended.
  python xbow_lock.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.w19 import cls as C  # noqa: E402

OUT = Counter()


def kind(x, rowsL, catalog):
    if x is None:
        return 'none'
    if str(x).startswith('T'):
        return 'tower'
    b = rowsL.get(x)
    c = (catalog.get(b['card_id']) or {}) if b else {}
    return 'building' if c.get('type') == 'building' else 'unit'


def run_fight(eng, m, events, fight, catalog, *a, **k):
    C.CAP.clear()
    r = C._run_fight(eng, m, events, fight, catalog, *a, **k)
    an = events[fight['anchor']]
    if (an['name'] == 'Xbow' and an['side'] == m['side'] and (fight['t0'], an['name'], an['tick']) in C.SELECT and 'rows' in C.CAP
            and r.get('card') and F.is_clean(r, 'strict')):
        rows, setup = C.CAP['rows'], C.CAP['setup']
        pairs = F.initial_pairs(rows, setup, catalog)
        inv = {s: l for l, s in pairs.items() if s}
        LT = C.live_targets(m, rows)
        xb = next((bd['id'] for t, live, _ in rows for bd in live if not bd['tower'] and bd['side'] == m['side']
                   and (catalog.get(bd['card_id']) or {}).get('display_name') == 'Xbow' and t >= an['tick'] - 2
                   and bd['id'] not in {s['id'] for s in setup}), None)
        if xb is None or pairs.get(xb) is None:
            return r
        sx = pairs[xb]
        first_l = first_s = None; tl = ts = None; blocker = False; t_act = None
        for t, live, sim in rows:
            L = {b['id']: b for b in live}; S = {s['id']: s for s in sim}
            xl = L.get(xb)
            if xl is None:
                continue
            if t_act is None and xl.get('state') not in (4, None):
                t_act = t
                blocker = any(not b['tower'] and b['side'] != m['side'] and 8000 <= math.hypot(b['x'] - xl['x'], b['y'] - xl['y']) <= 11500
                              for b in live)
            lt = LT.get(t, {}).get(xb)
            st = S.get(sx, {}).get('tgt')
            st = inv.get(st, st)
            if lt is not None and first_l is None:
                first_l = kind(lt, L, catalog)
            if st is not None and first_s is None:
                first_s = kind(st, L, catalog)
            tl = kind(lt, L, catalog) if lt is not None else tl
            ts = kind(st, L, catalog) if st is not None else ts
        OUT[('blocker 8-11.5t' if blocker else 'no blocker', first_l, first_s, tl == 'tower', ts == 'tower')] += 1
    return r


def one(job):
    path, sel, out_dir = job
    C.SELECT.clear(); C.SELECT.update(tuple(x) for x in sel); OUT.clear()
    tmp = tempfile.mkdtemp(dir=out_dir); os.makedirs(tmp + '/matches')
    try:
        F.run_match(path, 240, tmp, 0)
        return Path(path).stem, [list(k) + [v] for k, v in OUT.items()], None
    except Exception as e:  # noqa: BLE001
        return Path(path).stem, [], type(e).__name__ + ':' + str(e)[:200]
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
    C.ALL_FIGHTS = True
    fl = {k: [x for x in v if x[1] == 'Xbow'] for k, v in C.failing(ar.base).items()}
    fl = {k: v for k, v in fl.items() if v}
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items())]
    print('fights', sum(len(v) for v in fl.values()), 'matches', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'xbow.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, rows, err = fut.result()
            fo.write(json.dumps(dict(match=stem, err=err, rows=rows)) + '\n'); fo.flush()
    print('XBOW_DONE', flush=True)


if __name__ == '__main__':
    main()
