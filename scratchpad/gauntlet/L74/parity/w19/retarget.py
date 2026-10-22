"""W19 RETARGET CENSUS: when a live unit switches its target (phase-3 target rows) from one living enemy to ANOTHER living one,
does its SIM twin make the same switch (to the paired body, within +-6 ticks)? Re-runs every stamped strict fight at K = 0.
Per switch: attacker card, the live attacker's behaviour state before the switch (1 walk / 2 attack), whether the new target
was born in the last 30 ticks (a fresh deploy) and still deploying (live state 4), and the SIM's answer (same switch / stayed
on the old target / other). Aggregated per match.
  python retarget.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]"""
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
        LT = C.live_targets(m, rows)
        first = {}
        for t, live, _ in rows:
            for bd in live:
                first.setdefault(bd['id'], t)
        ticks = [t for t, _, _ in rows]
        Lrow = {t: {b['id']: b for b in live} for t, live, _ in rows}
        Srow = {t: {s['id']: s for s in sim} for t, _, sim in rows}
        prev = {}
        for t in ticks:
            for x, tg in LT.get(t, {}).items():
                old = prev.get(x)
                prev[x] = tg
                if old is None or tg is None or old == tg or str(tg).startswith('T') or str(old).startswith('T'):
                    continue
                if old not in Lrow[t] or tg not in Lrow[t]:
                    continue                                  # the old target died: a forced retarget, not a choice
                ax = Lrow[t].get(x)
                if ax is None or ax['tower']:
                    continue
                sx, sold, snew = pairs.get(x), pairs.get(old), pairs.get(tg)
                if sx is None or snew is None:
                    continue
                win = [u for u in ticks if t - 6 <= u <= t + 6]
                st = [Srow[u].get(sx, {}).get('tgt') for u in win if sx in Srow[u]]
                ans = 'same' if snew in st else ('stayed' if sold is not None and sold in st else 'other')
                card = (catalog.get(ax['card_id']) or {}).get('display_name', '?')
                fresh = 'fresh' if t - first.get(tg, -999) <= 30 else 'old'
                state_prev = next((Lrow[u][x].get('state') for u in reversed([u for u in ticks if u < t]) if x in Lrow[u]), None)
                deploying = Lrow[t][tg].get('state') == 4
                OUT[(card, ax['side'] == m['side'], state_prev, fresh, deploying, ans)] += 1
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
    done = {json.loads(x)['match'] for x in open(o / 'retarget.jsonl')} if (o / 'retarget.jsonl').exists() else set()
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items()) if k not in done]
    print('fights', sum(len(v) for v in fl.values()), 'matches', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'retarget.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, rows, err = fut.result()
            fo.write(json.dumps(dict(match=stem, err=err, rows=rows)) + '\n'); fo.flush()
    print('RETARGET_DONE', flush=True)


if __name__ == '__main__':
    main()
