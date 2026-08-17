"""Input automation for the learning bot: play a card via the mouse.

Same PC / Google Play Games window the policy trains on. mss makes the process
DPI-aware, so normalized->screen mapping matches the captured frames.
"""
from __future__ import annotations

import time

import pyautogui

pyautogui.FAILSAFE = True   # slam mouse into a screen corner to abort
pyautogui.PAUSE = 0.0


class Controller:
    def __init__(self, capture, cfg):
        self.capture = capture
        self.cfg = cfg

    def ensure_focus(self) -> bool:
        """Bring the game window to the FOREGROUND before tapping.

        Windows delivers the first click on an unfocused window to the focus change, not to the
        app -- so that tap selects nothing and the placement that follows lands with no card
        held. MEASURED on live_20260815_234336: 48% of plays never moved the elixir bar, and the
        split is diagnostic -- a tap within 1.5 s of the previous play failed 17% of the time,
        while a tap after a >3 s idle failed 63-82%. Consecutive taps keep the window hot;
        after a gap the first one is spent re-focusing. Nothing in the input path ever asked
        for focus.

        Cheap: reads the foreground handle and returns immediately when it is already ours.
        """
        try:
            import ctypes
            hwnd = self._hwnd()
            if not hwnd:
                return False
            if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                return True
            ctypes.windll.user32.ShowWindow(hwnd, 9)          # SW_RESTORE (no-op if not minimised)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(float(self.cfg.get("play", "focus_settle_s", default=0.06)))
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:  # noqa: BLE001
            return False

    def _hwnd(self):
        """HWND of the captured game window (cached; None if it cannot be found)."""
        if getattr(self, "_hwnd_cache", None):
            return self._hwnd_cache
        try:
            import pygetwindow as gw
            needle = (self.cfg.get("window", "title_contains", default="") or "").lower()
            if not needle:
                return None
            for w in gw.getAllWindows():
                if needle in (w.title or "").lower() and w.width > 100 and w.height > 100:
                    self._hwnd_cache = getattr(w, "_hWnd", None)
                    return self._hwnd_cache
        except Exception:  # noqa: BLE001
            pass
        return None

    def _press(self, x: int, y: int) -> None:
        """One tap the Android emulator actually registers.

        `pyautogui.click()` is move+down+up with NO dwell anywhere (PAUSE is 0). Google Play
        Games is a touch surface: it turns mouse events into synthetic touches, and a
        down/up in the same event batch as the move is routinely dropped -- the pointer
        appears at the new spot in the same frame the press arrives, so the press lands
        before the surface has the position. MEASURED on the 19:11 live match: 8 of 33 plays
        (24%) never happened -- the card was selected and the arena tap did nothing, which is
        exactly the "hovers over the card and never places" report. Split the gesture:
        move, let a frame pass, press, HOLD briefly, release.
        """
        pyautogui.moveTo(x, y)
        time.sleep(self.move_dwell)
        pyautogui.mouseDown(x, y)
        time.sleep(self.tap_hold)
        pyautogui.mouseUp(x, y)

    @property
    def move_dwell(self) -> float:
        return float(self.cfg.get("play", "move_dwell", default=0.03))

    @property
    def tap_hold(self) -> float:
        return float(self.cfg.get("play", "tap_hold", default=0.05))

    def tap(self, nx: float, ny: float) -> None:
        x, y = self.capture.to_screen(nx, ny)
        self._press(x, y)

    def play_card(self, slot_nx: float, slot_ny: float, target_nx: float, target_ny: float) -> None:
        """Tap-select a hand card, then tap-place it on the target."""
        sx, sy = self.capture.to_screen(slot_nx, slot_ny)
        tx, ty = self.capture.to_screen(target_nx, target_ny)
        if self.cfg.get("play", "ensure_focus", default=True):
            self.ensure_focus()          # an unfocused window eats the card tap (see ensure_focus)
        self._press(sx, sy)
        time.sleep(float(self.cfg.get("play", "select_delay", default=0.15)))
        self._press(tx, ty)
