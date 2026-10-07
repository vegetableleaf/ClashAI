"""Passive trophy reading for ladder_nav (2026-10-07). Two numbers, both optional, never raises:
  total  the trophy counter on the main menu (top-left, right of the cup): e.g. 11222
  delta  the trophy change on the results screen (right end of OUR banner): |+30| -> 30. The sign glyph is NOT read
         (it renders as a tiny dot during the banner animation); ladder_nav takes the sign from the WINNER banner.
Method: both numbers use the same 24-26 px game font, light fill (gold on the menu, white on results) with a dark
outline, so mask = red channel > 190, split into connected components (height filter drops cup / sign / "+"), each
digit resized to 16x24 and matched to the nearest exemplar in L73/trophies/digits.npz (built from labelled frames by
L73/trophies/build_digits.py). A glyph further than MAX_DIST from every exemplar -> the whole read is None.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
DIGITS = HERE.parents[1] / "L73" / "trophies" / "digits.npz"
MAIN_ROI = (376, 315, 540, 385)        # x0, y0, x1, y1 on the 900x1600 frame; starts right of the trophy cup
RESULT_ROI = (700, 905, 800, 985)      # right of the "+"/"-" sign in our banner
H_MIN, H_MAX, W_MIN, W_MAX = 20, 30, 7, 28
MAX_DIST = 0.20                        # mean |pixel diff| (0..1) to the nearest exemplar; measured max 0.107 (results frames), 0.000 (menu)
SIZE = (16, 24)


def glyphs(img, roi) -> list[np.ndarray]:
    """Digit-shaped light blobs inside roi, left to right, each as a flat float vector."""
    x0, y0, x1, y1 = roi
    m = (img[y0:y1, x0:x1, 2] > 190).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    out = []
    for x, y, w, h, _a in sorted(map(tuple, st[1:])):
        if H_MIN <= h <= H_MAX and W_MIN <= w <= W_MAX:
            g = cv2.resize(m[y:y + h, x:x + w] * 255, SIZE, interpolation=cv2.INTER_AREA)
            out.append(g.astype(np.float32).ravel() / 255.0)
    return out


class TrophyReader:
    def __init__(self, path: Path = DIGITS):
        d = np.load(path)
        self.X, self.y = d["X"].astype(np.float32) / 255.0, d["y"]

    def _digits(self, img, roi) -> str | None:
        s = ""
        for g in glyphs(img, roi):
            dist = np.abs(self.X - g).mean(axis=1)
            i = int(dist.argmin())
            if dist[i] > MAX_DIST:
                return None
            s += str(int(self.y[i]))
        return s or None

    def total(self, img) -> int | None:
        """Main-menu trophy counter, or None. 4-5 digits only."""
        try:
            s = self._digits(img, MAIN_ROI)
            return int(s) if s and 4 <= len(s) <= 5 else None
        except Exception:                                  # noqa: BLE001 -- passive logging never breaks navigation
            return None

    def delta(self, img) -> int | None:
        """Results-screen trophy change magnitude (1-2 digits), or None."""
        try:
            s = self._digits(img, RESULT_ROI)
            return int(s) if s and len(s) <= 2 else None
        except Exception:                                  # noqa: BLE001
            return None


def load(path: Path = DIGITS) -> TrophyReader | None:
    """None when the digit bank is missing: callers then log null and carry on."""
    try:
        return TrophyReader(path)
    except Exception:                                      # noqa: BLE001
        return None
