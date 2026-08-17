"""Troop health-bar reader (HP fraction) -- a helper meant to run ON TOP of the object detector.

Unlike a TOWER's HP, which is printed as a NUMBER (read by the digit CNN in ``tower_hp.py``), a
TROOP's HP is a small **fill bar** floating just above the unit -- so we don't OCR it, we measure
the GREEN filled fraction of that bar. Given a detected troop's box, multiply the fraction by the
unit's max HP (from the card KB, keyed by the detected class) to get an *approximate absolute HP*.

This is deliberately a scaffold, NOT wired in yet (it needs the trained detector to supply boxes).
It is coarse by nature: a troop's bar usually only appears once it's been DAMAGED, it is tiny, and
bars overlap in a crowded push. Calibrate the band geometry + green range against real detected
boxes with ``annotate`` before trusting the numbers -- see the module constants.

Usage (later, in the detection loop)::

    from .troop_hp import read_hp_fraction
    frac = read_hp_fraction(frame, (x0, y0, x1, y1))     # normalized box; None if no bar visible
    hp   = frac * card_db.get(cls)["hitpoints"] if frac is not None else None
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

# HP-bar geometry as fractions -- CALIBRATE on real detected boxes (annotate() overlay helps).
_BAR_GAP = 0.004        # gap between the box top and the bar (fraction of FRAME height)
_BAR_H = 0.012          # bar band thickness to search (fraction of FRAME height)
_BAR_XPAD = 0.15        # widen the search strip beyond the box width (bar can overhang), frac of BOX width
# CR unit HP bars are a bright GREEN fill over a dark (red/black) EMPTY remainder of equal length.
_GREEN_LO = (36, 110, 80)
_GREEN_HI = (92, 255, 255)
_DARK_V = 85            # the 'empty' remainder reads as low-value (dark) pixels beside the green
_MIN_GREEN_COLS = 3     # need at least this many green columns to call a bar present


def read_hp_fraction(frame: np.ndarray, box: Tuple[float, float, float, float],
                     cfg=None) -> Optional[float]:
    """HP fill fraction (0..1) for a troop whose normalized box is ``(x0, y0, x1, y1)``.

    Returns None when no bar is visible (troop at full HP, or the bar is occluded). The bar is
    found in a thin band just ABOVE the box; ``filled`` = green columns, ``total`` = green plus
    the contiguous dark 'empty' remainder to its right, and the fraction is filled / total.
    """
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    bw = max(1e-3, x1 - x0)
    y_bot = int(max(0.0, y0) * h)
    y_top = max(0, y_bot - int((_BAR_GAP + _BAR_H) * h))
    xpad = _BAR_XPAD * bw
    sx0 = max(0, int((x0 - xpad) * w))
    sx1 = min(w, int((x1 + xpad) * w))
    if y_bot - y_top < 1 or sx1 - sx0 < 3:
        return None
    strip = frame[y_top:y_bot, sx0:sx1]
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    green_cols = cv2.inRange(hsv, _GREEN_LO, _GREEN_HI).any(0)   # a bar pixel in this column?
    if int(green_cols.sum()) < _MIN_GREEN_COLS:
        return None
    xs = np.where(green_cols)[0]
    gx0, gx1 = int(xs.min()), int(xs.max())
    filled = gx1 - gx0 + 1
    dark_cols = (hsv[..., 2] < _DARK_V).any(0)                   # 'empty' bar remainder = dark
    total, c = filled, gx1 + 1
    while c < dark_cols.shape[0] and dark_cols[c]:
        total += 1
        c += 1
    return float(min(1.0, filled / max(1, total)))


def annotate(frame: np.ndarray, boxes: List[Tuple[float, float, float, float]], cfg=None) -> np.ndarray:
    """Draw each box + its measured HP% on a copy of the frame (for calibrating the bar geometry
    once the detector is producing boxes). ``boxes`` are normalized (x0, y0, x1, y1)."""
    out = frame.copy()
    h, w = out.shape[:2]
    for box in boxes:
        x0, y0, x1, y1 = box
        p0, p1 = (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h))
        cv2.rectangle(out, p0, p1, (0, 255, 0), 1)
        frac = read_hp_fraction(frame, box, cfg)
        txt = f"{int(round(frac * 100))}%" if frac is not None else "--"
        cv2.putText(out, txt, (p0[0], max(10, p0[1] - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    return out
