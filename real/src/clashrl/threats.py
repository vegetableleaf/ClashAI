"""Enemy-threat perception for reactive / anticipatory play.

The policy already sees a (heavily downscaled) arena image, but the small image
loses the cues that drive good DEFENCE: the *type* of the incoming push. This
module reads the enemy threat off a full-resolution frame and turns it into:

* a fixed-length, normalised feature VECTOR (``Threat.vector()``) that can be fed
  to the policy alongside the hand / next-card / elixir inputs, and
* a human-readable classification (colour / size / count / lane / depth / speed /
  projectile) used by the ``analyze`` replay miner and by reward shaping.

How it detects things
---------------------
* Enemy units carry the red team tint (red HP bar + aura), so the enemy mask
  reuses :func:`reward._red_mask` with the enemy tower boxes blanked (static towers
  are red too). Connected components over that mask give the ENTITY COUNT (a swarm
  is many small blobs, one tank is a single big blob) and the LARGEST unit size.
* Intrinsic troop COLOUR is sampled with saturated colour masks -- most usefully
  GREEN, because Goblins are green and this deck plays no green cards, so green in
  the arena is a clean "goblins" signal (Goblin Barrel / Goblin Gang / Spear Gobs).
* LANE (left/centre/right) and DEPTH (how far the push has advanced down YOUR half
  toward your king) come from where the enemy mass sits.
* APPROACH SPEED and a best-effort PROJECTILE-IN-FLIGHT detector (a small, fast
  blob arcing toward one of your towers -- e.g. a thrown Goblin Barrel) need frame
  history, so feed frames in order through :class:`ThreatTracker`.

Everything here is a coarse pixel proxy -- tune the thresholds (module constants,
a few overridable via ``env.threat_*``) with ``verify --threats``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .reward import _anchors, _arena_region

# Length of the feature vector fed to the policy (keep in sync with vector()).
THREAT_DIM = 14

# --- intrinsic troop colour buckets (OpenCV HSV: H 0-179) -----------------
# Saturated buckets so background grass / tower foliage doesn't count as a unit.
_GREEN_LO, _GREEN_HI = (34, 95, 70), (80, 255, 255)      # Goblins (a bright yellow-green)
_PURPLE_LO, _PURPLE_HI = (130, 110, 80), (158, 255, 255)  # e.g. Witch / Bats tint (strict)

# Enemy units read as SATURATED red (red HP bar + red aura). A stricter red than the
# tower detector's -- the enemy-territory ground tint + arena border are dull/pale red
# and must NOT count as troops.
_TROOP_RED_LO1, _TROOP_RED_HI1 = (0, 150, 110), (8, 255, 255)
_TROOP_RED_LO2, _TROOP_RED_HI2 = (169, 150, 110), (179, 255, 255)

# --- geometry (normalized) ------------------------------------------------
# The ENGAGEMENT ZONE spans the midfield + YOUR HALF -- from below the enemy back line
# (whose tower red + foliage would swamp the read) down to just above your king, inside
# the arena border. Including the midfield gives early warning as a push forms/crosses;
# ``my_side_mass`` (below the river) is the immediate part. The enemy back line + your
# towers are blanked, and the saturated-red mask rejects arena tints, so a real push
# stands out over the tan floor. A thrown projectile is tracked separately by motion.
_ENGAGE_TOP = 0.32       # below the enemy back line (midfield -> early warning)
_ENGAGE_BOT = 0.74       # just above your king base (skip the red arena border below it)
_ENGAGE_X0, _ENGAGE_X1 = 0.12, 0.88   # inside the arena border (skip the red/lava frame)
_RIVER_Y = 0.52          # troops below this are in YOUR half (the immediate threat)
_KING_Y = 0.74           # ~your king row -- the deepest a push gets before it's on the king

# --- classification thresholds (raw fractions unless noted) ---------------
_QUIET = 0.003           # arena red frac below this => no real threat on the board (baseline ~0.0015)
_SWARM_COUNT = 3         # >= this many enemy blobs => a swarm (goblins/skeletons)
_SINGLE_BLOB = 0.018     # largest-blob frac above this => a big single unit (tank)
_COLOR_MIN = 0.005       # green/purple frac above this => that colour is present (a real unit, not a tint)
_FAST_DEPTH = 0.22       # advance of >= this much depth/second => a fast push

# --- feature-vector gains (raw frac -> ~0..1) -----------------------------
_MASS_GAIN = 40.0
_BLOB_GAIN = 12.0
_COLOR_GAIN = 120.0
_SPEED_NORM = 0.5

# --- projectile detector --------------------------------------------------
_PROJ_DIFF = 26          # per-pixel frame-diff threshold (motion)
_PROJ_AMIN = 12          # min moving-blob area (px) to be a projectile
_PROJ_AMAX = 900         # max area -- above this it's a troop push / spell flash, not a barrel
_PROJ_MATCH_R = 0.10     # normalized radius to link a mover to a track between frames
_PROJ_MIN_SPEED = 1.1    # normalized speed (screens/sec) a track must average to be "in flight"
_PROJ_MIN_PTS = 3        # frames a track must persist (a real arc, not one-frame flicker)
_PROJ_STRAIGHT = 0.75    # net displacement / path length -- a clean arc/line, not jitter
_PROJ_TRACK_AGE = 0.35   # drop a track not extended within this many seconds
_PROJ_AIM = 0.11         # a projected trajectory passing within this of a tower => "toward tower"


@dataclass
class Projectile:
    """A small fast object in flight (best-effort; e.g. a thrown Goblin Barrel)."""
    x: float                     # normalized centroid
    y: float
    vx: float                    # normalized velocity (screens / second)
    vy: float
    speed: float
    toward_tower: bool
    target: Optional[str]        # nearest tower on its path (e.g. "M1"), or None


@dataclass
class Threat:
    """Enemy threat on the board at one instant (raw, normalized measurements)."""
    mass: float = 0.0                                   # enemy red frac over the arena
    my_side_mass: float = 0.0                           # enemy red frac in YOUR half
    largest_blob: float = 0.0                           # largest enemy blob / arena area
    count: int = 0                                      # number of distinct enemy blobs
    green: float = 0.0                                  # green (goblin) frac over the arena
    purple: float = 0.0                                 # purple frac over the arena
    depth: float = 0.0                                  # 0 at the river .. 1 at your king
    lanes: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # enemy mass in L/C/R of your half
    speed: float = 0.0                                  # advance speed (Δdepth / second)
    centroid: Optional[Tuple[float, float]] = None      # enemy mass centroid (nx, ny)
    proj: Optional[Projectile] = None

    # ---- readable classification (for analysis + reward shaping) ----------
    def active(self) -> bool:
        return self.mass >= _QUIET or self.proj is not None

    def size_label(self) -> str:
        if self.mass < _QUIET:
            return "none"
        if self.count >= _SWARM_COUNT and self.largest_blob < _SINGLE_BLOB:
            return "swarm"
        if self.largest_blob >= _SINGLE_BLOB:
            return "single_big"
        return "small"

    def color_label(self) -> str:
        if max(self.green, self.purple) < _COLOR_MIN:
            return "neutral"
        return "green" if self.green >= self.purple else "purple"

    def lane_label(self) -> str:
        if self.mass < _QUIET:
            return "none"
        i = int(np.argmax(self.lanes))
        return ("left", "center", "right")[i]

    def speed_label(self) -> str:
        if self.mass < _QUIET:
            return "none"
        return "fast" if self.speed >= _FAST_DEPTH else "slow"

    def type_label(self) -> str:
        """Compact key for aggregation, e.g. 'green-swarm-left' / 'single_big-right'."""
        if self.proj is not None:
            return "projectile-green" if self.green >= _COLOR_MIN else "projectile"
        if not self.active():
            return "quiet"
        color = self.color_label()
        prefix = f"{color}-" if color != "neutral" else ""
        return f"{prefix}{self.size_label()}-{self.lane_label()}"

    # ---- policy feature vector -------------------------------------------
    def vector(self) -> np.ndarray:
        def g(x: float, gain: float) -> float:
            return float(min(1.0, max(0.0, x * gain)))
        p = self.proj
        return np.asarray([
            g(self.mass, _MASS_GAIN),
            g(self.my_side_mass, _MASS_GAIN),
            g(self.largest_blob, _BLOB_GAIN),
            min(self.count, 12) / 12.0,
            g(self.green, _COLOR_GAIN),
            g(self.purple, _COLOR_GAIN),
            self.depth,
            g(self.lanes[0], _MASS_GAIN),
            g(self.lanes[1], _MASS_GAIN),
            g(self.lanes[2], _MASS_GAIN),
            min(1.0, self.speed / _SPEED_NORM) if self.speed > 0 else 0.0,
            1.0 if p is not None else 0.0,
            p.x if p is not None else 0.5,
            1.0 if (p is not None and p.toward_tower) else 0.0,
        ], dtype=np.float32)

    @staticmethod
    def zeros() -> np.ndarray:
        v = np.zeros(THREAT_DIM, dtype=np.float32)
        v[12] = 0.5      # projectile-x defaults to centre when unknown
        return v


def _troop_red_mask(hsv: np.ndarray) -> np.ndarray:
    """Saturated-red mask for enemy units (HP bars + red tint), not the pale ground tint."""
    m1 = cv2.inRange(hsv, _TROOP_RED_LO1, _TROOP_RED_HI1)
    m2 = cv2.inRange(hsv, _TROOP_RED_LO2, _TROOP_RED_HI2)
    return cv2.bitwise_or(m1, m2)


def _engage_bbox(frame: np.ndarray) -> Tuple[int, int, int, int]:
    h, w = frame.shape[:2]
    return (int(_ENGAGE_X0 * w), int(_ENGAGE_TOP * h),
            int(_ENGAGE_X1 * w), int(_ENGAGE_BOT * h))


def _blank_and_clip(mask: np.ndarray, frame: np.ndarray, cfg=None) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Blank YOUR tower boxes (their trim / effects aren't an enemy threat) and clip the
    mask to the engagement zone; return (mask, bbox_px). Shared by the red + colour masks.
    """
    h, w = frame.shape[:2]
    mine_a, _, _ = _anchors(cfg)
    for nx, ny in mine_a:
        x0, x1 = int((nx - 0.07) * w), int((nx + 0.07) * w)
        y0, y1 = int((ny - 0.06) * h), int((ny + 0.06) * h)
        mask[max(0, y0):y1, max(0, x0):x1] = 0
    X0, Y0, X1, Y1 = _engage_bbox(frame)
    out = np.zeros_like(mask)
    out[Y0:Y1, X0:X1] = mask[Y0:Y1, X0:X1]
    return out, (X0, Y0, X1, Y1)


