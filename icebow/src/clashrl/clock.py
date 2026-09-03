"""Live 2x / 3x elixir-multiplier clock.

Clash Royale 1v1 runs SINGLE elixir for most of regulation, DOUBLE for the last 60s, and TRIPLE in
overtime. The icebow offense->defense phase machine keys off this (the offensive X-Bow must break
through by double elixir or it gives up and switches to a defensive X-Bow + rocket-cycle), so the
LIVE bot needs the current multiplier. It's read TWO ways and CROSS-CHECKED; the CLOCK is
AUTHORITATIVE -- on any disagreement the clock wins (elapsed time is monotonic and can't false-fire,
whereas a template match can), so the multiplier only ever RISES within a match:

  * TIME  -- elapsed since the match started. Needs NOTHING; works out of the box. Lags the real
    clock by however long IN_MATCH took to detect (~1-2s), which is fine for a coarse 2x/3x gate.
  * BADGE -- template-match the on-screen "x2" / "x3" indicator. OPTIONAL cross-check: drop
    ``templates/elixir_2x.png`` + ``templates/elixir_3x.png`` and it's checked against the clock
    (any crop scale -- matched multi-scale); a disagreement is logged but the CLOCK's value is used.

Usage: build one per env/play, ``reset()`` when a match starts (IN_MATCH first detected), then
``update(frame)`` each step and read ``multiplier`` (1/2/3).
"""
from __future__ import annotations

import time
from typing import Optional

import cv2


def badge_score(vision, frame, tmpl_name) -> float:
    """Best TM_CCOEFF_NORMED score of a badge template over the WORK-scaled frame, searched across a
    small range of template SCALES. matchTemplate is NOT scale-invariant, and the x2/x3 badge is
    usually cropped from a full-resolution replay frame while matching runs on the work-scale (~480px)
    frame -- so a single fixed-scale match misses it entirely. The work frame is always work_width
    wide, so the badge has a resolution-independent size there; the scale sweep aligns the template."""
    tmpl = vision._templates.get(tmpl_name) if tmpl_name else None
    if tmpl is None or frame is None:
        return 0.0
    work = vision._work(frame)
    fh, fw = work.shape[:2]
    th, tw = tmpl.shape[:2]
    best = 0.0
    for s in (0.45, 0.55, 0.65, 0.75, 0.85, 1.0, 1.15, 1.3):
        w2, h2 = int(round(tw * s)), int(round(th * s))
        if w2 < 6 or h2 < 6 or w2 > fw or h2 > fh:
            continue
        t = cv2.resize(tmpl, (w2, h2), interpolation=(cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR))
        best = max(best, float(cv2.matchTemplate(work, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


class ElixirClock:
    def __init__(self, cfg, vision):
        self.cfg = cfg
        self.vision = vision
        self.double_t = float(cfg.get("elixir", "double_time_s", default=120.0))
        self.triple_t = float(cfg.get("elixir", "triple_time_s", default=240.0))
        # OVERTIME START (2026-08-15). Regulation is 180 s; overtime's FIRST minute is still
        # DOUBLE elixir (triple only arrives at 240 s -- see the four-phase schedule in
        # sim/engine.elixir_rate), so the 3x badge cannot be used to detect that overtime has
        # begun: it is a minute late. The icebow phase machine flips offence -> defence here.
        self.ot_t = float(cfg.get("elixir", "overtime_time_s", default=180.0))
        self.x2_tpl = cfg.get("elixir", "x2_template", default="elixir_2x.png")
        self.x3_tpl = cfg.get("elixir", "x3_template", default="elixir_3x.png")
        self.badge_threshold = float(cfg.get("elixir", "badge_threshold", default=0.7))
        self._start = time.time()
        self._mult = 1
        self.badge_mult = 0            # last icon reading (0 = no badge / no template)
        self.disagreed = False         # last update: did the icon and the clock disagree?
        self._logged_mismatch = None   # de-dupe the disagreement log

    def reset(self, start: Optional[float] = None) -> None:
        """Call when a match STARTS (IN_MATCH first detected) to zero the clock."""
        self._start = time.time() if start is None else start
        self._mult = 1
        self.badge_mult = 0
        self.disagreed = False
        self._logged_mismatch = None

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
            if self.x3_tpl and badge_score(self.vision, frame, self.x3_tpl) >= self.badge_threshold:
                return 3
            if self.x2_tpl and badge_score(self.vision, frame, self.x2_tpl) >= self.badge_threshold:
                return 2
        except Exception:                       # a missing/oversized template must never break a match
            pass
        return 0

    def _badge_window(self, now: Optional[float] = None) -> bool:
        """Only cross-check the badge NEAR an expected transition. The badge NEVER decides the
        multiplier (the clock is authoritative), so its whole value is the calibration hint when the
        two disagree -- and they can only meaningfully disagree around a transition. Away from one,
        each check is up to 2 templates x 8 scales = 16 whole-frame matchTemplates for nothing:
        MEASURED at ~865 ms/step under training load, the single largest term in the live decision
        pipeline (log 2026-08-12, cadence item). elixir.badge_check_window_s = 0 disables the badge
        entirely; a very large value restores the old every-step behaviour."""
        win = float(self.cfg.get("elixir", "badge_check_window_s", default=20.0))
        if win <= 0.0:
            return False
        elapsed = (time.time() if now is None else now) - self._start
        return any(abs(elapsed - t) <= win for t in (self.double_t, self.triple_t))

    def update(self, frame=None, now: Optional[float] = None) -> int:
        """Refresh + return the current multiplier (1/2/3). The CLOCK (elapsed time) and the on-screen
        ICON are read independently and CROSS-CHECKED; on ANY disagreement the CLOCK wins -- elapsed
        time is monotonic and can't false-fire, whereas a template match can mis-hit or miss. A NEW
        mismatch is logged (a hint that the badge crop / time threshold needs a look). Since time is
        monotonic the multiplier only ever rises within a match. The badge read only runs inside
        `_badge_window` of a transition (elsewhere it is dead weight -- see that docstring)."""
        t = self._time_mult(now)
        b = self._badge_mult(frame) if self._badge_window(now) else 0
        self.badge_mult = b
        self.disagreed = bool(b and b != t)              # icon gave a reading AND it differs from the clock
        if self.disagreed and (t, b) != self._logged_mismatch:
            self._logged_mismatch = (t, b)
            print(f"[clock] icon reads x{b} but the clock reads x{t} -> using the clock (x{t})")
        self._mult = t                                   # the clock is authoritative on any disagreement
        return self._mult

    @property
    def overtime(self) -> bool:
        """Has the match reached OVERTIME? (elapsed >= elixir.overtime_time_s)"""
        return (time.time() - self._start) >= self.ot_t

    @property
    def overtime_s(self) -> float:
        """Seconds INTO overtime (0 before it). Drives the soft defensive ramp (env, HANDOFF §5bo)."""
        return max(0.0, (time.time() - self._start) - self.ot_t)

    @property
    def multiplier(self) -> int:
        return self._mult

    def elixir_rate(self) -> float:
        """Elixir generated per second at the current multiplier (base ~1 pip / 2.8s)."""
        base = float(self.cfg.get("elixir", "base_rate_per_s", default=1.0 / 2.8))
        return base * self._mult
