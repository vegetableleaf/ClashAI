"""Reward signals for RL fine-tuning.

Two parts:

* **Terminal reward** (robust): win/loss read from the results scoreboard at the
  end of a match, via `outcome.read_scoreboard` -> `outcome.outcome_reward`.
* **Per-step shaping** (approximate): rewards **taking enemy towers** and
  penalises **losing your own**, so the agent gets signal during the ~3-4 min
  match instead of only at the end.

Tower state is read by checking for a team-coloured tower structure at each of
the six tower anchors (blue = yours, red = enemy). Because a lone frame is noisy
(troops/spells occlude towers, and your blue towers read faintly), a tower is
only latched **destroyed** once its colour stays gone for several consecutive
reads -- rubble is grey and towers never rebuild mid-match, so the latch can't
falsely flip back. Shaping is best-effort: calibrate the anchors on a recording
(`run.py verify`) or turn it off with `env.tower_shaping: false` to rely on the
(robust) win/loss reward alone.
"""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

# Six tower anchors as normalized (x, y): [L princess, R princess, king].
_DEFAULT_ENEMY = [[0.25, 0.21], [0.72, 0.21], [0.48, 0.12]]
_DEFAULT_MINE = [[0.25, 0.61], [0.72, 0.61], [0.48, 0.72]]
_ANCHOR_HALF = (0.075, 0.05)     # box half-width, half-height (normalized)
_ALIVE_FRAC = 0.03               # min team-colour fraction for a tower to read "alive"
_CONFIRM_STEPS = 3               # consecutive "gone" reads before latching destroyed


def _box(frame: np.ndarray, nx: float, ny: float) -> np.ndarray:
    h, w = frame.shape[:2]
    x0, x1 = int((nx - _ANCHOR_HALF[0]) * w), int((nx + _ANCHOR_HALF[0]) * w)
    y0, y1 = int((ny - _ANCHOR_HALF[1]) * h), int((ny + _ANCHOR_HALF[1]) * h)
    return frame[max(0, y0):y1, max(0, x0):x1]


def _red_mask(hsv: np.ndarray) -> np.ndarray:
    m1 = cv2.inRange(hsv, (0, 110, 80), (10, 255, 255))
    m2 = cv2.inRange(hsv, (168, 110, 80), (179, 255, 255))
    return cv2.bitwise_or(m1, m2)


def _red_frac(hsv: np.ndarray) -> float:
    return float(_red_mask(hsv).mean()) / 255.0


def _blue_frac(hsv: np.ndarray) -> float:
    return float(cv2.inRange(hsv, (95, 80, 80), (125, 255, 255)).mean()) / 255.0


def _team_frac(frame: np.ndarray, nx: float, ny: float, enemy: bool) -> float:
    box = _box(frame, nx, ny)
    if box.size == 0:
        return 0.0
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    return _red_frac(hsv) if enemy else _blue_frac(hsv)


def tower_alive_flags(frame: np.ndarray, cfg=None) -> Tuple[List[bool], List[bool]]:
    """Per-frame (no latch) alive flags for (mine, enemy) towers -- for debug/verify."""
    mine_a, enemy_a, thr = _anchors(cfg)
    mine = [_team_frac(frame, x, y, enemy=False) >= thr for x, y in mine_a]
    enemy = [_team_frac(frame, x, y, enemy=True) >= thr for x, y in enemy_a]
    return mine, enemy


ANCHOR_HALF = _ANCHOR_HALF  # public alias for drawing overlay boxes


def tower_readings(frame: np.ndarray, cfg=None):
    """(label, nx, ny, frac, alive, enemy) per tower anchor -- for the verify overlay."""
    mine_a, enemy_a, thr = _anchors(cfg)
    out = []
    for i, (x, y) in enumerate(enemy_a):
        f = _team_frac(frame, x, y, enemy=True)
        out.append((f"E{i + 1}", x, y, f, f >= thr, True))
    for i, (x, y) in enumerate(mine_a):
        f = _team_frac(frame, x, y, enemy=False)
        out.append((f"M{i + 1}", x, y, f, f >= thr, False))
    return out


def _anchors(cfg):
    if cfg is None:
        return _DEFAULT_MINE, _DEFAULT_ENEMY, _ALIVE_FRAC
    enemy = cfg.get("env", "enemy_towers", default=_DEFAULT_ENEMY)
    mine = cfg.get("env", "my_towers", default=_DEFAULT_MINE)
    thr = float(cfg.get("env", "tower_alive_frac", default=_ALIVE_FRAC))
    return mine, enemy, thr


