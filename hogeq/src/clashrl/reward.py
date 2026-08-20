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

import math

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


def weaker_princess_cell(cx, cy, radius, enemy_anchors, enemy_hp, enemy_alive, acts):
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
    return acts.cell_at(nx, ny)


def pump_rocket_cell(px, py, enemy_anchors, enemy_alive, pair_gap, king_guard, acts):
    """Best KING-SAFE rocket aim for a detected enemy ELIXIR COLLECTOR at (px, py): the midpoint that
    clips an adjacent ALIVE princess tower too when the two fit one blast (within ``pair_gap``), else
    the pump itself, else the pump nudged AWAY from the king. Returns a grid cell, or None when every
    candidate would land within ``king_guard`` of the enemy KING -- activating the king costs more
    than any pump, so in that case the caller keeps the policy's own aim."""
    king = tuple(enemy_anchors[2]) if len(enemy_anchors) >= 3 else (0.48, 0.11)
    cands = []
    for i, (ax, ay) in enumerate(enemy_anchors[:2]):
        alive = enemy_alive is None or (i < len(enemy_alive) and enemy_alive[i])
        if alive and np.hypot(px - ax, py - ay) <= pair_gap:
            cands.append(((px + ax) / 2.0, (py + ay) / 2.0))      # double hit: pump + tower
    cands.append((px, py))                                        # solo pump
    dx, dy = px - king[0], py - king[1]
    n = float(np.hypot(dx, dy)) or 1.0
    cands.append((px + dx / n * 0.05, py + dy / n * 0.05))        # nudged away from the king
    for tx, ty in cands:
        if np.hypot(tx - king[0], ty - king[1]) >= king_guard:
            return acts.cell_at(tx, ty)
    return None


def spell_intercept_cell(cx, cy, tracks, impact_s, snap_radius, acts):
    """LEAD THE TARGET: aim a point-blast spell at where the tracked enemies around the policy's aim
    will BE when it lands, not where they are now -- act latency + rocket flight add up to seconds,
    and a marching push walks clean out of a 2-tile blast in that time. ``tracks`` = [(x, y, vx, vy)]
    from TeamTracker.enemy_tracks(); tracks whose CURRENT position is within ``snap_radius`` of the
    aim (the group the policy meant) are advanced ``impact_s`` along their velocity, and the aim
    snaps to their predicted CENTROID. None = no tracked enemy near the aim (the aim stands)."""
    near = [(x + vx * impact_s, y + vy * impact_s) for x, y, vx, vy in tracks
            if np.hypot(x - cx, y - cy) <= snap_radius]
    if not near:
        return None
    tx = min(0.98, max(0.02, float(np.mean([p[0] for p in near]))))
    ty = min(0.98, max(0.02, float(np.mean([p[1] for p in near]))))
    return acts.cell_at(tx, ty)


def xbow_target_lane_cell(cx, cy, enemy_anchors, enemy_hp, enemy_alive, defense_y, acts,
                          hp_margin=0.10):
    """Put an OFFENSIVE X-Bow in the lane whose tower is worth shooting at.

    Reported from live overtime (user, 2026-08-16), one tower down each side: the model placed a
    technically perfect offensive bow several times and every one of them was in the lane whose
    enemy princess was ALREADY DESTROYED. Six elixir, a good spot, and nothing to chip -- the bow
    can only fall through to the king, which is far tankier and further away.

    Nothing existing catches this. ``xbow_lock_cell`` snaps to the NEARER tower's lane, which is
    precisely the wrong move when the nearer one is the dead one, and the depth assist only sets
    the row. Neither ever asks whether the target is alive.

    Two rules, in order:

      1. NEVER bow a dead lane. If the princess this bow points at is down and the other is up,
        move to the live one. Hard, no margin -- a destroyed tower cannot be chipped at all.
      2. Otherwise concentrate on the WEAKER tower, so successive bows work toward one kill
        instead of splitting the damage across two. Needs a real gap (``hp_margin`` of full HP)
        so a near-tie does not make the lane flap between placements.

    Keeps the bow's DEPTH row -- the caller's depth assist owns that. Returns a new cell, or None
    to leave the placement alone (defensive bow, no anchors, or already the right lane).
    """
    princesses = enemy_anchors[:2] if enemy_anchors else []
    if len(princesses) < 2 or cy >= defense_y:
        return None                                   # defensive bow: it is not aiming at a tower
    alive = list(enemy_alive or [True, True])[:2]
    while len(alive) < 2:
        alive.append(True)
    aimed = 0 if abs(princesses[0][0] - cx) <= abs(princesses[1][0] - cx) else 1
    other = 1 - aimed

    if not alive[aimed]:
        if not alive[other]:
            return None                               # both down: the king is all that is left
        return acts.cell_at(princesses[other][0], cy)  # rule 1: shoot something that exists
    if not alive[other]:
        return None                                   # already on the only live tower

    hp = list(enemy_hp or [])
    if len(hp) < 2 or hp[aimed] is None or hp[other] is None:
        return None
    full = max(hp[aimed], hp[other]) or 1.0
    if hp[other] < hp[aimed] - hp_margin * full:      # rule 2: concentrate on the weaker one
        return acts.cell_at(princesses[other][0], cy)
    return None


