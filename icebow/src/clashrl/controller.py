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
        self._press(sx, sy)
        time.sleep(float(self.cfg.get("play", "select_delay", default=0.15)))
        self._press(tx, ty)