# --- Enemy troop activity (spell-effect + patience rewards) ----------------
# Enemy units are red like the enemy towers, so measuring a spell's effect uses
# the BEFORE->AFTER drop in red mass at the target (a drop = units killed/scattered;
# the delta cancels the static tower). Whole-arena red mass (towers masked out)
# tells whether the board is 'quiet' so holding cards is fine. These are coarse
# pixel proxies -- calibrate the region/thresholds with `verify --spells`.
_ARENA_REGION = [0.03, 0.10, 0.97, 0.86]     # play area (x0,y0,x1,y1), excludes HUD + tray


def _arena_region(cfg):
    return cfg.get("env", "arena_region", default=_ARENA_REGION) if cfg else _ARENA_REGION


def enemy_mass_at(frame: np.ndarray, cx: float, cy: float, r: float, cfg=None) -> float:
    """Enemy (red) pixel fraction in a normalized box of half-size r around (cx, cy)."""
    h, w = frame.shape[:2]
    x0, x1 = int((cx - r) * w), int((cx + r) * w)
    y0, y1 = int((cy - r) * h), int((cy + r) * h)
    box = frame[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
    if box.size == 0:
        return 0.0
    return _red_frac(cv2.cvtColor(box, cv2.COLOR_BGR2HSV))


def troop_size_at(frame: np.ndarray, cx: float, cy: float, r: float, cfg=None) -> float:
    """Footprint of the LARGEST connected enemy-troop blob in the target box, as a
    fraction of the box area.

    A single big unit (Balloon / Bowler / Witch) shows up as one large red blob; a
    swarm (skeletons / goblins) is many tiny separate blobs, so its largest blob is
    small. Scaling a rocket's hit/kill reward by this -- rather than the raw red mass --
    makes reward track the SIZE (~HP / value) of the unit hit: a swarm of chip troops
    earns little, a fat high-HP unit earns more. A small open() drops speckle noise so
    the largest blob is a real unit, not stray red pixels. Coarse proxy (overlapping
    units merge; sprite size only loosely tracks HP) -- tune the scale in config.
    """
    h, w = frame.shape[:2]
    x0, x1 = int((cx - r) * w), int((cx + r) * w)
    y0, y1 = int((cy - r) * h), int((cy + r) * h)
    box = frame[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
    if box.size == 0:
        return 0.0
    mask = _red_mask(cv2.cvtColor(box, cv2.COLOR_BGR2HSV))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return 0.0
    return float(stats[1:, cv2.CC_STAT_AREA].max()) / float(mask.size)


def enemy_mass(frame: np.ndarray, cfg=None) -> float:
    """Enemy-troop activity over the arena: red pixel fraction with the enemy tower
    boxes blanked out (so the static red towers don't read as troops)."""
    h, w = frame.shape[:2]
    mask = _red_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV))
    _, enemy_a, _ = _anchors(cfg)
    for nx, ny in enemy_a:
        x0, x1 = int((nx - _ANCHOR_HALF[0]) * w), int((nx + _ANCHOR_HALF[0]) * w)
        y0, y1 = int((ny - _ANCHOR_HALF[1]) * h), int((ny + _ANCHOR_HALF[1]) * h)
        mask[max(0, y0):y1, max(0, x0):x1] = 0
    ax0, ay0, ax1, ay1 = _arena_region(cfg)
    arena = mask[int(ay0 * h):int(ay1 * h), int(ax0 * w):int(ax1 * w)]
    return float(arena.mean()) / 255.0 if arena.size else 0.0


def near_enemy_princess(cx: float, cy: float, cfg=None, radius: float = 0.12) -> bool:
    """True if a target is aimed at an enemy PRINCESS tower (an intended chip, not a
    whiff). The king (3rd anchor) is excluded -- rocketing the king counts as a whiff."""
    _, enemy_a, _ = _anchors(cfg)
    return any(abs(cx - nx) <= radius and abs(cy - ny) <= radius for nx, ny in enemy_a[:2])


def near_enemy_king(cx: float, cy: float, cfg=None, radius: float = 0.12) -> bool:
    """True if a target is aimed at the enemy KING tower (3rd enemy anchor). A spell here
    just wakes the king early -- a waste, penalised harder than a plain whiff."""
    _, enemy_a, _ = _anchors(cfg)
    if len(enemy_a) < 3:
        return False
    nx, ny = enemy_a[2]
    return abs(cx - nx) <= radius and abs(cy - ny) <= radius


def near_my_king(cx: float, cy: float, cfg=None, radius: float = 0.12) -> bool:
    """True if a target is aimed at YOUR king tower (3rd 'mine' anchor) -- e.g. a defensive
    tornado that pulls the push onto your high-HP king to tank it and activate it."""
    mine_a, _, _ = _anchors(cfg)
    if len(mine_a) < 3:
        return False
    nx, ny = mine_a[2]
    return abs(cx - nx) <= radius and abs(cy - ny) <= radius


