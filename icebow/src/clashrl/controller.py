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

    def tap(self, nx: float, ny: float) -> None:
        x, y = self.capture.to_screen(nx, ny)
        pyautogui.click(x, y)

    def play_card(self, slot_nx: float, slot_ny: float, target_nx: float, target_ny: float) -> None:
        """Tap-select a hand card, then tap-place it on the target."""
        sx, sy = self.capture.to_screen(slot_nx, slot_ny)
        tx, ty = self.capture.to_screen(target_nx, target_ny)
        pyautogui.click(sx, sy)
        time.sleep(self.cfg.get("play", "select_delay", default=0.08))
        pyautogui.click(tx, ty)
