"""Pack the detection dataset into ONE zip that a rented GPU can train from.

The 3070 in this machine has 8 GB, which at imgsz 960 forces batch 3 and rules out anything
bigger than yolo11s. That is now the ceiling: the data problem was solved by the KataCR import
(9,057 -> 38,265 boxes) and the measured gains since have come from the model, not the pictures.
A 16 GB card runs yolo11m at a sane batch, and free ones exist (Kaggle gives ~30 GPU-hours a
week), so the dataset has to become something uploadable.

Three details are what make the zip actually trainable on the other side rather than a pile of
files that needs hand-repair:

1. NO COMPRESSION. The payload is ~9,000 JPEGs and they are already compressed. Deflate spends
   minutes to save a fraction of a percent, and the upload is bounded by the network either way.

2. NO data.yaml. The one in data/detect carries an ABSOLUTE Windows path (`C:/Users/...`), which
   is meaningless on Linux and fails in a way that reads like a corrupt dataset. The notebook
   writes its own from classes.txt, which is the only file the class ORDER may ever come from --
   a yaml whose names drifted from classes.txt silently relabels every box.

3. THE SPLIT COMES ALONG. images/val is what makes a run on rented hardware comparable to a run
   here; leaving it out would mean scoring the new model on a different set than the old one and
   calling the difference progress.

`--own-only` exists because the KataCR half is public: the notebook can fetch those 6,623 frames
itself, so a re-upload after labelling only has to carry the frames that are actually new.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Optional

# (folder inside data/detect, required?) -- synth is generated and small, but it is part of what
# the local run trained on, so omitting it would make the comparison off by 3% of the images.
_PARTS = [("images/train", True), ("images/val", True),
          ("labels/train", True), ("labels/val", True),
          ("synth/images", False), ("synth/labels", False)]


def detect_pack(cfg, out: Optional[str] = None, own_only: bool = False) -> None:
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    classes = root / "classes.txt"
    if not classes.is_file():
        print(f"[pack] no {classes} -- nothing to describe the boxes with")
        return

    dest = Path(out) if out else root.parent / "exports" / "clashai-detect.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)

    n = skipped = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        for sub, required in _PARTS:
            d = root / sub
            if not d.is_dir():
                if required:
                    print(f"[pack] MISSING {sub} -- the zip would not train")
                continue
            for p in sorted(d.iterdir()):
                if not p.is_file():
                    continue
                # The KataCR frames came from a public repo; the notebook can pull them itself.
                if own_only and p.name.startswith("katacr_"):
                    skipped += 1
                    continue
                z.write(p, f"{sub}/{p.name}")
                n += 1
        z.write(classes, "classes.txt")
        n += 1

    # The notebook lands NEXT TO the zip, copied from the tracked original rather than kept as a
    # second editable copy: two files that drift is how the training settings stop matching the
    # local run, which is the one thing that makes the comparison meaningless.
    nb = Path(__file__).resolve().parents[2] / "tools" / "detect" / "kaggle_train.py"
    if nb.is_file():
        shutil.copyfile(nb, dest.with_name("kaggle_train.py"))

    gb = dest.stat().st_size / 1e9
    print(f"[pack] {n} file(s) -> {dest}  ({gb:.2f} GB)")
    if nb.is_file():
        print(f"[pack] notebook next to it: {dest.with_name('kaggle_train.py').name}")
    if skipped:
        print(f"[pack] left out {skipped} katacr_* file(s) (--own-only); the notebook re-imports "
              f"them from the public dataset")
    print(f"[pack] classes.txt is inside -- the notebook builds data.yaml FROM IT, because the "
          f"local data.yaml holds an absolute Windows path that means nothing on Linux")