def weaker_princess_cell(cx, cy, radius, enemy_anchors, enemy_hp, enemy_alive, gw, gh):
    """If a target (cx, cy) is aimed at an enemy princess and BOTH princesses are alive
    with DIFFERENT remaining HP, return the grid cell centered on the lower-HP one -- so
    a rocket finishes off the weaker tower instead of splitting damage. Returns None
    (keep the original target) when it isn't a princess aim, a princess is already down,
    or the two are tied. ``enemy_hp`` / ``enemy_alive`` are indexed [left, right] to
    match the first two enemy anchors.
    """
    princesses = enemy_anchors[:2]
    if not any(abs(cx - nx) <= radius and abs(cy - ny) <= radius for nx, ny in princesses):
        return None
    alive = [i for i in range(len(princesses))
             if enemy_alive is None or (i < len(enemy_alive) and enemy_alive[i])]
    if len(alive) < 2:
        return None                                   # need both princesses up to pick the weaker
    a, b = alive[0], alive[1]
    if enemy_hp[a] == enemy_hp[b]:
        return None                                   # tied HP -> no efficiency gain, keep the aim
    i = a if enemy_hp[a] < enemy_hp[b] else b
    nx, ny = princesses[i]
    gx = min(max(int(nx * gw), 0), gw - 1)
    gy = min(max(int(ny * gh), 0), gh - 1)
    return gy * gw + gx


def threat_side(frame, cfg=None, min_frac=0.02):
    """Which of your two lanes has an advancing enemy threat: -1 left, +1 right, 0 none.
    Compares enemy (red) troop mass in the left vs right half of YOUR side of the arena
    (from the bridge down to near your king), so a defender can be sent to the threatened
    lane. 0 when neither side has more than ``min_frac`` red mass."""
    h, w = frame.shape[:2]
    mask = _red_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV))
    y0, y1 = int(0.44 * h), int(0.80 * h)
    xm = int(0.48 * w)
    left = mask[y0:y1, :xm]
    right = mask[y0:y1, xm:w]
    lf = float(left.mean()) / 255.0 if left.size else 0.0
    rf = float(right.mean()) / 255.0 if right.size else 0.0
    if max(lf, rf) < min_frac:
        return 0
    return -1 if lf > rf else 1


def threat_front(frame, side, cfg=None, min_frac=0.02, a_bot=0.84):
    """Deepest (largest y, closest to YOUR king) row holding enemy troops on the threatened
    lane -- normalized y, or None. Lets a ranged defender be placed a fixed distance BEHIND
    this front so the push has to close the gap under fire instead of landing on top of it."""
    h, w = frame.shape[:2]
    mask = _red_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV))
    y0, y1 = int(0.44 * h), int(a_bot * h)
    xm = int(0.48 * w)
    lane = mask[y0:y1, :xm] if side < 0 else mask[y0:y1, xm:w]
    if lane.size == 0:
        return None
    rows = (lane > 0).mean(1)
    hits = np.where(rows >= min_frac)[0]
    if len(hits) == 0:
        return None
    return 0.44 + (float(hits.max()) / lane.shape[0]) * (a_bot - 0.44)


def defensive_cell(kind, side, front_y, gw, gh, params):
    """Grid cell for a DEFENSIVE placement. Evo Musketeer -> the very back (charged shot).
    Ranged units (Tesla / Ice Wizard / Musketeer) are placed toward the CENTRE (biased to
    the threatened side by ``center_bias``): the horizontal gap to an edge push adds to the
    vertical gap, so the push must close a longer diagonal under fire AND gets pulled to the
    middle where BOTH princess towers help. Because the centre offset covers part of the
    reach, the depth behind the front is only ``center_depth_frac`` x the unit's range.
    ``side`` is -1 left / +1 right; ``front_y`` is the deepest enemy troop y on that lane.

    The depth is capped at ``back_limit`` so the placement stays on the central grass in FRONT
    of your king tower. The centre column deeper than that is the king tower's own footprint,
    where a troop can't be deployed -- an uncapped defender aimed there just fails to place (the
    card is selected but the arena tap is a no-op), so the bot 'shuffles' it instead of playing.

    EXCEPTION -- a push that has broken PAST your kiting line (``front_y`` beyond ``close_defense_y``,
    i.e. already at your towers): a MOBILE defender then stops kiting and is placed BETWEEN the push
    and your king (just behind the front, ``close_side_bias`` to the threatened side to clear the
    central king footprint), body-blocking it instead of being kept at a distance it never engages
    from. Buildings (``building_kinds``) keep the capped central spot -- their own reward shapes depth.
    """
    if kind == "musketeer_evo":
        nx, ny = params["musketeer_evo"]
    else:
        rng = params["range_offsets"].get(kind, 0.13)
        if kind not in params.get("building_kinds", ()) and front_y > params.get("close_defense_y", 0.58):
            nx = 0.48 + side * params.get("close_side_bias", 0.13)   # off-centre to the threatened side (clears the king)
            ny = min(front_y + params.get("close_depth", 0.03), params["a_bot"])  # just behind the push front -> between it and the king
        else:
            nx = 0.48 + side * params["center_bias"]
            ny = min(front_y + rng * params["center_depth_frac"], params["a_bot"])
            ny = min(ny, params.get("back_limit", 0.58))   # stay on the central grass, off the king tower
    gx = min(max(int(nx * gw), 0), gw - 1)
    gy = min(max(int(ny * gh), 0), gh - 1)
    return gy * gw + gx


