"""Per-unit HP from the health bar floating above a troop.

This used to guess where the bar was: it searched a thin band above the unit's box, sized
RELATIVE TO THE UNIT. Two things were wrong with that, both measured against KataCR's 11,735
hand-labelled bars:

  * Bars are a FIXED size -- median 0.098 of frame width, 0.020 of frame height, p10/p90
    0.092/0.126 wide. A skeleton's box is far narrower than its own bar, so a unit-relative
    search strip cannot contain it; a golem's is far wider, so the strip sweeps up its
    neighbours' bars. Size had to stop scaling with the unit.
  * The fill was looked for in GREEN. Clash Royale colours unit bars BY TEAM. Measured over
    2,501 labelled bars, median hue (OpenCV 0-179) is 100 -- blue -- for own units and 18 --
    red -- for enemy ones. Nothing is green, so the old reader would have returned None
    forever and looked merely "coarse" rather than broken.

Now the bar is DETECTED, by the 2-class model in runs/bars (see tools/detect/build_bars.py),
and this module only does the two things that remain: measure the fill inside a given bar
box, and decide which unit the bar belongs to.

MATCHING IS THE HARD PART, AND ITS LIMITS ARE KNOWN. A bar sits centred on its unit, just
above the sprite. Applying exactly that as a rule to KataCR's ground truth:

    79.4%  exactly one plausible owner
     2.5%  two or more -- genuinely ambiguous, reported as such rather than guessed
    18.1%  no plausible owner (the unit is off-taxonomy, or its box is missing)

So this yields HP for roughly four fifths of visible bars, and says so for the rest. It does
NOT yield HP for undamaged units: Clash Royale draws no bar until a unit takes damage, which
is a property of the game, not of this reader. `None` therefore means "no bar", which usually
means full health -- but not always, so it is not reported as full.

    frac = read_fill(frame, bar_box)                  # 0..1, or None if unreadable
    owner = match_bars(bar_boxes, unit_boxes)         # bar index -> unit index / None
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

Box = Tuple[float, float, float, float]      # normalized (x0, y0, x1, y1)

# --- matching windows, in ABSOLUTE frame fractions ---------------------------------------
# Both come from the measured distribution of bar-to-body offsets, widened to roughly p90.
# They are absolute on purpose -- see the module docstring for why unit-relative fails.
_MAX_DX = 0.025          # |bar centre x - unit centre x|
_GAP_LO, _GAP_HI = -0.005, 0.035     # unit's top edge minus bar's centre y

# --- fill measurement --------------------------------------------------------------------
# The spent part of a CR bar is NOT dark -- it is the same colour, duller. Measured column
# profiles step from V ~220 to V ~120, so any absolute threshold either takes the whole bar
# (read 66% of all bars as exactly full) or none of it. The threshold has to be derived per
# bar, from its own bright/dull plateaus.
_MIN_SPAN = 45           # p90-p10 of column V below this = one plateau = the bar is full
_MIN_COLS = 12           # narrower than this and the profile is too short to find a step
_SAT_MIN = 90            # used only by bar_team, for picking bar pixels out of the box
_VAL_MIN = 90


def read_fill(frame: np.ndarray, bar: Box) -> Optional[float]:
    """Filled fraction (0..1) of a DETECTED bar box, or None if it cannot be read.

    The detector boxes the whole bar widget, not just its filled part -- confirmed by the
    width distribution being near-constant (p10 0.092, p90 0.126 of frame width) while HP
    obviously is not.

    MEASURED FROM THE RIGHT, on purpose. The natural reading -- length of the lit run from
    the left -- collapsed to 0.00 on two thirds of bars, because a CR bar carries the unit's
    LEVEL BADGE at its left end (KataCR labels that separately as `bar-level`) and the badge
    breaks the run immediately. The spent part is always a contiguous block at the right end,
    so measuring the gap instead sidesteps the badge entirely.

    NOT VERIFIED AGAINST TRUE HP -- the dataset has no HP ground truth to score against. What
    is established is that the resulting distribution is physically sensible (continuous over
    0.12-1.00, median 0.77, nothing piled at zero), which the two rejected variants were not.
    """
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = bar
    px0, px1 = max(0, int(x0 * w)), min(w, int(x1 * w))
    py0, py1 = max(0, int(y0 * h)), min(h, int(y1 * h))
    if px1 - px0 < _MIN_COLS or py1 - py0 < 6:
        return None
    # middle rows only -- the widget's top and bottom rows are its dark outline
    a = (py1 - py0) // 3
    band = frame[py0 + a: py0 + max(a + 1, 2 * (py1 - py0) // 3), px0:px1]
    v = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)[..., 2].mean(0)[2:-2]
    if v.size < 8:
        return None
    lo, hi = np.percentile(v, 10), np.percentile(v, 90)
    if hi - lo < _MIN_SPAN:
        return 1.0                      # one plateau: nothing spent
    thr = (lo + hi) / 2
    empty = 0
    for val in v[::-1]:
        if val >= thr:
            break
        empty += 1
    return float(max(0.0, 1.0 - empty / v.size))


def bar_team(frame: np.ndarray, bar: Box) -> Optional[str]:
    """'mine' / 'enemy' from the bar's hue, or None if unreadable.

    Independent of the detector's own team fusion, so it can be fed in as evidence rather
    than silently agreeing with itself. Own bars measured at median hue 100 (blue), enemy at
    18 (red); the split at 60 sits in the empty gap between the two populations. Scored
    against KataCR's side column on 3,008 bars: 91.0%.

    UNIT BARS ONLY. Tower bars do NOT separate this way -- measured over 2,005 of them, own
    towers sit at median hue 27 and enemy towers at 52, with the two populations overlapping
    almost completely (36% vs 13% land inside the blue window). Calling this on a tower bar
    returns a confident answer that is barely better than a coin flip; on one test frame it
    called all four towers 'enemy'. The tower's side is already known from its fixed position,
    so callers should simply not ask.
    """
    h, w = frame.shape[:2]
    px0, px1 = max(0, int(bar[0] * w)), min(w, int(bar[2] * w))
    py0, py1 = max(0, int(bar[1] * h)), min(h, int(bar[3] * h))
    if px1 <= px0 or py1 <= py0:
        return None
    hsv = cv2.cvtColor(frame[py0:py1, px0:px1], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 1] >= _SAT_MIN) & (hsv[..., 2] >= _VAL_MIN)
    if int(m.sum()) < 20:
        return None
    hue = float(np.median(hsv[..., 0][m]))
    return "mine" if 60 <= hue <= 140 else "enemy"


def match_bars(bars: Sequence[Box], units: Sequence[Box]) -> Dict[int, Optional[int]]:
    """bar index -> unit index, or None when no single owner can be named.

    None covers BOTH failure modes on purpose -- no candidate and several candidates. A
    matcher that broke ties by picking the nearest would turn a 2.5% "don't know" into a
    ~1.3% silent error, and a silent error in a training label is worse than a gap.
    """
    out: Dict[int, Optional[int]] = {}
    for bi, (bx0, by0, bx1, by1) in enumerate(bars):
        bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
        hits = [ui for ui, (ux0, uy0, ux1, uy1) in enumerate(units)
                if abs((ux0 + ux1) / 2 - bcx) <= _MAX_DX
                and _GAP_LO <= uy0 - bcy <= _GAP_HI]
        out[bi] = hits[0] if len(hits) == 1 else None
    return out


def annotate(frame: np.ndarray, bars: Sequence[Box],
             units: Sequence[Box] = ()) -> np.ndarray:
    """Draw detected bars with their fill %, and the unit each was matched to."""
    out = frame.copy()
    h, w = out.shape[:2]
    owner = match_bars(bars, units) if units else {}
    for bi, b in enumerate(bars):
        p0 = (int(b[0] * w), int(b[1] * h))
        p1 = (int(b[2] * w), int(b[3] * h))
        cv2.rectangle(out, p0, p1, (0, 255, 255), 1)
        f = read_fill(frame, b)
        cv2.putText(out, "--" if f is None else f"{int(round(f * 100))}%",
                    (p0[0], max(10, p0[1] - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        ui = owner.get(bi)
        if ui is not None:
            u = units[ui]
            cv2.line(out, ((p0[0] + p1[0]) // 2, p1[1]),
                     (int((u[0] + u[2]) / 2 * w), int(u[1] * h)), (0, 255, 255), 1)
    return out


def hp_for_units(frame: np.ndarray, bars: Sequence[Box],
                 units: Sequence[Box]) -> List[Optional[float]]:
    """Per-unit fill fraction, aligned to ``units``. None = no bar matched to that unit,
    which for a healthy unit is the normal case (CR draws no bar until damage)."""
    res: List[Optional[float]] = [None] * len(units)
    for bi, ui in match_bars(bars, units).items():
        if ui is None:
            continue
        f = read_fill(frame, bars[bi])
        if f is not None:
            res[ui] = f
    return res
