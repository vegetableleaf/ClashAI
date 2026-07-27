"""Robust match-to-match menu navigation, shared by env.reset() (train-rl) and play (live).

Both used to have their own copy of the HOME/MATCH_END/UNKNOWN tap logic, and they drifted
apart -- play.py got a watchdog while env.py (what train-rl actually uses) did not, so train-rl
kept hanging on the results screen. This module is the single source of truth.

Robustness it adds over a plain "tap the fixed button coordinate":
  * Buttons are LOCATED by template when one is available (Battle via the home template; Play Again
    via an optional buttons.play_again_template), so a tap follows the button even if the layout or
    window shifts -- this is what a fixed coordinate cannot do (it "drifts" off the button).
  * A MATCH_END that is not advancing after nav.match_end_timeout seconds ESCALATES to the OK
    button, which returns HOME, where the located Battle button re-queues reliably.
  * An UNRECOGNISED screen that lingers past play.stuck_timeout is tapped to dismiss it (a post-match
    chest / level-up / season / offer popup) so navigation never hangs.
  * Every action is logged (to data/nav_<label>_<ts>.log unless a log callable is supplied).
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .states import GameState


class MenuNavigator:
    def __init__(self, cfg, controller, vision, label: str = "run",
                 log: Optional[Callable[[str], None]] = None):
        self.controller = controller
        self.vision = vision
        self.battle = cfg.get("buttons", "battle_button", default=[0.5, 0.9])
        self.results_ok = cfg.get("buttons", "results_ok", default=[0.5, 0.9])
        self.play_again = cfg.get("buttons", "play_again", default=self.results_ok)
        self.menu_delay = float(cfg.get("nav", "menu_delay", default=1.0))
        self.poll_dt = 1.0 / float(cfg.get("nav", "poll_hz", default=6))
        self.match_end_timeout = float(cfg.get("nav", "match_end_timeout", default=6.0))
        self.stuck_timeout = float(cfg.get("play", "stuck_timeout", default=25.0))
        self.stuck_tap = cfg.get("play", "stuck_tap", default=self.results_ok)
        _home = cfg.get("states", "home_menu", default={}) or {}
        self.home_tpl = _home.get("template", "home_menu.png")
        self.home_thr = float(_home.get("threshold", 0.8))
        self.pa_tpl = cfg.get("buttons", "play_again_template", default=None)   # optional button PNG
        self.pa_thr = float(cfg.get("buttons", "play_again_threshold", default=0.8))
        self._match_end_since: Optional[float] = None
        self._stuck_since: Optional[float] = None
        self._log = log or self._make_file_log(cfg, label)

    @staticmethod
    def _make_file_log(cfg, label: str) -> Callable[[str], None]:
        path = Path(cfg.path("data")) / f"nav_{label}_{datetime.now():%Y%m%d_%H%M%S}.log"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        def _log(msg: str) -> None:
            line = f"{datetime.now():%H:%M:%S} {msg}"
            print(line)
            try:
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass
        return _log

    def reset_state(self) -> None:
        """Call when NOT on a menu (in-match / new episode) to clear the stuck timers."""
        self._match_end_since = None
        self._stuck_since = None

    def _locate(self, frame, tpl, thr, fallback):
        pt = self.vision.locate(frame, tpl, thr) if tpl else None
        return (pt, True) if pt else (fallback, False)

    def handle(self, frame, state) -> None:
        """Perform one navigation action for a non-IN_MATCH state."""
        if state == GameState.HOME:
            self._match_end_since = self._stuck_since = None
            pt, located = self._locate(frame, self.home_tpl, self.home_thr, self.battle)
            self._log(f"[nav] HOME -> Battle {'(located)' if located else '(fixed)'} "
                      f"({pt[0]:.3f},{pt[1]:.3f})")
            self.controller.tap(*pt)
            time.sleep(self.menu_delay)
        elif state == GameState.MATCH_END:
            self._stuck_since = None
            now = time.time()
            if self._match_end_since is None:
                self._match_end_since = now
            if now - self._match_end_since >= self.match_end_timeout:
                # Play Again taps aren't advancing (button drifted / covered) -> escalate to OK,
                # which returns HOME, where the located Battle button re-queues reliably.
                self._log(f"[nav] MATCH_END stuck ~{self.match_end_timeout:.0f}s -> escalate: OK "
                          f"({self.results_ok[0]:.3f},{self.results_ok[1]:.3f})")
                self.controller.tap(*self.results_ok)
                self._match_end_since = now                     # re-arm
            else:
                pt, located = self._locate(frame, self.pa_tpl, self.pa_thr, self.play_again)
                self._log(f"[nav] MATCH_END -> Play Again {'(located)' if located else '(fixed)'} "
                          f"({pt[0]:.3f},{pt[1]:.3f})")
                self.controller.tap(*pt)
            time.sleep(self.menu_delay)
        else:  # UNKNOWN / QUEUING: normally just wait, but don't hang on an unrecognised popup
            self._match_end_since = None
            now = time.time()
            if self._stuck_since is None:
                self._stuck_since = now
            elif now - self._stuck_since >= self.stuck_timeout:
                self._log(f"[nav] stuck on {state.name} ~{self.stuck_timeout:.0f}s -> dismiss "
                          f"({self.stuck_tap[0]:.3f},{self.stuck_tap[1]:.3f})")
                self.controller.tap(*self.stuck_tap)
                self._stuck_since = now
                time.sleep(self.menu_delay)
            else:
                time.sleep(self.poll_dt)
