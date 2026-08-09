"""Backing store for the launcher's box-labelling view.

The detector is trained from frames with hand-drawn boxes around each unit. Until now
that step lived entirely outside this project -- export to Label Studio, draw there,
import back -- which is why the queue here filled up (frames are harvested automatically
during train-rl) while the labelled set stayed effectively empty: 37 of 39 label files
had no boxes in them at all, so there was nothing to train on.

This module is deliberately thin. It reads and writes the SAME on-disk layout the
existing detect-* commands and tools/detect/train.py already use -- Ultralytics' standard
YOLO layout -- so labelling here and labelling in an external tool remain interchangeable:

    data/detect/images/to_label/*.jpg     harvested, not yet labelled
    data/detect/images/train/<name>.jpg   labelled (moved here on save)
    data/detect/images/val/<name>.jpg     same, for the validation split
    data/detect/labels/train/<name>.txt   one line per box: "<class> <cx> <cy> <w> <h>"
    data/detect/classes.txt               class index -> name

Coordinates in the .txt are normalised to [0,1] and are CENTRE + size, not corners --
that is the YOLO convention, and getting it wrong silently trains a detector that aims
half a box off, so the conversion lives here and nowhere else.
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


class LabelError(ValueError):
    """A label request could not be satisfied (bad name, bad box, unknown class)."""


def _root(cfg) -> Path:
    return Path(cfg.root) / "data" / "detect"


def classes(cfg) -> List[str]:
    """The class list TRAINING uses -- config/detect_classes.yaml, same source as data.yaml.

    This used to read data/detect/classes.txt, and the two had drifted: removing the 11
    event-only cards took the taxonomy 236 -> 225, but classes.txt still held the old order.
    Everything from index 16 up was off by one or two, so a box drawn as `mini_pekka` (86 in
    the old list) was stored as 86 and trained as `minions` (86 in the new one). Measured on
    this dataset: 36 of 63 boxes carried a class the trainer read as a different card.

    The picker and the trainer must therefore read the SAME list, and the trainer's is the
    authority -- classes.txt is regenerated from it rather than trusted.
    """
    from ..detect import _load_classes
    try:
        names = _load_classes(cfg)
    except (OSError, ValueError):
        p = _root(cfg) / "classes.txt"
        return ([ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
                if p.exists() else [])
    # keep the on-disk copy in step, so anything reading it sees the same order
    p = _root(cfg) / "classes.txt"
    try:
        if not p.exists() or p.read_text(encoding="utf-8").split() != names:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(names) + "\n", encoding="utf-8")
    except OSError:
        pass
    return names


def _safe_name(name: str) -> str:
    """Reject anything that isn't a bare file name -- these come from the browser."""
    n = Path(str(name)).name
    if not n or n != str(name) or n.startswith("."):
        raise LabelError(f"bad image name: {name!r}")
    return n


def _split_dirs(cfg, split: str):
    if split not in ("train", "val"):
        raise LabelError(f"unknown split: {split!r}")
    r = _root(cfg)
    return r / "images" / split, r / "labels" / split


def queue(cfg, limit: int = 500) -> List[str]:
    """Frames waiting to be labelled, newest first (they are the most representative)."""
    d = _root(cfg) / "images" / "to_label"
    if not d.is_dir():
        return []
    files = [p for p in d.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in files[:limit]]


def samples_with_boxes(cfg, limit: int = 6) -> List[str]:
    """Names of already-labelled frames that actually carry boxes, newest first.

    The Models tab used to illustrate "what it was taught" with Ultralytics' own
    train_batch mosaics -- a 4x4 grid of augmented, colour-jittered, randomly cropped
    tiles with hairline boxes. That is a debugging artefact of the augmentation pipeline,
    not a picture of your data, and it reads as noise. These are your frames, unmodified,
    with your boxes drawn by the same code as the Labelling tab.
    """
    out: List[str] = []
    for split in ("train", "val"):
        img_dir, lbl_dir = _split_dirs(cfg, split)
        if not img_dir.is_dir() or not lbl_dir.is_dir():
            continue
        for p in img_dir.iterdir():
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            lp = lbl_dir / f"{p.stem}.txt"
            if lp.is_file() and any(ln.strip() for ln in lp.read_text(encoding="utf-8").splitlines()):
                out.append((p.stat().st_mtime, p.name))
    out.sort(reverse=True)
    return [n for _, n in out[:limit]]