class TowerTracker:
    """Latches tower destruction over a match and emits the shaping reward."""

    def __init__(self, cfg=None):
        self.cfg = cfg
        self.enabled = bool(cfg.get("env", "tower_shaping", default=True)) if cfg else True
        self.confirm = int(cfg.get("env", "tower_confirm_steps", default=_CONFIRM_STEPS)) if cfg else _CONFIRM_STEPS
        self.take = float(cfg.get("rewards", "take_enemy_tower", default=1.0)) if cfg else 1.0
        self.lose = float(cfg.get("rewards", "lose_own_tower", default=-1.0)) if cfg else -1.0
        self.mine_a, self.enemy_a, self.thr = _anchors(cfg)
        self.reset()

    def reset(self) -> None:
        self.enemy_alive = [True] * len(self.enemy_a)
        self.mine_alive = [True] * len(self.mine_a)
        self._enemy_low = [0] * len(self.enemy_a)
        self._mine_low = [0] * len(self.mine_a)

    def _update_side(self, frame, anchors, alive, low, enemy: bool) -> int:
        """Return number of towers newly latched destroyed this step."""
        newly = 0
        for i, (x, y) in enumerate(anchors):
            if not alive[i]:
                continue
            if _team_frac(frame, x, y, enemy) < self.thr:
                low[i] += 1
                if low[i] >= self.confirm:
                    alive[i] = False
                    newly += 1
            else:
                low[i] = 0
        return newly

    def step(self, frame: np.ndarray) -> float:
        """Shaping reward for towers destroyed since the last step (0 if disabled)."""
        if not self.enabled:
            return 0.0
        enemy_down = self._update_side(frame, self.enemy_a, self.enemy_alive, self._enemy_low, True)
        # Latch ALL your towers (crown_counts / win-loss reads them), but only the KING adds the
        # flat lose penalty here: princess HP loss is penalised GRADUALLY by TowerHpTracker (the
        # env tops it up to the full lose_own_tower on destruction), so they don't double-count.
        king_i = len(self.mine_a) - 1
        king_before = self.mine_alive[king_i] if self.mine_a else False
        self._update_side(frame, self.mine_a, self.mine_alive, self._mine_low, False)
        king_down = 1 if (king_before and king_i >= 0 and not self.mine_alive[king_i]) else 0
        return enemy_down * self.take + king_down * self.lose  # lose is negative in config

    def crown_counts(self) -> Tuple[int, int, bool, bool]:
        """Crowns implied by latched tower falls: (blue, red, enemy_king_down, my_king_down).

        In Clash Royale crowns == towers destroyed, so the in-match destruction
        latch is a second, independent read of the result -- used to cross-check
        the finicky end-of-match scoreboard. ``blue`` = enemy towers you felled,
        ``red`` = your towers lost; the last anchor in each list is the king,
        whose fall is decisive (3 crowns / instant game over).
        """
        blue = int(sum(not a for a in self.enemy_alive))
        red = int(sum(not a for a in self.mine_alive))
        enemy_king = len(self.enemy_alive) >= 3 and not self.enemy_alive[2]
        my_king = len(self.mine_alive) >= 3 and not self.mine_alive[2]
        return blue, red, enemy_king, my_king

    def king_trending_down(self) -> Tuple[bool, bool]:
        """(enemy, mine) king that is destroyed OR was TRENDING destroyed (>=1 'gone' read) at the
        moment the match ended. A king fall ends the match instantly, so its destruction latch (needs
        ``confirm`` consecutive reads) frequently can't finish before the frame cuts to the results
        screen -- this recovers that near-miss so a 3-crown finish is counted as 3, not under-read."""
        ek = len(self.enemy_alive) >= 3 and (not self.enemy_alive[2] or self._enemy_low[2] >= 1)
        mk = len(self.mine_alive) >= 3 and (not self.mine_alive[2] or self._mine_low[2] >= 1)
        return ek, mk