def xbow_lock_cell(cx, cy, enemy_anchors, xbow_range, defense_y, acts):
    """Snap a FORWARD (offensive) X-Bow that landed OUT of firing range onto the nearer enemy
    princess's LANE so it actually locks the tower. The policy tends to drop the X-Bow at the far
    bridge EDGE (or dead centre) where -- once the deploy clamp holds it on your side of the river --
    it sits just outside ``xbow_range`` and never locks. Keeps the model's depth row, pulls x to the
    nearer tower's lane. Returns a new grid cell, or None (leave it) for a deep/defensive X-Bow
    (cy >= defense_y) or one that already reaches a tower.
    """
    princesses = enemy_anchors[:2] if enemy_anchors else []
    if not princesses or cy >= defense_y:
        return None
    d = min(np.hypot(cx - nx, cy - ny) for nx, ny in princesses)
    if d <= xbow_range:
        return None                                   # already in range -> keep the model's choice
    nx = min(princesses, key=lambda a: abs(a[0] - cx))[0]   # nearer tower's lane
    return acts.cell_at(nx, cy)                       # nearer lane column, model's own depth row


# Board geometry shared by the placement assists below (engine frame: river y=0.5, your side is
# the HIGH-y half, ground units cross only at a bridge).
BRIDGE_XS = (0.25, 0.75)
TILE = 0.16 / 5.5                # one board tile, normalized (long reach 0.16 == 5.5 tiles)


def _front_row_y(acts, deploy_top):
    """Centre-y of the FRONTMOST row an ordinary card can actually be deployed on.

    ``action.deploy_top`` is a clamp line, not a row: the nearest grid row to it can sit ABOVE it
    and would simply be pushed back by deploy_clamp, silently undoing any correction aimed there.
    """
    best = None
    for r in range(acts.gh):
        y = acts.cell_center(0, r)[1]
        if y >= deploy_top and (best is None or y < best):
            best = y
    return deploy_top if best is None else best


def xbow_offense_depth_cell(cx, cy, defense_y, deploy_top, acts,
                            bridge_tol=0.045, lane_back_rows=1):
    """Set the DEPTH of an OFFENSIVE X-Bow from the column it was placed in.

    The X-Bow's reach to the enemy princess is a RADIUS, so the frontmost row is not uniformly
    correct -- how far forward it must sit depends on how far off-lane it is:

    * BEHIND A BRIDGE (the tiles troops actually cross, x ~ 0.25 / 0.75) the bow is nearly in the
      tower's own column, so it still locks the tower a row further back. That row buys the thing
      the frontmost one cannot: ROOM to drop a Knight/Tesla IN FRONT of the bow to absorb the
      answer. Measured at lane x: 0.260 out at the front row, 0.291 one back -- both inside 0.36.
    * CENTRE (anywhere between the two crossings) the path to the tower is diagonal and longer, so
      the bow must sit on the FRONTMOST deployable row or it falls short. Measured at centre x:
      0.347 at the front row and 0.358 one row back, against a 0.36 range -- no slack at all.

    Keeps the model's column (it chooses the side). Returns a corrected cell, or None when the
    depth is already right or the bow is DEFENSIVE (cy >= defense_y, judged by its own band).
    """
    if cy >= defense_y:
        return None
    row_h = abs(acts.cell_center(0, 1)[1] - acts.cell_center(0, 0)[1]) or TILE
    ty = _front_row_y(acts, deploy_top)
    if min(abs(cx - b) for b in BRIDGE_XS) <= bridge_tol:
        ty += lane_back_rows * row_h                  # in-lane: one row back for the blocker
    if abs(cy - ty) <= 0.4 * row_h:
        return None                                   # already on the right row
    return acts.cell_at(cx, ty)


