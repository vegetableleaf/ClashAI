"""Build a small, separate HP-BAR dataset out of KataCR's annotations.

WHY A SECOND DATASET AND NOT TWO MORE CLASSES IN THE MAIN ONE
-------------------------------------------------------------
The 225-class detector sits at mAP50 0.805 and cost a 7.8 h Kaggle run. Appending classes
to `classes.txt` means retraining all of it to use them, and putting that number at risk
for two classes that are geometrically trivial. A 2-class `yolo11n` trains on the 8 GB
card in about an hour, cannot touch the main model, and is throwaway if it disappoints.

WHAT IS IN IT
-------------
    0  hp_bar         KataCR `bar`                     -- the bar above a UNIT
    1  tower_hp_bar   `tower-bar`, `king-tower-bar`,
                      `dagger-duchess-tower-bar`       -- the bar above a TOWER

`bar-level` is deliberately NOT a class: 468 boxes across 86 frames is not a training set,
it is a rounding error. Unit levels have to come from somewhere else.
`skeleton-king-bar` is also out -- it is an ABILITY CHARGE bar, not health, and calling it
health would poison the one number this detector exists to produce.

ALL 6,939 frames are used, including the ~310 that `katacr_boxes.py` rejects whole. That
rejection exists because an unnameable BODY left unlabelled teaches the detector to
suppress that body. This model has no body classes, so the reason does not apply here.

IMAGES ARE HARDLINKED, NOT COPIED. 6,939 frames is ~740 MB, and they already exist on this
disk. A hardlink is the same bytes under a second name; deleting one name never touches
the other. Falls back to a copy if the link fails (different volume, odd filesystem).

VALIDATION SPLIT IS BY EPISODE, NOT BY FRAME. Consecutive frames of one recording are near
duplicates -- a random frame split would put a frame's own neighbours in val and report a
score that means nothing.

    python icebow/tools/detect/build_bars.py --src <katacr_source> [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import shutil
from collections import Counter
from pathlib import Path

import yaml

# their class name -> ours. Anything not named here is dropped.
_MAP = {
    "bar": 0,
    "tower-bar": 1,
    "king-tower-bar": 1,
    "dagger-duchess-tower-bar": 1,
}
_NAMES = ["hp_bar", "tower_hp_bar"]

# Hold out every Nth episode. 41 episodes is few, and they differ wildly in length, so a
# 1-in-10 hold-out landed on 222 frames -- too thin to separate a real regression from noise.
_VAL_EVERY = 6


def _find_part2(src: Path) -> tuple[Path, Path] | None:
    """-> (annotation.txt, image root). They are NOT always the same directory: the copy on
    this machine keeps annotation.txt at the top and the frames under the unpacked repo."""
    ann = next((p for p in (src / "annotation.txt", src / "part2" / "annotation.txt")
                if p.is_file()), None)
    if ann is None:
        ann = next(iter(src.rglob("annotation.txt")), None)
    if ann is None:
        return None
    # the image root is whichever candidate actually holds the first referenced frame
    first = ann.read_text(encoding="utf-8").split("\n", 1)[0].split()[0].lstrip("./")
    for c in (ann.parent, *src.rglob("part2")):
        if (c / first).is_file():
            return ann, c
    return None


def _their_names(src: Path) -> dict[int, str]:
    y = next(iter([src / "ClashRoyale_detection.yaml"]
                  if (src / "ClashRoyale_detection.yaml").is_file()
                  else src.rglob("ClashRoyale_detection.yaml")), None)
    if y is None:
        raise SystemExit(f"ClashRoyale_detection.yaml not found under {src}")
    n = yaml.safe_load(y.read_text(encoding="utf-8"))["names"]
    return n if isinstance(n, dict) else dict(enumerate(n))


def _link(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"C:\Users\Maxi\Desktop\katacr_source")
    ap.add_argument("--out", default="icebow/data/bars")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    found = _find_part2(Path(a.src))
    if found is None:
        raise SystemExit(f"no annotation.txt (or no frames beside it) under {a.src}")
    ann, sp = found
    their = _their_names(Path(a.src))
    out = Path(a.out)

    # ---- pass 1: read and group by episode -----------------------------
    # rel path is "<session>/<episode>/<frame>.jpg"; the first two parts identify a
    # recording, and frames inside one are near duplicates.
    episodes: dict[str, list[tuple[str, Path, list[str]]]] = {}
    boxes = Counter()
    empty = 0

    for line in ann.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        rel = parts[0].lstrip("./")
        img, lab = sp / rel, sp / parts[1].lstrip("./")
        if not img.is_file() or not lab.is_file():
            continue

        rows = []
        for row in lab.read_text(encoding="utf-8").splitlines():
            q = row.split()
            if len(q) < 5:
                continue
            c = _MAP.get(their.get(int(q[0]), ""))
            if c is None:
                continue
            rows.append(f"{c} {float(q[1]):.6f} {float(q[2]):.6f} "
                        f"{float(q[3]):.6f} {float(q[4]):.6f}")
            boxes[_NAMES[c]] += 1
        if not rows:
            # kept on purpose: a frame with no bar is a real negative, and the detector
            # needs to learn that a bar-less arena has no bars in it.
            empty += 1

        ep = "/".join(Path(rel).parts[:2])
        episodes.setdefault(ep, []).append(("katacr_" + rel[:-4].replace("/", "_"), img, rows))

    eps = sorted(episodes)
    val_eps = {e for i, e in enumerate(eps) if i % _VAL_EVERY == _VAL_EVERY - 1}
    n_train = sum(len(episodes[e]) for e in eps if e not in val_eps)
    n_val = sum(len(episodes[e]) for e in val_eps)

    print(f"[bars] {sp}")
    print(f"[bars] {len(eps)} episode(s), {n_train + n_val} frame(s), "
          f"{empty} of them with no bar (kept as negatives)")
    for n, c in boxes.most_common():
        print(f"[bars]   {n:<14} {c:>7} box(es)")
    print(f"[bars] split by EPISODE: {len(eps) - len(val_eps)} train / {len(val_eps)} val "
          f"-> {n_train} / {n_val} frame(s)")

    if a.dry_run:
        print("[bars] --dry-run: nothing written")
        return

    # ---- pass 2: write --------------------------------------------------
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    for ep in eps:
        split = "val" if ep in val_eps else "train"
        for stem, img, rows in episodes[ep]:
            _link(img, out / "images" / split / f"{stem}.jpg")
            (out / "labels" / split / f"{stem}.txt").write_text(
                "".join(r + "\n" for r in rows), encoding="utf-8")

    (out / "data.yaml").write_text(
        yaml.safe_dump({"path": str(out.resolve()), "train": "images/train",
                        "val": "images/val", "names": dict(enumerate(_NAMES))},
                       sort_keys=False), encoding="utf-8")
    print(f"[bars] wrote {out}/ (images hardlinked, {len(_NAMES)} classes)")


if __name__ == "__main__":
    main()
