"""Index dataset_gen pro FAST-FOLLOW rows; no synthesized actions or private inputs.

The small NPZ stores source row indexes and exact card/cell labels. The immutable
source NPZ supplies the observations, avoiding a second multi-GB corpus copy.
Use unshifted dataset_gen rows: a latency-shifted row's past age is not the age
at the pro's actual play. Ordinary anchors exclude recent-play WAIT rows too.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

TICK_SECONDS = .05


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def masks(arrs, window=24):
    if window <= 0:
        raise ValueError('positive pending window required')
    past = arrs['past']
    if past.ndim != 3 or past.shape[-1] != 5:
        raise ValueError('dataset_gen past must be [card, form, x, y, dt_s]')
    dt = past[..., 4]
    valid = (past[..., 0] > 0) & np.isfinite(dt) & (dt >= 0)
    # float32 represents 1.2 just above its mathematical value.
    recent = (valid & (dt <= np.float32(window * TICK_SECONDS))).any(axis=1)
    play = arrs['y_gate'] > .5
    pending = recent & play
    pos = arrs['y_hand_pos']
    hit = arrs['hand_card'][np.arange(len(pos)), np.clip(pos, 0, 3)] == arrs['y_card']
    if np.any(pending & ((pos < 0) | (pos > 3) | (arrs['y_card'] <= 0) | ~hit)):
        raise ValueError('pending pro label is missing from its hand')
    return pending, ~recent


def deck_mask(arrs, vocab, cards):
    if not cards:
        return np.ones(len(arrs['y_gate']), dtype=bool)
    names = [c.replace('_', '-') for c in cards]
    if len(names) != 8 or len(set(names)) != 8:
        raise ValueError('deck must contain eight distinct base card keys')
    ids = np.sort([vocab.index(c) for c in names])
    return (np.sort(arrs['deck_card'], axis=1) == ids).all(axis=1)


def mix(cards, vocab):
    ids, counts = np.unique(cards, return_counts=True)
    return {vocab[int(c)]: int(n) / len(cards) for c, n in zip(ids, counts)}


def build(data, out, window=24, cards=None):
    from .model_v3 import cell_label
    import torch
    data, out = Path(data), Path(out)
    if out.exists() or out.with_suffix('.json').exists():
        raise FileExistsError(out)
    with np.load(data, allow_pickle=False) as z:
        meta = json.loads(str(z['meta']))
        if meta.get('kind') != 'generalist' or meta.get('shift_ticks', 0) != 0:
            raise ValueError('requires unshifted dataset_gen pro rows')
        a = {k: z[k] for k in ('past', 'y_gate', 'y_hand_pos', 'y_card', 'hand_card',
                               'deck_card', 'y_xy', 'split')}
        pending, ordinary = masks(a, window)
        selected = deck_mask(a, meta['card_vocab'], cards)
        ids = np.flatnonzero(pending & selected)
        if not len(ids):
            raise ValueError('no pending pro rows for the requested deck')
        labels = cell_label(torch.from_numpy(a['y_xy'][ids]), meta['grid']).numpy()
        report = dict(source=str(data.resolve()), source_sha256=digest(data), window_ticks=window,
                      definition='accepted pro play; valid own past age in [0, 24] ticks' if window == 24 else 'valid own past age within window',
                      card_vocab=meta['card_vocab'], grid=meta['grid'], deck=cards,
                      source_rows=len(pending), rows=len(ids),
                      train_rows=int((a['split'][ids] == 0).sum()),
                      val_rows=int((a['split'][ids] == 1).sum()),
                      second_card_mix=mix(a['y_card'][ids], meta['card_vocab']),
                      all_deck_pending_rows=int(pending.sum()),
                      all_deck_second_card_mix=mix(a['y_card'][pending], meta['card_vocab']),
                      ordinary_rows=int(ordinary.sum()))
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out, pending=ids, ordinary=np.flatnonzero(ordinary),
                            y_card=a['y_card'][ids], y_cell=labels, y_xy=a['y_xy'][ids],
                            split=a['split'][ids], meta=json.dumps(report))
    out.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--deck', nargs=8, help='base card slugs; omitted means all decks')
    p.add_argument('--window', type=int, default=24)
    a = p.parse_args(argv)
    print(json.dumps(build(a.data, a.out, a.window, a.deck), indent=2))


if __name__ == '__main__':
    main()
