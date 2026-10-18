"""Step d: per-row sampling weights for imitation = the owner's "train on unfavourable matchups ~3x" (memory
train-on-unfavorable-matchups; pipeline.archetypes.unfavorable = the six named archetypes).

    python scratchpad/gauntlet/L74/stepd/row_weights.py --data icebow/data/pipeline/gen_dataset_v32_fv5.npz \
        --out /workspace/stepd/v32_w3.npy [--factor 3]

A row gets weight --factor when ITS side plays an X-Bow deck and the OTHER side of that replay plays an unfavourable
archetype; every other row 1. train_gen --row-weights draws each epoch's rows with replacement in proportion.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def weights(rep, side, deck_card, vocab, factor: float) -> tuple[np.ndarray, dict]:
    from pipeline.archetypes import classify, unfavorable
    w = np.ones(len(rep), np.float32)
    decks: dict = {}
    first = {}
    for i in np.unique(np.stack([rep, side], 1), axis=0, return_index=True)[1]:
        first[int(rep[i]), int(side[i])] = i
    for (r, s), i in first.items():
        decks[r, s] = [vocab[int(c)] for c in deck_card[i] if int(c) > 0]
    hits, arch = 0, {}
    for (r, s), names in decks.items():
        other = decks.get((r, 1 - s))
        if other is None or "x-bow" not in names:
            continue
        a = classify(other)
        arch[a] = arch.get(a, 0) + 1
        if unfavorable(a):
            m = (rep == r) & (side == s)
            w[m] = factor
            hits += 1
    return w, dict(xbow_sides=sum(arch.values()), boosted_sides=hits, opp_archetypes=arch,
                   boosted_rows=int((w > 1).sum()), rows=len(w))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--factor", type=float, default=3.0)
    a = ap.parse_args(argv)
    z = np.load(a.data, allow_pickle=False)
    vocab = json.loads(str(z["meta"]))["card_vocab"]
    w, info = weights(z["rep"], z["side"], z["deck_card"], vocab, a.factor)
    np.save(a.out, w)
    print("ROW_WEIGHTS_DONE", json.dumps(dict(info, factor=a.factor, out=str(a.out))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
