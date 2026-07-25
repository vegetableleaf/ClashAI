"""Screen capture and normalized -> screen coordinate mapping."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import mss
import numpy as np

try:  # pragma: no cover - optional dependency at import time
    import pygetwindow as gw
except Exception:  # noqa: BLE001
    gw = None


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int


class WindowCapture:
    """Captures a region of the screen (the Clash Royale render area).

    Either locates the window by title substring, or uses an explicit region
    from config. Also converts normalized [0..1] coordinates to absolute
    screen pixels for the input controller.
    """

    def __init__(self, title_contains: Optional[str], region: Optional[List[int]] = None):
        self.title_contains = title_contains
        self._sct = mss.mss()
        self._explicit = region is not None
        self._region: Optional[Region] = Region(*region) if region else None
        if self._region is None:
            self.refresh_region()

    def refresh_region(self) -> Optional[Region]:
        if self._explicit or gw is None or not self.title_contains:
            return self._region
        needle = self.title_contains.lower()
        wins = [
            w for w in gw.getAllWindows()
            if needle in (w.title or "").lower() and w.width > 100 and w.height > 100
        ]
        if wins:
            w = wins[0]
            self._region = Region(int(w.left), int(w.top), int(w.width), int(w.height))
        return self._region

    @property
    def region(self) -> Optional[Region]:
        return self._region

    def grab(self) -> Optional[np.ndarray]:
        """Return the captured region as a BGR image, or None if unavailable."""
        if self._region is None:
            self.refresh_region()
        if self._region is None:
            return None
        r = self._region
        raw = self._sct.grab({"left": r.left, "top": r.top, "width": r.width, "height": r.height})
        img = np.asarray(raw)  # BGRA
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def to_screen(self, nx: float, ny: float) -> Tuple[int, int]:
        """Map normalized [0..1] client coordinates to absolute screen pixels."""
        r = self._region
        if r is None:
            raise RuntimeError("Capture region unknown; cannot map coordinates.")
        return int(r.left + nx * r.width), int(r.top + ny * r.height)
