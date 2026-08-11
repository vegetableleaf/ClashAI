"""`run.py detect-check` -- draw the GROUND TRUTH onto frames and look at it.

WHY THIS EXISTS. Labels are numbers in a .txt beside a clean .jpg, so a dataset can be verified
by counting -- files pair up, classes resolve, totals look right -- while every box sits in the
wrong place. That failure is invisible to every check we had. It happened here once already: a
stale class list meant 36 of 63 boxes carried a number the trainer read as a different card, and
nothing in the counts showed it. The only way to know is to render the numbers back onto the
picture and use your eyes.

It matters more now that datasets arrive from other people. 2,414 frames imported from another
machine are 2,414 assertions about what is in them, and the cost of being wrong is a detector
trained to find Musketeers where the Ice Wizards are.

`--class` is the point of the tool rather than a convenience: coverage says magic_archer has one
box, and one box is exactly the case where a single mislabel is 100% of what the class will ever
learn. This is how you look at that box.

Draws from the label FILE, never from the model -- `detect-preview` is the one that shows
predictions. Confusing the two would let a wrong dataset validate itself.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np


def _tiles(images: List[np.ndarray], cols: int) -> np.ndarray:
    """Lay tiles out in a grid, padding the last row so hconcat/vconcat agree on shapes.

    Tiles are forced to ONE size first. Frames in this dataset do not all share a resolution --
    ours are a 756x1334 client, the imported ones are not -- and cv2.hconcat asserts on mismatched
    shapes rather than doing anything sensible. Found by running this against two classes.
    """
    if not images:
        return np.zeros((10, 10, 3), np.uint8)
    h = max(im.shape[0] for im in images)
    w = max(im.shape[1] for im in images)
    images = [im if im.shape[:2] == (h, w) else cv2.resize(im, (w, h)) for im in images]
    rows = []
    for i in range(0, len(images), cols):
        row = images[i:i + cols]
        while len(row) < cols:
            row.append(np.zeros((h, w, 3), np.uint8))
        rows.append(cv2.hconcat(row))
    return cv2.vconcat(rows) if len(rows) > 1 else rows[0]


def detect_check(cfg, n: int = 6, split: str = "train", cls: Optional[str] = None,
                 out: Optional[str] = None, seed: Optional[int] = None,
                 min_boxes: int = 1, scale: float = 0.5) -> None:
    from .detect import _load_classes
    names = _load_classes(cfg)
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    want_idx = None
    if cls:
        if cls not in names:
            near = [x for x in names if cls.lower() in x.lower()][:8]
            print(f"[detect-check] '{cls}' is not in the taxonomy."
                  + (f" Did you mean: {', '.join(near)}" if near else ""))
            return
        want_idx = names.index(cls)

    splits = ("train", "val") if split == "both" else (split,)
    cands = []
    for sp in splits:
        lbl_dir = root / "labels" / sp
        if not lbl_dir.is_dir():
            continue
        for p in sorted(lbl_dir.glob("*.txt")):
            rows = []
            for ln in p.read_text(encoding="utf-8").splitlines():
                parts = ln.split()
                if len(parts) != 5:
                    continue
                try:
                    rows.append((int(parts[0]), *[float(v) for v in parts[1:]]))
                except ValueError:
                    continue
            if len(rows) < min_boxes:
                continue
            if want_idx is not None and not any(r[0] == want_idx for r in rows):
                continue
            cands.append((sp, p, rows))

    if not cands:
        where = f"{split} split" + (f" containing {cls}" if cls else "")
        print(f"[detect-check] no labelled frame in the {where} with at least {min_boxes} box(es)")
        return
    # Report the pool BEFORE sampling: "6 frames shown" means something different when the pool
    # is 6 than when it is 247, and for a thin class the pool size IS the finding.
    print(f"[detect-check] {len(cands)} frame(s) match" + (f" for {cls}" if cls else "")
          + f"; showing up to {n}")
    if seed is not None:
        random.seed(seed)
    picks = cands if len(cands) <= n else random.sample(cands, n)

    tiles = []
    for sp, lp, rows in picks:
        ip = None
        for ext in (".jpg", ".jpeg", ".png"):
            q = root / "images" / sp / (lp.stem + ext)
            if q.is_file():
                ip = q
                break
        if ip is None:
            print(f"[detect-check] {lp.name}: no image beside this label -- skipped")
            continue
        im = cv2.imread(str(ip))
        if im is None:
            print(f"[detect-check] {ip.name}: unreadable -- skipped")
            continue
        H, W = im.shape[:2]
        for c, cx, cy, bw, bh in rows:
            name = names[c] if 0 <= c < len(names) else f"?{c}"
            # the class asked about is highlighted; everything else stays context
            hit = want_idx is not None and c == want_idx
            col = (60, 200, 255) if hit else (90, 220, 120)
            x1, y1 = int((cx - bw / 2) * W), int((cy - bh / 2) * H)
            x2, y2 = int((cx + bw / 2) * W), int((cy + bh / 2) * H)
            cv2.rectangle(im, (x1, y1), (x2, y2), col, 3 if hit else 2)
            tw = 8 * len(name) + 6
            cv2.rectangle(im, (x1, max(0, y1 - 17)), (x1 + tw, max(0, y1)), (18, 18, 18), -1)
            cv2.putText(im, name, (x1 + 3, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, .42, col, 1)
        # the split is drawn ON the tile: a val frame among train frames is the mistake that
        # quietly inflates every score afterwards, so it must be visible at a glance
        cv2.putText(im, f"{sp}  {lp.stem[:28]}  {len(rows)} box(es)", (6, H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, .45, (230, 230, 230), 1)
        tiles.append(cv2.resize(im, (int(W * scale), int(H * scale))))

    if not tiles:
        print("[detect-check] nothing could be rendered")
        return
    sheet = _tiles(tiles, cols=min(4, len(tiles)))
    dest = Path(cfg.path(out)) if out else Path(cfg.path("data/detect_check.jpg"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"[detect-check] {len(tiles)} frame(s) -> {dest}")
