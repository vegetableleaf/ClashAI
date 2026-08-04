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
        if region is not None and (not isinstance(region, (list, tuple)) or len(region) != 4):
            print(f"[capture] window.region must be 4 numbers [left, top, width, height] or null "
                  f"(got {region!r}) -- ignoring it and auto-detecting the window by title instead.")
            region = None
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
            # The WINDOW rect includes the title bar + borders; every normalized coordinate
            # (hand slots, elixir bar, tower HP boxes, templates, tap targets) is calibrated to
            # the RENDER area, so auto-detect must use the CLIENT rect. Falling back to the
            # window rect only if the Win32 query fails (non-Windows / odd window).
            self._region = self._client_area(w) or Region(int(w.left), int(w.top),
                                                          int(w.width), int(w.height))
        return self._region

    @staticmethod
    def _client_area(w) -> Optional[Region]:
        """The window's CLIENT area (the game render surface) in physical screen pixels."""
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = getattr(w, "_hWnd", None)
            if not hwnd:
                return None
            rect = wintypes.RECT()
            if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
                return None
            pt = wintypes.POINT(0, 0)
            if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt)):
                return None
            if rect.right > 100 and rect.bottom > 100:
                return Region(int(pt.x), int(pt.y), int(rect.right), int(rect.bottom))
        except Exception:  # noqa: BLE001
            return None
        return None

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
