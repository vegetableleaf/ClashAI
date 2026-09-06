"""Evaluate S1 checkpoints on the VAL rows of one dataset -- one instrument for models trained on different corpora.

    python -m pipeline.eval_s1 hogeq --data hogeq/data/pipeline/s1_dataset.npz hogeq/data/pipeline/s1_hogeq_s0.pt ...

Prints one JSON line per checkpoint (same keys as train_s1.evaluate) and writes nothing else.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from .dataset import load as load_ds
from .model_v3 import S1Model
from .obs_contract import load_deck
from .train_s1 import Rows, evaluate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("ckpts", nargs="+", type=Path)
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--split", type=int, default=1, help="0 = train rows, 1 = val rows")
    a = ap.parse_args(argv)
    deck = load_deck(a.deck)
    arrs, meta = load_ds(a.data or (deck.data_dir / "pipeline" / "s1_dataset.npz"))
    dev = torch.device("cpu")
    idx = np.where(arrs["split"] == a.split)[0]
    rows = Rows(arrs, idx, dev)
    for c in a.ckpts:
        st = torch.load(c, map_location=dev)
        args = st.get("args", {})
        model = S1Model(d=args.get("d", 128), layers=args.get("layers", 4)).to(dev)
        model.load_state_dict(st["model"])
        with torch.no_grad():
            ev = evaluate(model, rows)
        ev.update({"ckpt": str(c), "epoch": st.get("epoch"), "data": str(a.data), "rows": int(len(idx)),
                   "trained_on": str(args.get("data"))})
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev.items()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