def tesla_pull_cell(wx, wy, sight, front_y, back_y, acts, bridges=BRIDGE_XS):
    """CENTRE-PULL a lane win condition: the furthest-from-the-attack tile that still aggros it.

    A win condition dropped at one bridge beelines the near princess tower, and only that tower
    ever shoots it. A defensive building placed inside its AGGRO radius but pulled toward the
    middle drags it off that line, so it walks across the centre under fire instead. The best spot
    is therefore the one that maximises horizontal distance from the attacking side while STILL
    sitting inside the win condition's sight radius -- any further and it is not pulled at all.

    ``sight`` is the card's own aggro radius from the KB (``CardDB.sight_range_tiles`` -> normalized),
    so a 9.5-tile Hog is pulled much further across than a 5.5-tile Ram Rider. Solves
    ``dx = sqrt(sight^2 - dy^2)`` for the placement row and steps that far toward mid-board.
    Returns None when the row is already outside the radius (no pull is possible from there).
    """
    ty = 0.5 * (float(front_y) + float(back_y))
    dy = abs(ty - wy)
    if dy >= sight:
        return None                                   # unreachable from this row -- no pull exists
    dx = float(np.sqrt(max(0.0, sight * sight - dy * dy)))
    sgn = 1.0 if wx < 0.5 else -1.0                   # step AWAY from the attacking side
    lo, hi = min(bridges), max(bridges)
    # The grid is COARSE (a cell is ~0.05 wide, wider than the margin we are aiming for), so the
    # ideal x can snap to a cell whose CENTRE sits outside the aggro radius -- which would place a
    # building the win condition never even looks at, the exact failure this assist exists to avoid.
    # Walk inward a cell at a time until the SNAPPED centre is genuinely inside.
    cw = abs(acts.cell_center(1, 0)[0] - acts.cell_center(0, 0)[0]) or 0.02
    for _ in range(8):
        tx = min(max(wx + sgn * dx, lo), hi)
        cell = acts.cell_at(tx, ty)
        px, py = acts.cell_center(cell % acts.gw, cell // acts.gw)
        if np.hypot(px - wx, py - wy) <= sight:
            return cell
        dx -= cw                                      # too far out -- give back one column
        if dx <= 0:
            return None
    return None


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


def defensive_cell(kind, side, front_y, acts, params):
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
    return acts.cell_at(nx, ny)


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


# ---- spell-impact verification (2026-08-19) ---------------------------------------------
#
# The live reward scored spells AT CAST by aim geometry alone -- the spell-impact frame sampler
# was retired -- so a whiffed rocket paid the same as a landed one and `spell_waste` never fired
# live (user report). These are the pure evaluators; env.py owns the pending queue and the
# tracker. Tracker tracks are used instead of raw detections because they BRIDGE detector misses
# (a unit absent from ~31% of passes is carried for forget_s), so a whiff verdict cannot be
# manufactured by one missed frame.

def spell_whiffed(cx, cy, radius_tiles, enemy_tracks, tower_anchors=(), tower_alive=(),
                  tower_aim_radius=0.10, tiles_x=18.0, tiles_y=32.0):
    """True when a spell aimed at (cx, cy) has NO enemy within `radius_tiles` TILES, and is not
    aimed at a live enemy tower.

    THE RADIUS IS IN TILES, and the comparison scales each axis by the board's own dimensions.
    This used to take a normalised radius and compare normalised Euclidean distance, which
    silently stretched every blast vertically: the board is 18 x 32, so tornado's 5.5-tile pull
    became 7.0 tiles wide and 12.4 TILES TALL and "hit" half the arena (user, 2026-08-20 -- a
    tornado cast in the river was scored as a hit). Same bug nado_regressed had and the same fix.

    `enemy_tracks` are (x, y, ...) tuples from TeamTracker.enemy_tracks.
    """
    for tr in enemy_tracks:
        if math.hypot((tr[0] - cx) * tiles_x, (tr[1] - cy) * tiles_y) <= radius_tiles:
            return False
    for i, (ax, ay) in enumerate(tower_anchors):
        alive = bool(tower_alive[i]) if i < len(tower_alive) else True
        if alive and math.hypot(cx - ax, cy - ay) <= tower_aim_radius:
            return False
    return True


def nado_regressed(pulled_at_cast, enemy_tracks_now, my_princess_anchors,
                   follow_radius=0.22, gain_tiles=1.0, tiles_x=18.0, tiles_y=32.0):
    """True when a tornado made things WORSE: the units it pulled are still alive (their tracks
    persist near where the pull left them) and ended up CLOSER to our princess towers than when
    the cast began, by more than `gain_tiles` -- with nothing to show for it (the caller only
    invokes this when no kill combo and no king activation were credited).

    `pulled_at_cast` is [(x, y)] captured at cast for enemies inside the pull radius. LIVE tracks
    carry no identity handle across seconds, so survivors are matched by proximity: the nearest
    current enemy track within `follow_radius` of each pulled unit's cast position stands in for
    it. Approximate BY DESIGN (documented) -- the sim twin uses engine ground truth instead."""
    if not pulled_at_cast or not my_princess_anchors:
        return False

    def d_home(x, y):
        # TRUE TILES, per axis: the board is 18 x 32, so a normalized-space hypot understates
        # vertical distance by nearly half -- a 2.2-tile pull toward our tower measured as 0.9
        # "tiles" and slipped under the gain gate (caught by this function's own verification).
        return min(math.hypot((x - ax) * tiles_x, (y - ay) * tiles_y)
                   for ax, ay in my_princess_anchors)

    deltas = []
    for (px, py) in pulled_at_cast:
        best, bd = None, follow_radius
        for tr in enemy_tracks_now:
            g = math.hypot(tr[0] - px, tr[1] - py)
            if g <= bd:
                best, bd = tr, g
        if best is None:
            continue                                  # died or left -- not a regression
        deltas.append(d_home(px, py) - d_home(best[0], best[1]))
    if not deltas:
        return False                                  # everything it pulled is gone: fine
    # positive delta = the survivor is CLOSER to our towers than where the pull found it
    return (sum(deltas) / len(deltas)) >= gain_tiles


# Tiles per second, from the KB's speed words. Clash Royale's published bands: slow 45, medium 60,
# fast 90, very fast 120 "units"; one tile is 1000 units per minute, i.e. tiles/s = band / 60.
_SPEED_TILES_S = {"slow": 0.75, "medium": 1.0, "fast": 1.5, "very_fast": 2.0, "very fast": 2.0}


def lead_velocity(track, db=None, toward_y: float = 1.0):
    """(vx, vy) in board units/second for a tracked enemy, in TILE-correct terms.

    Prefers the tracker's measured velocity. Falls back to the card's KNOWN WALKING SPEED when the
    track is too young to have one -- enemy_tracks reports zero velocity below 0.5 s of history,
    which is exactly the window in which a just-crossed win condition needs leading most (user
    report, 2026-08-20). A unit on our half is walking at our towers, so the fallback points down
    the lane; `toward_y` is +1 because our towers sit at the high-y end of the board.
    """
    vx = float(track[2]) if len(track) > 2 else 0.0
    vy = float(track[3]) if len(track) > 3 else 0.0
    if abs(vx) > 1e-6 or abs(vy) > 1e-6:
        return vx, vy
    base = str(track[4]) if len(track) > 4 and track[4] else ""
    if not base or db is None:
        return 0.0, 0.0
    c = db.get(base) or {}
    if (c.get("kind") or "") not in ("troop", "champion"):
        return 0.0, 0.0                                   # buildings and spells do not walk
    speed = str(c.get("speed") or "medium").strip().lower().replace("-", "_")
    tiles_s = _SPEED_TILES_S.get(speed, 1.0)
    return 0.0, toward_y * tiles_s / 32.0                  # board units: 32 tiles down the y axis


def lead_point(cx, cy, tracks, impact_s, snap_radius_tiles, db=None,
               tiles_x=18.0, tiles_y=32.0):
    """Where the enemies the policy aimed at will BE when the spell lands.

    Distances are measured in TRUE TILES (the board is 18x32, so a normalised radius is nearly
    twice as permissive down the y axis -- the bug that made a river tornado "hit" things 12 tiles
    away). Returns None when nothing tracked is near the aim, so the caller's own aim stands.
    """
    pts = []
    for t in tracks:
        if math.hypot((t[0] - cx) * tiles_x, (t[1] - cy) * tiles_y) > snap_radius_tiles:
            continue
        vx, vy = lead_velocity(t, db)
        pts.append((t[0] + vx * impact_s, t[1] + vy * impact_s))
    if not pts:
        return None
    tx = min(0.98, max(0.02, sum(p[0] for p in pts) / len(pts)))
    ty = min(0.98, max(0.02, sum(p[1] for p in pts) / len(pts)))
    return tx, ty


def log_hits(cx, cy, tracks, half_w=0.064, roll=0.28, air=()):
    """Would a Log cast at (cx, cy) actually touch anything?

    The roll starts AT the cast point and travels forward (decreasing y -- our side is the high-y
    end), so the damage area is the band `x within half_w` and `cy - roll <= y <= cy`. A unit
    BEHIND the cast point is never hit, which is the whole of the "log played too high" failure:
    the push is behind the roll and the spell touches nothing.

    Flying bases are excluded -- the Log passes underneath them.
    """
    for t in (tracks or ()):
        base = str(t[4]) if len(t) > 4 and t[4] else ""
        if base and base in air:
            continue
        if abs(float(t[0]) - cx) > half_w:
            continue                                  # beside the corridor
        dy = cy - float(t[1])                          # >0 = the unit is FORWARD of the cast
        if -0.5 * half_w <= dy <= roll:
            return True
    return False
