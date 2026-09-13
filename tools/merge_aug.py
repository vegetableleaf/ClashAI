"""L67d: augmented training set = clean v6 rows (splits intact) + the degraded twin's TRAIN rows appended as train.

Val rows stay clean and identical to the clean build, so checkpoint selection is the same rule v6lat used and the
only variable is the extra degraded copies of the train rows.

Moved from scratchpad/gauntlet/L67/merge_aug.py; behaviour unchanged (it has no repo paths of its own).

usage (from the repo root):
  icebow\\.venv\\Scripts\\python.exe tools\\merge_aug.py --clean <npz> --degraded <npz> --out <npz>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROW_KEYS = ("sc", "y_slot", "y_xy", "y_gate", "y_wait_slot", "y_wait_dt", "tick", "rep", "side", "split",
            "past", "y_crowns")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", type=Path, required=True)
    ap.add_argument("--degraded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    c = np.load(a.clean, allow_pickle=False)   # meta is a plain json string, so allow_pickle stays off
    d = np.load(a.degraded, allow_pickle=False)
    assert c["split"].shape == d["split"].shape, "row counts differ -- not a paired twin"
    assert np.array_equal(c["split"], d["split"]) and np.array_equal(c["y_xy"], d["y_xy"]), "targets/splits differ"
    tr = np.flatnonzero(d["split"] == 0)
    out = {}
    for k in ROW_KEYS:
        out[k] = np.concatenate([c[k], d[k][tr]], axis=0)
    # token blocks: keep clean tokens, then append the degraded train rows' blocks and rebuild offsets.
    # NpzFile.__getitem__ DECOMPRESSES THE WHOLE ARRAY on every access, so `d["tok"][a:b]` inside a loop
    # re-reads a 74 MB array once per row (the L67d MemoryError). Materialise both token arrays ONCE and
    # gather with a vectorised ragged range instead of building 250k slices.
    coff, doff = np.asarray(c["off"]), np.asarray(d["off"])
    c_tok, d_tok = np.asarray(c["tok"]), np.asarray(d["tok"])
    lens_new = (doff[tr + 1] - doff[tr]).astype(np.int64)
    total = int(lens_new.sum())
    starts = doff[tr].astype(np.int64)
    prior = np.concatenate([[0], np.cumsum(lens_new)[:-1]])
    idx = np.repeat(starts - prior, lens_new) + np.arange(total, dtype=np.int64)
    out["tok"] = np.concatenate([c_tok, d_tok[idx]], axis=0)
    lens = np.concatenate([np.diff(coff), lens_new])
    out["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    out["tags"] = c["tags"]
    meta = json.loads(str(c["meta"]))
    meta["augmented"] = {"degraded_train_rows": int(len(tr)), "source_clean": str(a.clean), "source_degraded": str(a.degraded)}
    np.savez_compressed(a.out, meta=json.dumps(meta), **out)
    print(json.dumps({"out": str(a.out), "clean_rows": int(len(c["split"])), "added_degraded_train_rows": int(len(tr)),
                      "total_rows": int(len(out["split"])), "val_rows": int((out["split"] == 1).sum()),
                      "tok_rows": int(len(out["tok"])), "off_ok": bool(out["off"][-1] == len(out["tok"]))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
