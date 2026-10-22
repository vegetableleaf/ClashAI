"""W19 WALK-SPEED CENSUS: do paired bodies walk at the same speed live and in the SIM? Re-runs every stamped strict fight at
K = 0 and, for each paired non-tower body and frame gap where BOTH walk (live behaviour state 1, SIM attack phase Idle, both
moved, no deploy), records live and SIM speed (mt per tick, 5 mt bins). Aggregated per (card, side, era).
  python speeds.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]
Output OUT_DIR/speeds.jsonl: per match {match, rows: [[card, own, live_speed_bin, sim_speed_bin, count]]}."""
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
_bodies0 = C.bodies


def bodies(self, by):
    st, out = _bodies0(self, by)
    rows = [dict(zip(self.F, r)) for r in st['entities']]
    for e, o in zip(rows, out):
        o['ph'] = e.get('attack_phase')
    return st, out


def run_fight(eng, m, events, fight, catalog, *a, **k):
    C.CAP.clear()
    r = C._run_fight(eng, m, events, fight, catalog, *a, **k)
    an = events[fight['anchor']]
    if (fight['t0'], an['name'], an['tick']) in C.SELECT and 'rows' in C.CAP and r.get('card') and F.is_clean(r, 'strict'):
        rows, setup = C.CAP['rows'], C.CAP['setup']
        pairs = F.initial_pairs(rows, setup, catalog)
        for (ta, la, sa), (tb, lb, sb) in zip(rows, rows[1:]):
            dt = tb - ta
            if dt <= 0:
                continue
            LB = {b['id']: b for b in lb}; SA = {b['id']: b for b in sa}; SB = {b['id']: b for b in sb}
            for a0 in la:
                if a0['tower'] or a0.get('state') != 1:
                    continue
                sid = pairs.get(a0['id'])
                b0, s0, s1 = LB.get(a0['id']), SA.get(sid), SB.get(sid)
                if not (b0 and s0 and s1) or b0.get('state') != 1 or s0.get('ph') not in (0, 'Idle', None) or s0.get('deploying') or s1.get('deploying'):
                    continue
                vl = math.hypot(b0['x'] - a0['x'], b0['y'] - a0['y']) / dt
                vs = math.hypot(s1['x'] - s0['x'], s1['y'] - s0['y']) / dt
                if vl < 15 or vs < 15:
                    continue
                name = (catalog.get(a0['card_id']) or {}).get('display_name', str(a0['card_id']))
                OUT[(name, a0['side'] == m['side'], int(vl // 5 * 5), int(vs // 5 * 5))] += 1
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
    F.Engine.bodies, F.measure, F.run_fight, F.cut = bodies, C.measure, run_fight, C.cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run']); ap.add_argument('--base', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--live', required=True); ap.add_argument('--workers', type=int, default=4)
    ar = ap.parse_args()
    o = Path(ar.out); o.mkdir(parents=True, exist_ok=True)
    C.ALL_FIGHTS = True
    fl = C.failing(ar.base)
    done = {json.loads(x)['match'] for x in open(o / 'speeds.jsonl')} if (o / 'speeds.jsonl').exists() else set()
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items()) if k not in done]
    print('fights', sum(len(v) for v in fl.values()), 'matches', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'speeds.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, rows, err = fut.result()
            fo.write(json.dumps(dict(match=stem, err=err, rows=rows)) + '\n'); fo.flush()
    print('SPEEDS_DONE', flush=True)


if __name__ == '__main__':
    main()
