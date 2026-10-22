"""W19 BIRTH CENSUS: is every body that appears inside a fight made at the same tick in the SIM as live? Re-runs every stamped
strict fight at K = 0 and lists each body first seen after the fight's first frame -- spawner waves (Witch, Tombstone,
huts), death spawns (Golem, Elixir Golem, Lava), curse pigs, spell spawns, and the plays themselves -- with its first live
tick and first SIM tick (paired bodies), or one side only. Aggregated per card: SIM - live birth tick, live-only, SIM-only.
  python births.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]
Output OUT_DIR/births.jsonl: per match {match, rows: [[card, own, sim-live (None = one side only), only ('L'/'S'/''), anchor_card, count]]}."""
from __future__ import annotations

import argparse
from collections import Counter
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

OUT = Counter()


def run_fight(eng, m, events, fight, catalog, *a, **k):
    C.CAP.clear()
    r = C._run_fight(eng, m, events, fight, catalog, *a, **k)
    an = events[fight['anchor']]
    if (fight['t0'], an['name'], an['tick']) in C.SELECT and 'rows' in C.CAP and r.get('card') and F.is_clean(r, 'strict'):
        rows, setup = C.CAP['rows'], C.CAP['setup']
        pairs = F.initial_pairs(rows, setup, catalog)
        inv = {s: l for l, s in pairs.items() if s}
        t0, t_end = rows[0][0], rows[-1][0]
        fl, fs, info = {}, {}, {}
        for t, live, sim in rows:
            for bd in live:
                if not bd['tower']:
                    fl.setdefault(bd['id'], t)
                    info.setdefault(bd['id'], ((catalog.get(bd['card_id']) or {}).get('display_name', str(bd['card_id'])), bd['side']))
            for s in sim:
                if not s['tower']:
                    k = inv.get(s['id'], s['id'])
                    fs.setdefault(k, t)
                    info.setdefault(k, (s['name'], s['side']))
        for k in set(fl) | set(fs):
            a_, b_ = fl.get(k), fs.get(k)
            if (a_ is not None and a_ <= t0) or (b_ is not None and b_ <= t0):
                continue                                  # on the start board
            if (a_ or b_) > t_end - 10:
                continue                                  # too close to the window end to judge
            name, side = info[k]
            dt = (b_ - a_) if a_ is not None and b_ is not None else None
            only = '' if dt is not None else ('L' if b_ is None else 'S')
            OUT[(name, side == m['side'], dt, only, an['name'])] += 1
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
    fl = C.failing(ar.base)
    done = {json.loads(x)['match'] for x in open(o / 'births.jsonl')} if (o / 'births.jsonl').exists() else set()
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items()) if k not in done]
    print('fights', sum(len(v) for v in fl.values()), 'matches', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'births.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, rows, err = fut.result()
            fo.write(json.dumps(dict(match=stem, err=err, rows=rows)) + '\n'); fo.flush()
    print('BIRTHS_DONE', flush=True)


if __name__ == '__main__':
    main()
