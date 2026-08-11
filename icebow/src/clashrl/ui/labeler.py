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


def queue(cfg, limit: int = 500, source: str = "to_label",
          cls: Optional[str] = None) -> List[str]:
    """Frames to work through, newest first.

    `source` picks WHICH frames, because "label the next unlabelled frame" is only half the job.
    The other half is fixing labels that already exist -- and 2,414 of them arrived from another
    machine, so they are exactly the ones nobody here has ever looked at. Reviewing an existing
    box is also the only way to fix the swarm-landing case (two Archers still merged into one
    blob get a single oversized box), which no amount of new labelling repairs.

        to_label   the harvest queue, nothing drawn yet
        train      already labelled, training side
        val        already labelled, validation side -- errors here poison every measurement
        labelled   both splits together

    `cls` narrows to frames containing that class, which is how you review one card's boxes
    rather than scrolling 2,400 frames hoping to meet it.
    """
    r = _root(cfg)
    if source == "to_label":
        dirs = [(r / "images" / "to_label", None)]
    elif source in ("train", "val"):
        dirs = [(r / "images" / source, r / "labels" / source)]
    elif source == "labelled":
        dirs = [(r / "images" / s, r / "labels" / s) for s in ("train", "val")]
    else:
        raise LabelError(f"unknown source: {source!r}")

    want_idx = None
    if cls:
        names = classes(cfg)
        if cls not in names:
            raise LabelError(f"unknown class: {cls!r}")
        want_idx = names.index(cls)

    files = []
    for img_dir, lbl_dir in dirs:
        if not img_dir.is_dir():
            continue
        for p in img_dir.iterdir():
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            if want_idx is not None:
                if lbl_dir is None:
                    continue                      # unlabelled frames cannot match a class
                lp = lbl_dir / f"{p.stem}.txt"
                if not lp.is_file():
                    continue
                hit = False
                for ln in lp.read_text(encoding="utf-8").splitlines():
                    parts = ln.split()
                    if parts and parts[0].isdigit() and int(parts[0]) == want_idx:
                        hit = True
                        break
                if not hit:
                    continue
            files.append(p)
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


# A rule-of-thumb floor for fine-tuning a YOLO detector, NOT a measurement from this project:
# below roughly this many instances a class tends not to be learned at all. It is here to turn
# "225 classes" into a short list of what to label next, not to promise a score.
BOXES_WANTED = 50


def coverage(cfg) -> Dict[str, Any]:
    """How many boxes and how many FRAMES exist per class -- i.e. what is still missing.

    Two counts, because they answer different questions. `boxes` is how many examples of a unit
    the detector gets to see; `images` is how many DIFFERENT frames they came from. Fifty boxes
    of Musketeer from three frames is three backgrounds, three lightings and three poses -- the
    detector can memorise that and still fail on the fourth. A class is only really covered when
    both numbers are up.

    Ordering is by need, not alphabet: the cards this bot must actually recognise come first.
    `deck` is what YOU play, `whitelist` is observation.detector_cards -- the threats the policy
    is fed. A class outside both can be left at zero without it costing anything, which is why
    the count alone is not a to-do list.
    """
    idx_to_name = classes(cfg)
    n_boxes = {n: 0 for n in idx_to_name}
    n_imgs = {n: 0 for n in idx_to_name}
    per_split = {n: {"train": 0, "val": 0} for n in idx_to_name}
    unknown = 0                       # class indices with no name -- a drifted classes.txt
    for split in ("train", "val"):
        _, lbl_dir = _split_dirs(cfg, split)
        if not lbl_dir.is_dir():
            continue
        for p in lbl_dir.glob("*.txt"):
            here = set()
            for ln in p.read_text(encoding="utf-8").splitlines():
                parts = ln.split()
                if not parts:
                    continue
                try:
                    i = int(parts[0])
                except ValueError:
                    continue
                if not (0 <= i < len(idx_to_name)):
                    unknown += 1
                    continue
                name = idx_to_name[i]
                n_boxes[name] += 1
                per_split[name][split] += 1
                here.add(name)
            for name in here:
                n_imgs[name] += 1

    deck, whitelist = _deck_keys(cfg), set(cfg.get("observation", "detector_cards", default=[]) or [])
    rows = []
    for i, name in enumerate(idx_to_name):
        in_deck, in_wl = name in deck, name in whitelist
        rows.append({
            "idx": i, "name": name,
            "boxes": n_boxes[name], "images": n_imgs[name],
            "train": per_split[name]["train"], "val": per_split[name]["val"],
            "deck": in_deck, "whitelist": in_wl,
            # what this class is FOR: your own cards are needed to read your side of the board,
            # whitelist cards are the threats the policy actually receives.
            "role": "deck" if in_deck else ("threat" if in_wl else "other"),
            "wanted": BOXES_WANTED if (in_deck or in_wl) else 0,
        })
    matters = [r for r in rows if r["role"] != "other"]
    return {
        "classes": rows,
        "wanted": BOXES_WANTED,
        "unknown_indices": unknown,
        "totals": {
            "classes": len(rows),
            "matters": len(matters),
            "matters_missing": sum(1 for r in matters if r["boxes"] == 0),
            "matters_thin": sum(1 for r in matters if 0 < r["boxes"] < BOXES_WANTED),
            "matters_done": sum(1 for r in matters if r["boxes"] >= BOXES_WANTED),
            "seen": sum(1 for r in rows if r["boxes"] > 0),
        },
    }


def _deck_keys(cfg) -> set:
    """Your own eight cards, base names -- evolutions share the base card's appearance."""
    try:
        from ..cards import CardDB
        out = set()
        for k in CardDB(cfg).deck_identities():
            out.add(k[:-4] if k.endswith("_evo") else k)
        return out
    except Exception:                 # a missing/!broken card DB must not break the labelling view
        return set()


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


def status(cfg, source: str = "to_label", cls: Optional[str] = None) -> Dict[str, Any]:
    """Everything the labelling view needs in one call."""
    lab = labelled(cfg)
    q = queue(cfg, source=source, cls=cls)
    return {
        "queue": q,
        "queue_count": len(q),
        "classes": classes(cfg),
        "source": source,
        "filter_class": cls,
        **lab,
    }
