"""Live 2x / 3x elixir-multiplier clock.

Clash Royale 1v1 runs SINGLE elixir for most of regulation, DOUBLE for the last 60s, and TRIPLE in
overtime. The icebow offense->defense phase machine keys off this (the offensive X-Bow must break
through by double elixir or it gives up and switches to a defensive X-Bow + rocket-cycle), so the
LIVE bot needs the current multiplier. It's read TWO ways and LATCHED to the max -- the multiplier
only ever RISES within a match, so latching is robust to badge occlusion + detection lag:

  * TIME  -- elapsed since the match started. Needs NOTHING; works out of the box. Lags the real
    clock by however long IN_MATCH took to detect (~1-2s), which is fine for a coarse 2x/3x gate.
  * BADGE -- template-match the on-screen "x2" / "x3" indicator. Screen-accurate but OPTIONAL:
    drop ``templates/elixir_2x.png`` + ``templates/elixir_3x.png`` and it refines the time reading.

Usage: build one per env/play, ``reset()`` when a match starts (IN_MATCH first detected), then
``update(frame)`` each step and read ``multiplier`` (1/2/3).
"""
from __future__ import annotations

import time
from typing import Optional


class ElixirClock:
    def __init__(self, cfg, vision):
        self.cfg = cfg
        self.vision = vision
        self.double_t = float(cfg.get("elixir", "double_time_s", default=120.0))
        self.triple_t = float(cfg.get("elixir", "triple_time_s", default=180.0))
        self.x2_tpl = cfg.get("elixir", "x2_template", default="elixir_2x.png")
        self.x3_tpl = cfg.get("elixir", "x3_template", default="elixir_3x.png")
        self.badge_threshold = float(cfg.get("elixir", "badge_threshold", default=0.7))
        self._start = time.time()
        self._mult = 1

    def reset(self, start: Optional[float] = None) -> None:
        """Call when a match STARTS (IN_MATCH first detected) to zero the clock."""
        self._start = time.time() if start is None else start
        self._mult = 1

    def _time_mult(self, now: Optional[float] = None) -> int:
        elapsed = (time.time() if now is None else now) - self._start
        if elapsed >= self.triple_t:
            return 3
        if elapsed >= self.double_t:
            return 2
        return 1

    def _badge_mult(self, frame) -> int:
        """3 if the on-screen x3 badge is present, 2 for x2, else 0 (no badge visible / no template)."""
        if frame is None:
            return 0
        try:
            if self.x3_tpl and self.vision._find(frame, self.x3_tpl, self.badge_threshold):
                return 3
            if self.x2_tpl and self.vision._find(frame, self.x2_tpl, self.badge_threshold):
                return 2
        except Exception:                       # a missing/oversized template must never break a match
            pass
        return 0

    def update(self, frame=None, now: Optional[float] = None) -> int:
        """Refresh + return the current multiplier (1/2/3). LATCHES: never decreases within a match."""
        self._mult = max(self._mult, self._time_mult(now), self._badge_mult(frame))
        return self._mult

    @property
    def multiplier(self) -> int:
        return self._mult

    def elixir_rate(self) -> float:
        """Elixir generated per second at the current multiplier (base ~1 pip / 2.8s)."""
        base = float(self.cfg.get("elixir", "base_rate_per_s", default=1.0 / 2.8))
        return base * self._mult