def _enemy_mask(frame: np.ndarray, cfg=None) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Saturated enemy-red mask over the ENGAGEMENT ZONE (zero elsewhere), plus that zone's
    bbox in pixels. The zone keeps the enemy back line + arena border out and YOUR towers
    are blanked, so blob stats only see an actual incoming push.
    """
    return _blank_and_clip(_troop_red_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)), frame, cfg)


def _color_frac(frame: np.ndarray, cfg, lo, hi) -> float:
    """Fraction of the engagement zone matching a colour (your towers blanked)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask, (X0, Y0, X1, Y1) = _blank_and_clip(cv2.inRange(hsv, lo, hi), frame, cfg)
    return float(mask[Y0:Y1, X0:X1].mean()) / 255.0


def read_threat(frame: np.ndarray, cfg=None) -> Threat:
    """One-shot threat read (no motion: speed=0, no projectile). Use ThreatTracker
    when you have frames in order and want approach speed + projectile detection."""
    return ThreatTracker(cfg).update(frame, t=None)


def read_threat_window(cap, fi: int, times, cfg=None, window: int = 8):
    """Run a fresh ThreatTracker over frames [fi-window, fi] of an open cv2.VideoCapture
    and return (Threat at fi, frame at fi). The short run gives the tracker the history it
    needs for approach speed + projectile detection. Used by the labeler so the dataset
    carries the same threat vector the live env will feed the policy. Returns (Threat(), None)
    if the frame can't be read.
    """
    tk = ThreatTracker(cfg)
    start = max(0, fi - window)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    thr = Threat()
    frame = None
    for k in range(start, fi + 1):
        ok, f = cap.read()
        if not ok:
            break
        frame = f
        t = times[k] if k < len(times) else k / 12.0
        thr = tk.update(f, t)
    return thr, frame


