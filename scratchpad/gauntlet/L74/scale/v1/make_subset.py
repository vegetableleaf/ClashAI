"""Rows of mix_v1.npz whose deciding side plays one deck (default: icebow, the 8 cards of pipeline/decks/icebow.yaml, any
forms) -> a smaller train_gen npz (same keys / meta / vocab) + its memory tables (same packed tables, row_tab subset).
Splits are kept (0 train, 1 HF held-out = the step trainer's selection rows, 3 v32 held-out = never used).
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
    a = ap.parse_args(argv)
    z = np.load(a.mix, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    vocab = meta["card_vocab"]
    want = sorted(vocab.index(k) for k in a.cards.split(","))
    keep = np.where((np.sort(z["deck_card"], 1) == np.array(want)[None, :]).all(1))[0]
    off = z["off"]
    tsel = np.concatenate([np.arange(off[i], off[i + 1]) for i in keep])
    out = {}
    for k in z.files:
        if k in ("meta", "tags"):
            continue
        v = z[k]
        if k in ("tok", "unit_form"):
            out[k] = v[tsel]
        elif k == "off":
            out[k] = np.concatenate([[0], np.cumsum(off[keep + 1] - off[keep])]).astype(v.dtype)
        else:
            out[k] = v[keep]
    out["tags"] = z["tags"]                              # rep still indexes the full tag list
    sp = out["split"]
    st = {"rows": int(len(keep)), "split_counts": {str(s): int((sp == s).sum()) for s in np.unique(sp)},
          "src_counts": {str(s): int((out["src"] == s).sum()) for s in np.unique(out["src"])},
          "play_rows": int((out["y_gate"] > 0).sum()), "cards": a.cards}
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
