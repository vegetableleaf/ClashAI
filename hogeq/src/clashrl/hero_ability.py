"""Hero Ice Wizard ability (Frosty Fella) for live play -- L67ag, owner rulings 2026-09-12 (HANDOFF 5cs.99 AL/AM).

Three pieces, all perception-light and outside the model's action space (adding an action would silently change the
checkpoint's width):

* ``ability_button_state`` -- the button's own pixels say whether the ability can be used. The detector does NOT see
  the hero reliably (run17: mostly unboxed), so availability cannot come from a detection the way hogeq's champion
  path does. Run17 clips: READY = a blue disc (blue fraction ~0.36), GREY = unaffordable (~0.85-0.98 grey), ABSENT =
  no hero on the board (both ~0). The classifier matched every hand-labelled strip tile.
* ``UIMaskedDetector`` -- D1. The board detector boxes the button as an ENEMY ``earthquake`` (0.91-0.95; red box in
  ~30% of sampled frames where the button shows). Detections centred on the button are dropped while it is on screen.
* ``frosty_fella_decision`` -- H3. No pro data exists for this hero yet (every crawl ends 2026-09-06), so the rule
  encodes the situations where a 2.5-tile freeze plus a 321-HP snowman decoy pays: an enemy win condition about to
  reach one of our buildings/towers, a push stacked inside the radius, or troops on our X-Bow. The game spawns the
  snowman behind the Ice Wizard's CURRENT target, so a candidate must be within the hero's reach.

Distances are in TILES with separate x / y scales: the frame is not isotropic. From the config tower anchors, the
princess towers are 0.50 apart in x for 11 tiles and 0.41 apart in y for 19 tiles (standard arena layout).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

TILE_X = 0.50 / 11.0          # frame-width units per tile  (princess tower centres 3.5 -> 14.5)
TILE_Y = 0.41 / 19.0          # frame-height units per tile (princess tower centres 6.5 -> 25.5)


def tiles_between(a, b, tile=(TILE_X, TILE_Y)) -> float:
    return math.hypot((float(a[0]) - float(b[0])) / tile[0], (float(a[1]) - float(b[1])) / tile[1])


def ability_button_state(frame, center=(0.909, 0.765), radius=0.045, blue_min=0.30, grey_min=0.35):
    """('ready' | 'grey' | 'absent', blue_fraction, grey_fraction) inside the button disc.

    ``radius`` is in frame-WIDTH units (the disc is round on screen)."""
    if frame is None:
        return "absent", 0.0, 0.0
    h, w = frame.shape[:2]
    r = max(2, int(float(radius) * w))
    cx, cy = int(float(center[0]) * w), int(float(center[1]) * h)
    x0, x1, y0, y1 = max(0, cx - r), min(w, cx + r), max(0, cy - r), min(h, cy + r)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return "absent", 0.0, 0.0
    yy, xx = np.mgrid[y0:y1, x0:x1]
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0][inside].astype(int), hsv[..., 1][inside].astype(int), hsv[..., 2][inside].astype(int)
    if H.size == 0:
        return "absent", 0.0, 0.0
    blue = float(((H >= 90) & (H <= 125) & (S >= 110) & (V >= 120)).mean())
    grey = float(((S <= 40) & (V >= 110)).mean())
    if blue >= float(blue_min):
        return "ready", blue, grey
    if grey >= float(grey_min):
        return "grey", blue, grey
    return "absent", blue, grey


class UIMaskedDetector:
    """Wraps a board detector; drops detections centred inside an on-screen UI disc while that UI is showing.

    ``discs`` = [(cx, cy, radius_in_width_units)]. The first disc is also the button whose state gates the mask, so a
    real unit walking through that corner is only hidden while the button covers it anyway."""

    def __init__(self, detector, discs, state_radius=0.045, blue_min=0.30, grey_min=0.35):
        self._det = detector
        self.discs = [tuple(map(float, d)) for d in discs]
        self._state_r, self._blue_min, self._grey_min = float(state_radius), float(blue_min), float(grey_min)
        self.masked = 0

    def __getattr__(self, name):
        return getattr(self._det, name)

    def detect(self, frame, conf: float = 0.3):
        dets = self._det.detect(frame, conf=conf)
        if frame is None or not self.discs or not dets:
            return dets
        st, _, _ = ability_button_state(frame, self.discs[0][:2], self._state_r, self._blue_min, self._grey_min)
        if st == "absent":
            return dets
        h, w = frame.shape[:2]
        keep = []
        for d in dets:
            hit = False
            for bx, by, br in self.discs:
                if math.hypot(float(d.cx) - bx, (float(d.cy) - by) * h / w) <= br:
                    hit = True
                    break
            if hit:
                self.masked += 1
            else:
                keep.append(d)
        return keep


def frosty_fella_decision(enemies, buildings, towers, hero_xy, *, elixir, is_wincon, xbows=(),
                          cost=2.0, radius=2.5, wincon_reach=4.0, cluster_min=3, guard=3.0,
                          hero_reach=7.0, half_y=0.42, tile=(TILE_X, TILE_Y)):
    """Should the hero's ability be pressed now? None, or {reason, center, n, wincon}.

    enemies   [(x, y, base)] frame-normalised enemy tracks (air and ground: the freeze takes both)
    buildings [(x, y)] our X-Bow / Tesla;  towers [(x, y)] our ALIVE towers;  xbows [(x, y)] our X-Bows
    hero_xy   best estimate of the hero (an ally detection, else his deploy point); None = unknown (no reach test)

    Cases, most valuable first: ``wincon_at_building`` (an enemy win condition on our half within ``wincon_reach``
    tiles of a building or tower), ``xbow_guard`` (>= 2 enemies within ``guard`` tiles of our X-Bow), ``stacked_push``
    (>= ``cluster_min`` enemies inside the freeze radius on our half). A lone non-win-condition unit never qualifies.
    """
    if float(elixir) + 1e-6 < float(cost):
        return None
    ens = [(float(e[0]), float(e[1]), (e[2] if len(e) > 2 else None)) for e in enemies or ()]
    if not ens:
        return None

    def n_within(c):
        return sum(1 for e in ens if tiles_between(e, c, tile) <= radius)

    def reachable(c):
        return hero_xy is None or tiles_between(hero_xy, c, tile) <= hero_reach

    anchors = [tuple(b) for b in (buildings or ())] + [tuple(t) for t in (towers or ())]
    best = None
    for e in ens:
        if e[1] < half_y or not e[2] or not is_wincon(e[2]) or not reachable(e):
            continue
        near = min((tiles_between(e, a, tile) for a in anchors), default=float("inf"))
        if near <= wincon_reach:
            n = n_within(e)
            if best is None or (n, -near) > (best["n"], -best["_near"]):
                best = {"reason": "wincon_at_building", "center": (e[0], e[1]), "n": n, "wincon": e[2], "_near": near}
    if best is not None:
        best.pop("_near")
        return best
    for xb in xbows or ():
        close = [e for e in ens if tiles_between(e, xb, tile) <= guard and reachable(e)]
        if len(close) >= 2:
            c = max(close, key=n_within)
            return {"reason": "xbow_guard", "center": (c[0], c[1]), "n": n_within(c), "wincon": None}
    cands = [e for e in ens if e[1] >= half_y and reachable(e)]
    if cands:
        c = max(cands, key=n_within)
        n = n_within(c)
        if n >= int(cluster_min):
            return {"reason": "stacked_push", "center": (c[0], c[1]), "n": n, "wincon": None}
    return None
