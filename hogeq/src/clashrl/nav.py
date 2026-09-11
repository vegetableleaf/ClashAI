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
  * Every action is logged (to data/nav/<label>_<ts>.log unless a log callable is supplied).
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
        self.results_ok_center = cfg.get("buttons", "results_ok_center", default=[0.5, 0.905])
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
        self._escalate_alt = True                        # alternate center-OK / bottom-right-OK on escalation
        # L67q NO-MATCH CEILING (HANDOFF 5cs.99 V). The owner's 8 h run lost 3 h 45 min (02:42-06:27) on the results
        # screen: a WINDOWS POPUP sat over the game, the frame still showed Play Again, the template was LOCATED,
        # and ~16,000 taps plus 2,059 OK escalations landed on the popup. No rule above can see that. So after
        # `recover_after_s` with no match: desktop screenshot, log the foreground window, force the game window to
        # the front and -- only if that worked -- press Escape; after `give_up_after_s`: set `give_up` (play.py
        # stops) and send a text-only Discord alert. 0 disables either.
        self.recover_after = float(cfg.get("nav", "recover_after_s", default=120.0))
        self.recover_every = float(cfg.get("nav", "recover_every_s", default=60.0))
        self.give_up_after = float(cfg.get("nav", "give_up_after_s", default=600.0))
        self.stall_shots_keep = int(cfg.get("nav", "stall_shots_keep", default=20))
        self._shot_dir = Path(cfg.path("data")) / "nav_stall"
        self._cfg = cfg
        self._off_match_since: Optional[float] = None
        self._last_recover: Optional[float] = None
        self._recovers = 0
        self.give_up = False
        self._now = time.time                            # injectable, so tests do not wait minutes
        self._sleep = time.sleep
        self._log = log or self._make_file_log(cfg, label)

    @staticmethod
    def _make_file_log(cfg, label: str) -> Callable[[str], None]:
        path = Path(cfg.path("data")) / "nav" / f"{label}_{datetime.now():%Y%m%d_%H%M%S}.log"
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
        self._escalate_alt = True
        self._off_match_since = None
        self._last_recover = None
        self._recovers = 0

    def _locate(self, frame, tpl, thr, fallback):
        pt = self.vision.locate(frame, tpl, thr) if tpl else None
        return (pt, True) if pt else (fallback, False)

    # -- L67q no-match ceiling ------------------------------------------------------------------------------
    def _ceiling(self, state) -> bool:
        """Recover or give up when no match has started for a long time. True = this call acted (skip the tap)."""
        now = self._now()
        if self._off_match_since is None:
            self._off_match_since = now
            return False
        off = now - self._off_match_since
        if self.give_up_after > 0 and off >= self.give_up_after and not self.give_up:
            shot = self._screenshot("giveup")
            fg, is_game = self._foreground()
            self.give_up = True
            self._log(f"[nav] NO MATCH for {off:.0f}s (state {state.name}) -> GIVING UP, stopping play. "
                      f"foreground {fg!r} (game: {is_game}), screenshot {shot}")
            self._alert(f"ClashBot play stopped: no match started for {off / 60:.0f} min (stuck on {state.name}). "
                        + ("The game window was in front." if is_game else
                           "Another window was in front of the game.")
                        + " A desktop screenshot is saved locally in data/nav_stall.")
            return True
        if self.recover_after > 0 and off >= self.recover_after and (
                self._last_recover is None or now - self._last_recover >= self.recover_every):
            self._last_recover = now
            self._recovers += 1
            shot = self._screenshot("recover")
            fg, is_game = self._foreground()
            focus = getattr(self.controller, "force_focus", None)
            focused = bool(focus()) if callable(focus) else False
            # Escape only when the GAME is in front (a key must never land in someone else's window), and never
            # on HOME, where Android back opens the exit dialog instead of leaving a screen.
            esc = focused and state != GameState.HOME
            if esc:
                self.controller.press_key("esc")
            self._log(f"[nav] NO MATCH for {off:.0f}s (state {state.name}) -> recover #{self._recovers}: "
                      f"foreground {fg!r} (game: {is_game}), force focus {'ok' if focused else 'FAILED'}, "
                      f"{'Escape sent' if esc else 'no Escape'}, screenshot {shot}")
            self._sleep(self.menu_delay)
            return True
        return False

    def _foreground(self) -> tuple:
        """(title of the foreground window, whether it is the game window)."""
        try:
            import ctypes
            u32 = ctypes.windll.user32
            h = u32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, buf, 256)
            hw = getattr(self.controller, "_hwnd", None)
            game = hw() if callable(hw) else None
            return buf.value, bool(game) and h == game
        except Exception:  # noqa: BLE001
            return "?", False

    def _screenshot(self, tag: str) -> str:
        """WHOLE-DESKTOP PNG -- not the game region, the point is to see what covers it. Newest N kept."""
        try:
            import mss
            import mss.tools
            self._shot_dir.mkdir(parents=True, exist_ok=True)
            path = self._shot_dir / f"{tag}_{datetime.now():%Y%m%d_%H%M%S}.png"
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[0])
                mss.tools.to_png(img.rgb, img.size, output=str(path))
            shots = sorted(self._shot_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
            for old in shots[:max(0, len(shots) - self.stall_shots_keep)]:
                try:
                    old.unlink()
                except OSError:
                    pass
            return str(path)
        except Exception as exc:  # noqa: BLE001
            return f"(failed: {type(exc).__name__})"

    def _alert(self, text: str) -> None:
        """Text-only Discord alert. No screenshot upload (the desktop can show anything); never logs the URL."""
        try:
            import json
            import urllib.request
            from .monitor import _load_webhook
            url = _load_webhook(self._cfg)
            if not url:
                self._log("[nav] no Discord webhook configured -- alert not sent")
                return
            req = urllib.request.Request(url, data=json.dumps({"content": text}).encode("utf-8"), method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "clashrl-nav/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            self._log("[nav] Discord alert sent")
        except Exception as exc:  # noqa: BLE001
            self._log(f"[nav] Discord alert failed ({type(exc).__name__})")

    def handle(self, frame, state) -> None:
        """Perform one navigation action for a non-IN_MATCH state."""
        if self._ceiling(state):
            return
        if state == GameState.HOME:
            self._match_end_since = self._stuck_since = None
            pt, located = self._locate(frame, self.home_tpl, self.home_thr, self.battle)
            self._log(f"[nav] HOME -> Battle {'(located)' if located else '(fixed)'} "
                      f"({pt[0]:.3f},{pt[1]:.3f})")
            self.controller.tap(*pt)
            self._sleep(self.menu_delay)
        elif state == GameState.MATCH_END:
            self._stuck_since = None
            now = self._now()
            if self._match_end_since is None:
                self._match_end_since = now
            if now - self._match_end_since >= self.match_end_timeout:
                # Play Again isn't advancing. Two results-screen variants: the normal one (OK is
                # bottom-right) and the "OK only, centered" one (Play Again removed). Alternate the tap
                # so whichever OK exists gets pressed -> returns HOME, where located Battle re-queues.
                tgt = self.results_ok_center if self._escalate_alt else self.results_ok
                self._escalate_alt = not self._escalate_alt
                self._log(f"[nav] MATCH_END stuck ~{self.match_end_timeout:.0f}s -> escalate: tap OK "
                          f"({tgt[0]:.3f},{tgt[1]:.3f})")
                self.controller.tap(*tgt)
                self._match_end_since = now                     # re-arm
            else:
                pt, located = self._locate(frame, self.pa_tpl, self.pa_thr, self.play_again)
                self._log(f"[nav] MATCH_END -> Play Again {'(located)' if located else '(fixed)'} "
                          f"({pt[0]:.3f},{pt[1]:.3f})")
                self.controller.tap(*pt)
            self._sleep(self.menu_delay)
        else:  # UNKNOWN / QUEUING: normally just wait, but don't hang on an unrecognised popup
            self._match_end_since = None
            now = self._now()
            if self._stuck_since is None:
                self._stuck_since = now
            elif now - self._stuck_since >= self.stuck_timeout:
                self._log(f"[nav] stuck on {state.name} ~{self.stuck_timeout:.0f}s -> dismiss "
                          f"({self.stuck_tap[0]:.3f},{self.stuck_tap[1]:.3f})")
                self.controller.tap(*self.stuck_tap)
                self._stuck_since = now
                self._sleep(self.menu_delay)
            else:
                self._sleep(self.poll_dt)
