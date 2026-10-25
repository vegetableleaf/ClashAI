"""Gate calibration on PRO val rows: base (CLXIII) vs the S3 memory model (real memory / empty memory) vs its delta
checkpoint (make_delta.py), next to the pros' own play rate -- the same rows the S3 trained on (val split). Read-only.

    python pro_shift.py --base B.pt --mem M.pt [--delta D.pt] --head 400000 [--n 6000] [--device cuda]"""
import argparse
from pathlib import Path

import numpy as np
import torch

from pipeline.dataset_gen import load_memory_tables
from pipeline.model_gen import load_model
from pipeline.train_gen import GenRows
from pipeline.train_memory import npz_head

REPO = Path(__file__).resolve().parents[5] if len(Path(__file__).resolve().parents) > 5 else Path('.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--mem', required=True)
    ap.add_argument('--delta')
    ap.add_argument('--data', default='icebow/data/pipeline/gen_dataset_v32_fv5.npz')
    ap.add_argument('--tables', default='icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz')
    ap.add_argument('--head', type=int, default=400000)
    ap.add_argument('--n', type=int, default=6000)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--icebow', action='store_true', help='only rows of icebow-deck sides (the 8 icebow cards)')
    a = ap.parse_args()
    dev = torch.device(a.device)
    arrs, meta = npz_head(Path(a.data), a.head)
    packed, row_tab, _ = load_memory_tables(Path(a.tables))
    n = len(arrs['y_gate'])
    val = np.flatnonzero(arrs['split'][:n] == 1)
    if a.icebow:
        from pipeline.dataset_gen import checkpoint_gid
        g = checkpoint_gid(meta['card_vocab'])
        ice = np.sort([g[k] for k in ('x-bow', 'tesla', 'ice-wizard', 'tornado', 'rocket', 'knight', 'the-log', 'skeletons')])
        val = val[np.all(np.sort(arrs['deck_card'][val].astype(np.int64), 1) == ice, 1)]
    idx = np.sort(np.random.default_rng(0).choice(val, size=min(a.n, len(val)), replace=False))
    rows = GenRows(arrs, idx, dev)
    rows.grid = 'lattice'
    tables = (packed, row_tab[:n], arrs['tick'])
    y = arrs['y_gate'][idx].astype(np.float64)
    t = arrs['tick'][idx].astype(np.int64)
    arms = [('base', a.base, None), ('mem', a.mem, tables), ('mem_empty', a.mem, 'empty')]
    if a.delta:
        arms += [('delta', a.delta, tables), ('delta_empty', a.delta, 'empty')]
    P = {}
    for name, ck, mem in arms:
        net = load_model(ck, dev)[0].eval()
        rows.memory = mem if getattr(net, 'mem', None) is not None else None
        ps = []
        with torch.no_grad():
            for s in range(0, len(idx), 512):
                ps.append(torch.sigmoid(net(rows.batch(idx[s:s + 512]))['gate'].double()).cpu().numpy())
        P[name] = np.concatenate(ps)
    print(f'{len(idx)} pro val rows (head {a.head}); pro play-row share {y.mean():.3f}')
    bins = ((0, 200), (200, 1200), (1200, 2400), (2400, 3600), (3600, 10 ** 6))
    print(f'{"arm":12s} {"mean p":>7s} {"p|play":>7s} {"p|wait":>7s} {">=.35":>6s}  ' + '  '.join(f'[{lo},{hi})' for lo, hi in bins))
    for k, p in P.items():
        print(f'{k:12s} {p.mean():7.3f} {p[y == 1].mean():7.3f} {p[y == 0].mean():7.3f} {(p >= .35).mean():6.3f}  ' + '  '.join(
            f'{p[(t >= lo) & (t < hi)].mean():.3f}/{y[(t >= lo) & (t < hi)].mean():.3f}' for lo, hi in bins))
    print('bins: model mean p / pro play share')
    for k in P:
        if k != 'base':
            print(f'{k} - base: mean dp {np.mean(P[k] - P["base"]):+.3f}, |dp| {np.mean(np.abs(P[k] - P["base"])):.3f}')


if __name__ == '__main__':
    main()
