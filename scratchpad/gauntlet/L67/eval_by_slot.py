"""L67o: per-CARD breakdown of eval_s1 on one dataset's VAL play rows -- did the tesla <- cannon alias hurt tesla?

The v6 hogeq corpus added one-card-off pro decks where the pro's CANNON plays are labelled as our TESLA slot. The
alias passed a placement-usage test before mining (HANDOFF 5cs.99 Q), but the owner's condition was that
placements must not be confounded -- so the question here is whether v6lat places TESLA worse than v5lat (trained
with no aliased rows) on the exact-deck v3 VAL file. Same evaluate() as eval_s1, restricted to play rows whose
label is slot k.

usage: python scratchpad/gauntlet/L67/eval_by_slot.py hogeq --data <npz> --ckpts <a.pt> <b.pt> ... > out
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from pipeline.dataset import load as load_ds          # noqa: E402
from pipeline.model_v3 import S1Model                  # noqa: E402
from pipeline.obs_contract import load_deck            # noqa: E402
from pipeline.train_s1 import Rows, evaluate           # noqa: E402

KEYS = ("cell_half_top1", "card_top1", "place_1t", "place_dist", "n_play")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--ckpts", nargs="+", type=Path, required=True)
    a = ap.parse_args()
    deck = load_deck(a.deck)
    arrs, _ = load_ds(a.data)
    val_play = (arrs["split"] == 1) & (arrs["y_gate"] == 1)
    print(json.dumps({"val_play_rows": int(val_play.sum()),
                      "rows_by_slot": {deck.cards[k]: int((val_play & (arrs["y_slot"] == k)).sum())
                                       for k in range(len(deck.cards))}}), flush=True)
    dev = torch.device("cpu")
    for c in a.ckpts:
        st = torch.load(c, map_location=dev)
        args = st.get("args", {})
        model = S1Model(d=args.get("d", 128), layers=args.get("layers", 4)).to(dev)
        model.load_state_dict(st["model"])
        model.eval()
        out = {"ckpt": c.name}
        for k, card in enumerate(deck.cards):
            idx = np.where(val_play & (arrs["y_slot"] == k))[0]
            if len(idx) == 0:
                continue
            with torch.no_grad():
                ev = evaluate(model, Rows(arrs, idx, dev), grid=args.get("grid", "floor"))
            out[card] = {kk: (round(ev[kk], 4) if isinstance(ev.get(kk), float) else ev.get(kk)) for kk in KEYS}
        print(json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
