"""L67d: augmented training set = clean v6 rows (splits intact) + the degraded twin's TRAIN rows appended as train.

Val rows stay clean and identical to the clean build, so checkpoint selection is the same rule v6lat used and the
only variable is the extra degraded copies of the train rows.

usage: python scratchpad/gauntlet/L67/merge_aug.py --clean <npz> --degraded <npz> --out <npz>
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
    c = np.load(a.clean, allow_pickle=False)
    d = np.load(a.degraded, allow_pickle=False)
    assert c["split"].shape == d["split"].shape, "row counts differ -- not a paired twin"
    assert np.array_equal(c["split"], d["split"]) and np.array_equal(c["y_xy"], d["y_xy"]), "targets/splits differ"
    tr = np.flatnonzero(d["split"] == 0)
    out = {}
    for k in ROW_KEYS:
        out[k] = np.concatenate([c[k], d[k][tr]], axis=0)
    # token blocks: keep clean tokens, then append the degraded train rows' blocks and rebuild offsets
    coff, doff = c["off"], d["off"]
    blocks = [c["tok"]] + [d["tok"][doff[i]:doff[i + 1]] for i in tr]
    out["tok"] = np.concatenate(blocks, axis=0)
    lens = np.concatenate([np.diff(coff), (doff[tr + 1] - doff[tr])])
    out["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    out["tags"] = c["tags"]
    meta = json.loads(str(np.load(a.clean, allow_pickle=True)["meta"]))
    meta["augmented"] = {"degraded_train_rows": int(len(tr)), "source_clean": str(a.clean), "source_degraded": str(a.degraded)}
    np.savez_compressed(a.out, meta=json.dumps(meta), **out)
    print(json.dumps({"out": str(a.out), "clean_rows": int(len(c["split"])), "added_degraded_train_rows": int(len(tr)),
                      "total_rows": int(len(out["split"])), "val_rows": int((out["split"] == 1).sum()),
                      "tok_rows": int(len(out["tok"])), "off_ok": bool(out["off"][-1] == len(out["tok"]))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
