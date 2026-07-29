"""Screen capture and normalized -> screen coordinate mapping.

Captures the Clash Royale render area on PC (Google Play Games). The region is
PHYSICAL pixels; mss makes the process DPI-aware so capture and mouse/`pyautogui`
coordinates share the same pixel space.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import mss
import numpy as np

try:  # pragma: no cover - optional at import time
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
        r = self._region
        if r is None:
            raise RuntimeError("Capture region unknown; cannot map coordinates.")
        return int(r.left + nx * r.width), int(r.top + ny * r.height)

    def to_norm(self, sx: int, sy: int) -> Tuple[float, float]:
        """Map an absolute screen pixel to normalized [0..1] within the region."""
        r = self._region
        if r is None:
            raise RuntimeError("Capture region unknown; cannot map coordinates.")
        return (sx - r.left) / r.width, (sy - r.top) / r.height