def labelled(cfg) -> Dict[str, Any]:
    """What is already labelled, and how much of it actually carries boxes.

    An EMPTY label file is valid YOLO -- it means "this frame contains none of the
    classes" -- but a set that is mostly empty by accident trains the detector to
    predict nothing, so the two are counted separately rather than lumped together.
    """
    out: Dict[str, Any] = {"train": 0, "val": 0, "boxes": 0, "with_boxes": 0, "empty": 0}
    for split in ("train", "val"):
        img_dir, lbl_dir = _split_dirs(cfg, split)
        n = len([p for p in img_dir.iterdir()
                 if p.suffix.lower() in (".jpg", ".jpeg", ".png")]) if img_dir.is_dir() else 0
        out[split] = n
        if not lbl_dir.is_dir():
            continue
        for p in lbl_dir.glob("*.txt"):
            lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            out["boxes"] += len(lines)
            out["with_boxes" if lines else "empty"] += 1
    return out


def find_image(cfg, name: str) -> Optional[Path]:
    """Locate a frame by name in the queue or in either split."""
    name = _safe_name(name)
    r = _root(cfg)
    for rel in ("images/to_label", "images/train", "images/val"):
        p = r / rel / name
        if p.is_file():
            return p
    return None


def read_boxes(cfg, name: str) -> List[Dict[str, Any]]:
    """Existing boxes for a frame, as {cls, cx, cy, w, h} in normalised coordinates."""
    name = _safe_name(name)
    stem = Path(name).stem
    for split in ("train", "val"):
        _, lbl_dir = _split_dirs(cfg, split)
        p = lbl_dir / f"{stem}.txt"
        if not p.is_file():
            continue
        out = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if len(parts) != 5:
                continue
            try:
                out.append({"cls": int(parts[0]), "cx": float(parts[1]), "cy": float(parts[2]),
                            "w": float(parts[3]), "h": float(parts[4])})
            except ValueError:
                continue
        return out
    return []


def save(cfg, name: str, boxes: List[Dict[str, Any]], split: Optional[str] = None,
         val_frac: float = 0.15, seed: Optional[int] = None) -> Dict[str, Any]:
    """Write the boxes for one frame and move it out of the queue.

    Frames are assigned to train/val RANDOMLY rather than in arrival order: consecutive
    harvested frames come from the same match seconds apart and look nearly identical, so
    slicing the tail off as validation would measure the detector on frames it effectively
    trained on. An explicit `split` overrides that.
    """
    name = _safe_name(name)
    n_cls = len(classes(cfg))
    clean: List[str] = []
    for b in boxes or []:
        try:
            c = int(b["cls"])
            cx, cy, w, h = (float(b["cx"]), float(b["cy"]), float(b["w"]), float(b["h"]))
        except (KeyError, TypeError, ValueError):
            raise LabelError(f"malformed box: {b!r}") from None
        if n_cls and not (0 <= c < n_cls):
            raise LabelError(f"class index {c} out of range (0..{n_cls - 1})")
        # A box that leaves the frame, or has no area, poisons training silently.
        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
            raise LabelError("box centre outside the image")
        if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
            raise LabelError("box has no area")
        clean.append(f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    src = find_image(cfg, name)
    if src is None:
        raise LabelError(f"no such frame: {name}")
    if split is None:
        # keep a frame in the split it is already in, so re-editing never moves it
        split = "val" if src.parent.name == "val" else (
            "train" if src.parent.name == "train"
            else ("val" if (random.Random(seed if seed is not None else name).random() < val_frac)
                  else "train"))
    img_dir, lbl_dir = _split_dirs(cfg, split)
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    dst = img_dir / name
    if src != dst:
        shutil.move(str(src), str(dst))       # out of the queue, into the split
    (lbl_dir / f"{Path(name).stem}.txt").write_text(
        ("\n".join(clean) + "\n") if clean else "", encoding="utf-8")
    return {"name": name, "split": split, "boxes": len(clean)}


def status(cfg) -> Dict[str, Any]:
    """Everything the labelling view needs in one call."""
    lab = labelled(cfg)
    q = queue(cfg)
    return {
        "queue": q,
        "queue_count": len(q),
        "classes": classes(cfg),
        **lab,
    }