class ThreatTracker:
    """Stateful threat reader: feed frames in order to get approach speed + a
    best-effort projectile-in-flight detector. Reset per match."""

    def __init__(self, cfg=None):
        self.cfg = cfg
        _, self._enemy_a, _ = _anchors(cfg)
        self._mine_a, _, _ = _anchors(cfg)
        self.reset()

    def reset(self) -> None:
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_t: Optional[float] = None
        self._prev_depth: float = 0.0
        self._tracks: List[dict] = []      # motion tracks: {pts: [(t,nx,ny)...], last: t}

    # ---- projectile helpers ----------------------------------------------
    def _toward_tower(self, x, y, vx, vy) -> Tuple[bool, Optional[str]]:
        """Does the ray from (x,y) along (vx,vy) pass near a tower within ~0.35 ahead?"""
        speed = math.hypot(vx, vy)
        if speed < 1e-6:
            return False, None
        ux, uy = vx / speed, vy / speed
        best = None
        best_d = _PROJ_AIM
        towers = ([(f"M{i+1}", a) for i, a in enumerate(self._mine_a)]
                  + [(f"E{i+1}", a) for i, a in enumerate(self._enemy_a)])
        for label, (tx, ty) in towers:
            # distance from the tower to the forward ray (project onto the heading)
            proj = (tx - x) * ux + (ty - y) * uy
            if proj <= 0 or proj > 0.5:                 # behind, or too far ahead
                continue
            px, py = x + ux * proj, y + uy * proj
            d = math.hypot(tx - px, ty - py)
            if d < best_d:
                best_d, best = d, label
        return (best is not None), best

    def _detect_projectile(self, gray, t, dt) -> Optional[Projectile]:
        """Track small fast movers across frames; a projectile is one that persists for
        several frames moving in a consistent (near-straight) direction, fast, toward a
        tower. Multi-frame tracking is what separates a thrown barrel/arrows from the
        constant one-frame flicker of troop animation + HP bars."""
        h, w = gray.shape[:2]
        diff = cv2.absdiff(gray, self._prev_gray)
        dmask = cv2.threshold(diff, _PROJ_DIFF, 255, cv2.THRESH_BINARY)[1]
        dmask = cv2.morphologyEx(dmask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, _, stats, cents = cv2.connectedComponentsWithStats(dmask, connectivity=8)
        ax0, ay0, ax1, ay1 = _arena_region(self.cfg)
        movers: List[Tuple[float, float]] = []
        for i in range(1, n):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if not (_PROJ_AMIN <= area <= _PROJ_AMAX):
                continue
            nx, ny = cents[i][0] / w, cents[i][1] / h
            if ax0 <= nx <= ax1 and ay0 <= ny <= ay1:
                movers.append((nx, ny))
        # link movers to existing tracks (nearest within radius), else start new tracks
        used = set()
        for tr in self._tracks:
            _, lx, ly = tr["pts"][-1]
            best_j, best_d = -1, _PROJ_MATCH_R
            for j, (nx, ny) in enumerate(movers):
                if j in used:
                    continue
                d = math.hypot(nx - lx, ny - ly)
                if d < best_d:
                    best_j, best_d = j, d
            if best_j >= 0:
                nx, ny = movers[best_j]
                tr["pts"].append((t, nx, ny))
                tr["pts"] = tr["pts"][-6:]
                tr["last"] = t
                used.add(best_j)
        for j, (nx, ny) in enumerate(movers):
            if j not in used:
                self._tracks.append({"pts": [(t, nx, ny)], "last": t})
        self._tracks = [tr for tr in self._tracks if t - tr["last"] <= _PROJ_TRACK_AGE]
        # pick the fastest track that looks like a clean fast arc toward a tower
        best: Optional[Projectile] = None
        for tr in self._tracks:
            pts = tr["pts"]
            if len(pts) < _PROJ_MIN_PTS:
                continue
            (t0, x0, y0), (t1, x1, y1) = pts[0], pts[-1]
            span = t1 - t0
            if span <= 1e-3:
                continue
            vx, vy = (x1 - x0) / span, (y1 - y0) / span
            speed = math.hypot(vx, vy)
            if speed < _PROJ_MIN_SPEED:
                continue
            path = sum(math.hypot(pts[k + 1][1] - pts[k][1], pts[k + 1][2] - pts[k][2])
                       for k in range(len(pts) - 1))
            net = math.hypot(x1 - x0, y1 - y0)
            if path <= 1e-6 or net / path < _PROJ_STRAIGHT:
                continue
            toward, target = self._toward_tower(x1, y1, vx, vy)
            if best is None or speed > best.speed:
                best = Projectile(x1, y1, vx, vy, speed, toward, target)
        return best

    def update(self, frame: np.ndarray, t: Optional[float]) -> Threat:
        h, w = frame.shape[:2]
        mask, (X0, Y0, X1, Y1) = _enemy_mask(frame, self.cfg)
        arena_area = max(1, (X1 - X0) * (Y1 - Y0))
        thr = Threat()
        thr.mass = float(mask[Y0:Y1, X0:X1].mean()) / 255.0 if arena_area else 0.0
        thr.green = _color_frac(frame, self.cfg, _GREEN_LO, _GREEN_HI)
        thr.purple = _color_frac(frame, self.cfg, _PURPLE_LO, _PURPLE_HI)

        # blob stats (entity count + biggest unit)
        clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, _, stats, cents = cv2.connectedComponentsWithStats(clean, connectivity=8)
        blobs = [(int(stats[i, cv2.CC_STAT_AREA]), cents[i]) for i in range(1, n)
                 if stats[i, cv2.CC_STAT_AREA] >= 18]
        thr.count = len(blobs)
        if blobs:
            thr.largest_blob = max(a for a, _ in blobs) / float(arena_area)
            wsum = sum(a for a, _ in blobs)
            cx = sum(a * c[0] for a, c in blobs) / wsum / w
            cy = sum(a * c[1] for a, c in blobs) / wsum / h
            thr.centroid = (cx, cy)

        # YOUR half: immediate mass + depth; lanes span the whole zone (midfield too)
        river_px = int(_RIVER_Y * h)
        zone = mask[Y0:Y1, X0:X1]
        my_half = mask[river_px:Y1, X0:X1]
        thr.my_side_mass = float(my_half.mean()) / 255.0 if my_half.size else 0.0
        if zone.size:
            third = max(1, zone.shape[1] // 3)
            lanes = [zone[:, :third], zone[:, third:2 * third], zone[:, 2 * third:]]
            thr.lanes = tuple(float(l.mean()) / 255.0 for l in lanes)  # type: ignore
        if my_half.size:
            rows = (my_half > 0).mean(1)
            hits = np.where(rows >= 0.02)[0]
            if len(hits):
                deepest_y = _RIVER_Y + (hits.max() / max(1, my_half.shape[0])) * (_ENGAGE_BOT - _RIVER_Y)
                thr.depth = float(min(1.0, max(0.0, (deepest_y - _RIVER_Y) / (_KING_Y - _RIVER_Y))))

        # motion: approach speed + projectile (needs a previous frame + dt)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is not None and t is not None and self._prev_t is not None:
            dt = t - self._prev_t
            if dt > 1e-3:
                thr.speed = max(0.0, (thr.depth - self._prev_depth) / dt)
                thr.proj = self._detect_projectile(gray, t, dt)
        self._prev_gray, self._prev_t, self._prev_depth = gray, t, thr.depth
        return thr


def ay_bottom(cfg=None) -> float:
    """Bottom of the engagement zone (normalized y) -- the deepest a troop is tracked."""
    return _ENGAGE_BOT


def annotate(frame: np.ndarray, thr: Threat, cfg=None) -> np.ndarray:
    """Draw the threat read on a copy of the frame (for verify --threats / debugging)."""
    out = frame.copy()
    h, w = out.shape[:2]
    mask, (X0, Y0, X1, Y1) = _enemy_mask(frame, cfg)
    # tint enemy mask
    red = np.zeros_like(out)
    red[..., 2] = mask
    out = cv2.addWeighted(out, 1.0, red, 0.4, 0)
    # arena + river + king lines
    cv2.rectangle(out, (X0, Y0), (X1, Y1), (90, 90, 90), 1)
    cv2.line(out, (X0, int(_RIVER_Y * h)), (X1, int(_RIVER_Y * h)), (255, 200, 0), 1)
    for i in (1, 2):
        x = X0 + (X1 - X0) * i // 3
        cv2.line(out, (x, int(_RIVER_Y * h)), (x, Y1), (60, 120, 60), 1)
    if thr.centroid:
        cx, cy = int(thr.centroid[0] * w), int(thr.centroid[1] * h)
        cv2.drawMarker(out, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
    if thr.proj is not None:
        p = thr.proj
        px, py = int(p.x * w), int(p.y * h)
        ex, ey = int((p.x + p.vx * 0.15) * w), int((p.y + p.vy * 0.15) * h)
        cv2.arrowedLine(out, (px, py), (ex, ey), (255, 0, 255), 2, tipLength=0.3)
        cv2.putText(out, f"PROJ->{p.target or '?'}", (px + 6, py),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
    cv2.putText(out, thr.type_label(), (X0 + 4, Y0 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(out, f"mass{thr.mass:.3f} big{thr.largest_blob:.3f} n{thr.count} "
                     f"grn{thr.green:.3f} dep{thr.depth:.2f} spd{thr.speed:.2f}",
                (X0 + 4, Y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
    return out
