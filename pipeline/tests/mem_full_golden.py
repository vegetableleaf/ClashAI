"""MEM-FULL: golden sha256s of match_memory's DEFAULT outputs (tables, features v1 / v2, features_at, rows_features, empty
rows), written ONCE from the pre-MEM-FULL code (commit c51efd9) and pinned by test_memory_full.py: absent opt-in keys must
stay byte-identical.

    python -I pipeline/tests/mem_full_golden.py write    # only to re-pin after a deliberate default change"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]
from pipeline import match_memory as M  # noqa: E402
from test_match_memory import DECK, GID, rich_match  # noqa: E402

GOLDEN = HERE / 'mem_full_golden.json'


def _h(d):
    h = hashlib.sha256()
    for k in sorted(d):
        a = np.ascontiguousarray(d[k])
        h.update(k.encode() + str(a.dtype).encode() + str(a.shape).encode() + a.tobytes())
    return h.hexdigest()


def digests():
    out = {}
    deck = [GID.get(M.card_key(c), 0) for c in DECK]
    tabs = []
    for seed in range(3):
        side, sm, plays = rich_match(500 + seed)
        m = M.build(side, sm, plays)
        tab = m.table(GID)
        tabs.append(tab)
        ticks = [s['tick'] for s in sm][::7] + [10 ** 6]
        out[f'table{seed}'] = _h(tab)
        for v in ('v1', 'v2'):
            out[f'feat{seed}_{v}'] = _h({f'{t}_{k}': x for t in ticks for k, x in m.features(t, GID, deck, v).items()})
            out[f'fat{seed}_{v}'] = _h(M.features_at(tab, ticks, deck, v, GID))
    packed = M.pack(tabs)
    rng = np.random.default_rng(1)
    rt, tt = rng.integers(-1, 3, 40), rng.integers(0, 4200, 40)
    out['rows_v1'] = _h(M.rows_features(packed, rt, tt, np.tile(deck, (40, 1)), np.arange(40)))
    out['rows_v2'] = _h(M.rows_features(packed, rt, tt, np.tile(deck, (40, 1)), np.arange(40), 'v2', GID))
    out['empty_v1'], out['empty_v2'] = _h(M.empty_rows(3)), _h(M.empty_rows(3, 'v2'))
    return out


if __name__ == '__main__':
    if sys.argv[1:] == ['write']:
        GOLDEN.write_text(json.dumps(digests(), indent=1, sort_keys=True))
    print(json.dumps(digests(), indent=1, sort_keys=True))
