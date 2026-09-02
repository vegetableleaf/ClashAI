"""Split kitka's segment library into a TRAIN slice and a HELD-OUT slice, deterministically.

Why this exists (HANDOFF 5az.5 / 5bb): 69 of 230 detector classes have ZERO real val instances and the
evolution classes kitka fixes have 0-2, so mAP on the real val set cannot see whether the import taught
them anything. The held-out slice is imported into its OWN bank (`--bank`) and composed onto VAL frames
into its own folder; the training synth never sees those sprites, so a per-class read on that set is a
genuine "unseen sprite of a class we only learned from synth" measurement.

The split is by sha1 of the file name, so it is reproducible and a re-run moves nothing.

    python tools/detect/kitka_split.py --src data/kitka/detector_data/segment/segment \
        --out data/kitka/split --holdout 0.2
then
    run.py katacr-segments --src data/kitka/split/train   --src-width 735 --prefix kitka
    run.py katacr-segments --src data/kitka/split/holdout --src-width 735 --prefix kitka \
        --bank data/detect/sprites_holdout
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--min-holdout", type=int, default=3,
                    help="a class with fewer segments than this is NOT split (all go to train)")
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    tr, ho = out / "train", out / "holdout"
    for d in (tr, ho):
        if d.exists():
            shutil.rmtree(d)
    n_tr = n_ho = 0
    rows = []
    for cls in sorted(p for p in src.iterdir() if p.is_dir()):
        pngs = sorted(cls.glob("*.png"))
        if not pngs:
            continue
        k_ho = int(round(len(pngs) * a.holdout))
        if len(pngs) < a.min_holdout / a.holdout or k_ho == 0:
            k_ho = 0
        # rank by hash, hold out the lowest k -- deterministic, name-only
        ranked = sorted(pngs, key=lambda p: hashlib.sha1(p.name.encode()).hexdigest())
        hold = set(ranked[:k_ho])
        for p in pngs:
            dst = (ho if p in hold else tr) / cls.name
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / p.name)
        n_tr += len(pngs) - k_ho
        n_ho += k_ho
        rows.append((cls.name, len(pngs) - k_ho, k_ho))
    print(f"[kitka_split] {len(rows)} classes -> train {n_tr}, holdout {n_ho}  ({out})")
    for c, t, h in rows:
        if h:
            print(f"   {c:<30} train {t:4d}  holdout {h:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
