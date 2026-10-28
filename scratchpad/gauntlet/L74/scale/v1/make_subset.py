"""Rows of mix_v1.npz -> a smaller train_gen npz (same keys / meta / vocab) + its memory tables (same packed tables, row_tab subset).
Splits are kept (0 train, 1 HF held-out = the step trainer's selection rows, 3 v32 held-out = never used).
  default:           rows whose deciding side plays one deck (--cards, default icebow: pipeline/decks/icebow.yaml, any forms)
  --v32-train-only:  the CONTROL set (lead 10-28): v32 TRAIN rows (src 0, split 0) + every split-1 row (selection only, never trained on)
  --mmap-cache-dir:  read the mix memory-mapped (pods with a 62 GB container cap; needs PYTHONPATH=<code dir>; extracts ~54 GB there)
    python make_subset.py --mix mix_v1.npz --memory mix_v1_memory.npz --out ice_v1.npz
"""
import argparse
import json
from pathlib import Path

import numpy as np

ICEBOW = ("tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", type=Path, required=True)
    ap.add_argument("--memory", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cards", default=",".join(ICEBOW))
    ap.add_argument("--v32-train-only", action="store_true")
    ap.add_argument("--mmap-cache-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.mmap_cache_dir:
        from pipeline.dataset_spool import load_mapped
        arrs, meta = load_mapped(a.mix, a.mmap_cache_dir)
        files, get = list(arrs), arrs.__getitem__
    else:
        z = np.load(a.mix, allow_pickle=False)
        meta = json.loads(str(z["meta"]))
        files, get = [k for k in z.files if k != "meta"], z.__getitem__
    vocab = meta["card_vocab"]
    want = sorted(vocab.index(k) for k in a.cards.split(","))
    if a.v32_train_only:
        keep = np.where(((get("src") == 0) & (get("split") == 0)) | (get("split") == 1))[0]
    else:
        keep = np.where((np.sort(get("deck_card"), 1) == np.array(want)[None, :]).all(1))[0]
    off = np.asarray(get("off"))
    ln = off[keep + 1] - off[keep]
    start = np.concatenate([[0], np.cumsum(ln)[:-1]])
    tsel = np.repeat(off[keep] - start, ln) + np.arange(int(ln.sum()))      # = concat of arange(off[i], off[i+1]) over keep
    out = {}
    for k in files:
        if k in ("meta", "tags"):
            continue
        v = get(k)
        if k in ("tok", "unit_form"):
            out[k] = v[tsel]
        elif k == "off":
            out[k] = np.concatenate([[0], np.cumsum(ln)]).astype(v.dtype)
        else:
            out[k] = v[keep]
    out["tags"] = np.asarray(get("tags"))                  # rep still indexes the full tag list
    sp = out["split"]
    st = {"rows": int(len(keep)), "split_counts": {str(s): int((sp == s).sum()) for s in np.unique(sp)},
          "src_counts": {str(s): int((out["src"] == s).sum()) for s in np.unique(out["src"])},
          "play_rows": int((out["y_gate"] > 0).sum()),
          "cards": "v32-train-only" if a.v32_train_only else a.cards}
    meta = dict(meta, subset={"of": str(a.mix), **st})
    np.savez(a.out, meta=json.dumps(meta), **out)
    if a.memory is not None:
        m = np.load(a.memory, allow_pickle=False)
        mm = json.loads(str(m["meta"]))
        mm.update(dataset=str(a.out), rows=int(len(keep)), rows_with_table=int((m["row_tab"][keep] >= 0).sum()))
        np.savez(a.out.with_name(a.out.stem + "_memory.npz"), **{k: m[k] for k in m.files if k.startswith("tab_")},
                 row_tab=m["row_tab"][keep], meta=json.dumps(mm))
    print(json.dumps(st))


if __name__ == "__main__":
    main()
