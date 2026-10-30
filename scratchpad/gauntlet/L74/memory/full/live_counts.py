"""MEM-FULL step 1 (live): per recorded live match, the full-match event count of the live memory inputs (live_dump.read =
the S1a offline build that live_replay.py proved identical to the live path, 2013/2013 decisions). Read-only.

    python -I scratchpad/gauntlet/L74/memory/full/live_counts.py OUT.json N        # the newest N complete logs
-> OUT.json: list of {log, n, play, ability, tower_damage, tower_fall, 1x, 2x, ot, dropped*, dec, dec_over, t129}
   (count_events.py counts OUT.json summarises it)."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[4]), str(HERE.parent)]
import live_dump as D  # noqa: E402
from pipeline import match_memory as M  # noqa: E402
from pipeline.dataset_gen import card_key  # noqa: E402

E = 128


def one(p):
    m = D.read(p)
    gid = {k: i + 1 for i, k in enumerate(sorted({card_key(str(q['card'])) for q in m['plays']}))}
    tab = M.build(m['side'], m['samples'], m['plays']).table(gid)
    v, tk = tab['vals'], tab['tick'].astype(np.int64)
    typ, mine = np.argmax(v[:, :4], 1), v[:, 4] == 1
    ph = np.where(tk < M.DOUBLE_T, 0, np.where(tk < M.OT_T, 1, 2))
    n = len(tk)
    dr = np.arange(n) < n - E
    vis = np.sort(tab['vis'])
    dec = [s['tick'] for s in m['samples']]
    visible = np.searchsorted(vis, dec, 'right')
    return dict(log=p.name, n=n, **{k: int((typ == i).sum()) for i, k in enumerate(M.TYPES)},
                **{k: int((ph == i).sum()) for i, k in enumerate(('1x', '2x', 'ot'))},
                dropped=int(dr.sum()), **{f'dropped_{k}': int((dr & (ph == i)).sum()) for i, k in enumerate(('1x', '2x', 'ot'))},
                dropped_own=int((dr & mine).sum()), dropped_opp=int((dr & ~mine).sum()),
                dec=len(dec), dec_over=int((visible > E).sum()), t129=int(tk[E]) if n > E else None)


def main():
    out, N = Path(sys.argv[1]), int(sys.argv[2])
    paths = []
    for p in sorted(D.LOGS.glob('live_play_2026*.jsonl'), reverse=True):
        if p.stat().st_size > 2e6:
            with open(p, 'rb') as f:
                f.seek(max(0, p.stat().st_size - 200000))
                if b'{"event": "end"' not in f.read():
                    continue
            paths.append(p)
        if len(paths) == N:
            break
    res = []
    for i, p in enumerate(paths):
        try:
            res.append(one(p))
        except Exception as ex:                    # a partial / odd log is counted, not fatal
            print(f'{p.name}: {type(ex).__name__}: {ex}', file=sys.stderr)
        if (i + 1) % 10 == 0:
            print(f'{i + 1}/{len(paths)}', file=sys.stderr, flush=True)
            out.write_text(json.dumps(res))
    out.write_text(json.dumps(res))


if __name__ == '__main__':
    main()
