"""L67h: merge teacher-corpus shards into one .npz the trainer can read.

Ragged layout, same as pipeline/dataset.py: `tok` is one long array of unit rows and `off` indexes into it, so
merging means concatenating `tok` and SHIFTING each shard's offsets by the running total. `rep` (match id) is
also shifted, because the split is by match and two shards both numbering from 0 would collide -- and a
collision would put the same match on both sides of the split, which is the leak the split exists to prevent.

Reads each shard with np.load(mmap-free) ONCE and materialises its arrays before indexing: an earlier merge in
this project hit MemoryError by slicing an NpzFile per row, which decompresses the whole array every time.

usage: python scratchpad/gauntlet/L67/merge_teacher.py --out <merged.npz> shard1.npz shard2.npz ...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

FLAT = ("sc", "past", "y_gate", "y_slot", "y_xy", "tick", "side", "y_wait_slot", "y_wait_dt", "y_crowns")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shards", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--val-every", type=int, default=5, help="1 in N MATCHES held out (never row-wise)")
    a = ap.parse_args()

    toks, offs, rep_all, flat = [], [], [], {k: [] for k in FLAT}
    tok_base, rep_base, meta = 0, 0, None
    for sh in a.shards:
        z = np.load(sh, allow_pickle=False)
        d = {k: np.array(z[k]) for k in z.files if k != "meta"}       # materialise once
        if meta is None and "meta" in z.files:
            meta = str(z["meta"])
        n = len(d["sc"])
        toks.append(d["tok"])
        offs.append(d["off"][1:] + tok_base)                          # drop the leading 0, shift the rest
        rep_all.append(d["rep"].astype(np.int64) + rep_base)
        for k in FLAT:
            flat[k].append(d[k])
        tok_base += int(d["off"][-1])
        rep_base += int(d["rep"].max()) + 1
        print(f"{sh.name}: {n} rows, {len(d['tok'])} unit rows, matches {int(d['rep'].max()) + 1}", flush=True)

    rep = np.concatenate(rep_all)
    out = {k: np.concatenate(v) for k, v in flat.items()}
    out["tok"] = np.concatenate(toks)
    out["off"] = np.concatenate([[0], np.concatenate(offs)]).astype(np.int64)
    out["rep"] = rep.astype(np.int32)
    out["split"] = ((rep % int(a.val_every)) == 0).astype(np.int8)
    assert int(out["off"][-1]) == len(out["tok"]), "offset table does not end at the token count"
    assert len(out["off"]) == len(out["sc"]) + 1, "one offset per row plus the leading zero"
    out["meta"] = np.array(meta or json.dumps({"source": "rollout_search_teacher"}))
    np.savez_compressed(a.out, **out)
    print(json.dumps({"rows": int(len(out["sc"])), "unit_rows": int(len(out["tok"])),
                      "matches": int(rep.max()) + 1, "val_rows": int((out["split"] == 1).sum()),
                      "gate_rate": round(float(out["y_gate"].mean()), 4), "out": str(a.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
