"""Screen capture and normalized -> screen coordinate mapping.

Captures the Clash Royale render area on PC (Google Play Games). The region is
PHYSICAL pixels; mss makes the process DPI-aware so capture and mouse/`pyautogui`
coordinates share the same pixel space.
"""
from __future__ import annotations

import threading
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
        # mss wraps thread-local GDI/BitBlt resources on Windows -- an instance made on one
        # thread fails (silently or with "BitBlt failed") when grabbed from another. play/env
        # only ever call grab() from their own single loop thread, so a shared instance was
        # never a problem there; the launcher's Flask server runs threaded=True, so a request
        # can land on a different worker thread each time. threading.local() gives every
        # thread its own mss() the first time IT calls grab(), instead of sharing one.
        self._sct_local = threading.local()
        if region is not None and (not isinstance(region, (list, tuple)) or len(region) != 4):
            print(f"[capture] window.region must be 4 numbers [left, top, width, height] or null "
                  f"(got {region!r}) -- ignoring it and auto-detecting the window by title instead.")
            region = None
        self._explicit = region is not None
        self._region: Optional[Region] = Region(*region) if region else None
        if self._region is None:
            self.refresh_region()

    @property
    def _sct(self) -> mss.mss:
        sct = getattr(self._sct_local, "sct", None)
        if sct is None:
            sct = mss.mss()
            self._sct_local.sct = sct
        return sct

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
            # Google Play Games draws a CUSTOM title bar INSIDE the Win32 client area, so neither the
            # window rect nor GetClientRect isolates the game render. Every normalized coordinate
            # (hand slots, elixir bar, templates, taps) is calibrated to the RENDER area -> detect it
            # from CONTENT: trim unsaturated chrome rows on top + black pillarbox columns, then sanity-
            # check the aspect. Falls back to the client rect, then the window rect.
            base = self._client_area(w) or Region(int(w.left), int(w.top), int(w.width), int(w.height))
            render = self._render_area(base)
            self._render_locked = render is not None      # False -> grab() keeps retrying the scan
            self._region = render or base
        return self._region

    @staticmethod
    def _client_area(w) -> Optional[Region]:
        """The window's CLIENT area in physical screen pixels (drops the OS title bar/borders)."""
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

    def _render_area(self, base: Region) -> Optional[Region]:
        """Locate the GAME RENDER inside a window area by content. Google Play Games draws a
        custom TITLE BAR **and a LEFT ICON SIDEBAR** inside the client area; both are near-
        grayscale chrome while the game is saturated, and true pillarbox bars are near-black.
        Returns None (caller falls back + retries) when the scan is implausible -- e.g. a black
        loading screen or another window overlapping the game at scan time."""
        try:
            raw = self._sct.grab({"left": base.left, "top": base.top,
                                  "width": base.width, "height": base.height})
            img = cv2.cvtColor(np.asarray(raw), cv2.COLOR_BGRA2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            sat = hsv[..., 1].astype(np.float32)
            val = hsv[..., 2].astype(np.float32)
            h, w = sat.shape
            chrome = ((sat < 50.0) | (val < 25.0)).astype(np.float32)   # unsaturated OR dark = chrome-ish
            # 1. custom title bar: rows that are ALMOST ENTIRELY chrome (fraction, not mean -- the
            #    colorful app icon / window buttons can't stop the trim the way they skewed a mean).
            row_frac = chrome.mean(axis=1)
            top = 0
            limit = int(h * 0.12)
            while top < limit and row_frac[top] > 0.90:
                top += 1
            # 2. LEFT SIDEBAR (gray icon rail) or pillarbox: near-total chrome columns.
            col_frac = chrome[top:, :].mean(axis=0)
            col_val = val[top:, :].mean(axis=0)
            x0, x1 = 0, w
            while x0 < w * 0.25 and col_frac[x0] > 0.90:
                x0 += 1
            while x1 > w * 0.75 and col_val[x1 - 1] < 18.0:   # right side: black bars only
                x1 -= 1
            # 3. bottom black bar (rare; some window shapes letterbox below too).
            row_dark = val[top:, x0:x1].mean(axis=1)
            y1 = len(row_dark)
            while y1 > len(row_dark) * 0.85 and row_dark[y1 - 1] < 18.0:
                y1 -= 1
            rw, rh = x1 - x0, y1
            if rw < 200 or rh < 300:
                return None
            aspect = rw / float(rh)
            if not (0.50 <= aspect <= 0.68):          # game render is ~9:16 (0.566 calibrated)
                return None
            return Region(base.left + x0, base.top + top, int(rw), int(rh))
        except Exception:  # noqa: BLE001
            return None

    @property
    def region(self) -> Optional[Region]:
        return self._region

    def grab(self) -> Optional[np.ndarray]:
        """Return the captured region as a BGR image, or None if unavailable."""
        if self._region is None:
            self.refresh_region()
        elif not self._explicit and not getattr(self, "_render_locked", True):
            self.refresh_region()          # render not found yet (loading screen?) -> keep trying
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
