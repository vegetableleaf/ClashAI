"""Input automation: taps, card placement, and the emote flow."""
from __future__ import annotations

import random
import time

import pyautogui

pyautogui.FAILSAFE = True   # slam mouse into a screen corner to abort
pyautogui.PAUSE = 0.0


class Controller:
    def __init__(self, capture, cfg):
        self.capture = capture
        self.cfg = cfg

    def _screen(self, nx: float, ny: float):
        return self.capture.to_screen(nx, ny)

    def tap(self, nx: float, ny: float, jitter_px: int = 2) -> None:
        x, y = self._screen(nx, ny)
        x += random.randint(-jitter_px, jitter_px)
        y += random.randint(-jitter_px, jitter_px)
        pyautogui.click(x, y)

    def play_card(self, slot_nx: float, slot_ny: float, target_nx: float, target_ny: float) -> None:
        """Tap-to-select a hand card, then tap-to-place it on the target."""
        sx, sy = self._screen(slot_nx, slot_ny)
        tx, ty = self._screen(target_nx, target_ny)
        pyautogui.click(sx, sy)
        time.sleep(self.cfg.get("timing", "select_delay", default=0.05))
        pyautogui.click(tx, ty)

    def emote_good_game(self) -> None:
        """Open the emote wheel and select the 'Good game!' text emote."""
        button = self.cfg.get("emote", "button", default=[0.08, 0.92])
        good_game = self.cfg.get("emote", "good_game", default=[0.30, 0.55])
        delay = self.cfg.get("emote", "open_delay", default=0.4)
        self.tap(*button)
        time.sleep(delay)
        self.tap(*good_game)
