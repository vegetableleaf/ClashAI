"""Radius-graded placement geometry -- the PURE scoring module (research/RADIUS_REWARD_PROPOSALS.md).

Step 0 of the graded reward (L58). Everything here is plain arithmetic over a plain record of the
board: no engine import at module top, no RNG, no config read. The sim env builds a :class:`Board`
from the engine (:func:`board_from_engine`, lazy import), the live env will build one from tracks,
and `sim-view --radii` draws the SAME radii this module scores (:func:`radii_of` is the one source
of truth for `r_atk` / `r_sight`), so what you see is what is scored.

Conventions (all from the doc's §1):
  * positions are NORMALISED (x, y in 0..1); every distance is in TILES on an 18 x 32 board whose
    axes are not isotropic -- `_dist` scales each axis by its tile count, never a bare hypot;
  * `band(x; lo, hi, w)` is the one curve shape: 1 inside [lo, hi], linear to 0 over `w` on each
    side, 0 beyond. Every credit is 0..1 and peaks in the band; the only negative terms are
    `p1_close_penalty` (+ its snapshot twin) and `p7_fragility`, all bounded in [-1, 0];
  * team 0's own half is HIGH y (own princess y ~0.797); the scorer's team is `Board.team` and
    "enemy" means `obj.team != board.team`;
  * towers: alive only (doc §7.5). A dead tower is not on the board at all.

Choices where the doc is ambiguous are listed in the progress file
(scratchpad/gauntlet/L58/impl_geometry.md) and marked `CHOICE:` inline below.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# --- defaults (match config/config.yaml `sim.*` and the engine's board) -------------------------
DEFAULT_TILES = (18.0, 32.0)
DEFAULT_RIVER_Y = 0.5
DEFAULT_BRIDGES_X = (3.5 / 18.0, 14.5 / 18.0)
DEFAULT_TOWER_RANGE = 8.0        # princess reach, tiles (config sim.tower_range)
DEFAULT_KING_RANGE = 8.5         # king reach, tiles (config sim.king_range)
DEFAULT_SIEGE_SIGHT = 11.5       # X-Bow engage range, tiles (config sim.siege_sight)
DEFAULT_SIGHT = 5.5              # troop aggro fallback, tiles (config sim.sight_tiles)
DEFAULT_RIVER_HALF = 1.0         # river half-thickness, tiles

# --- the doc's constants (P1-P7, §7.3, §7.4) ---------------------------------------------------
P1_LO_PAD = 1.0                  # lo = r_atk(t) + 1.0
P1_W = 2.0
P2_W = 1.5
P3_W = 2.0
P3_KITE_SIGHT_MAX = 5.0          # kiteable threat: r_sight(t) <= 5.0
P3_KITE_W = 0.5
P5_LO_PAD = 0.5                  # lo = t_cross + 0.5
P5_HI_PAD = 1.0                  # hi = t_hit + 1.0 (owner ruling Q2)
P5_W = 1.5
P6_LO_PAD = 0.5                  # lo = r_atk(tower) + 0.5
P6_W = 1.0
P6_BUILDING_W = 0.5
P7_W = 0.5
THREAT_MIN_VALUE = 3.0           # "ACTUAL threat": value >= 3 elixir, or a building-targeting wincon
MELEE_REACH_MAX = 2.0            # CHOICE: a threat with r_atk <= 2.0 tiles counts as melee for P1/P7
FRAGILE_HP_MAX = 800.0           # CHOICE: P7 "low-HP counter" = hp_max <= 800 (Ice Wizard / Skeletons)
BRIDGE_BLOCK_TILES = 1.5         # §7.4: placement within 1.5 tiles of a bridge tile
BRIDGE_APPROACH_PAD = 3.0        # §7.4: enemy within r_sight(unit) + 3 tiles of the bridge
BRIDGE_SUPPORT_ANTI = 3          # §7.4 anti-case (1): >= 3 enemy troops trailing the tank
BRIDGE_NO_BLOCK_BASES = ("magic_archer", "firecracker")     # §7.4 B9: never a block case
BRIDGE_WALL_BREAKER_BASES = ("wall_breakers",)              # B7
BRIDGE_PRINCESS_BASES = ("princess",)                       # B8

SWARM_ROLE = "swarm"             # L59: P7 is never charged to a swarm card (gate.md 1d.4)
CREDIT_FLOOR = -0.3              # L59: placement_credit floor (the close / fragility penalties are clipped here)
CREDIT_CAP = 1.0                 # L59: placement_credit cap (a pull AND an offensive bow can coincide)

TERM_KEYS = (
    "p1_pull_band", "p1_close_penalty", "p2_cover", "p3_intercept", "p4_spell_frac", "p4_nado",
    "p4_king_activation", "p5_timing", "p6_siege", "p7_fragility",
    "bridge_block_detected", "bridge_block_case", "d_threat",
    # L59 (HANDOFF 5cs.29 decisions): the OLD snapshot P1 pair, kept so the gate rerun reports both.
    # `p1_pull_band` is now PATH-based (band on the distance from the building to the threat's forward
    # march path); `p1_snapshot` / `p1_close_snapshot` are the same formulas on the threat's CURRENT
    # march distance. Both P1 bands are RAW (no P2 factor) -- `placement_credit` applies (0.5 + 0.5 P2).
    "p1_snapshot", "p1_close_snapshot", "d_path",
)


# =============================================================================================
# records
# =============================================================================================
@dataclass
class BoardObj:
    """One body on the board. Radii in TILES, position normalised. `value` is elixir-equivalent."""
    team: int
    kind: str                       # "troop" | "building" | "tower" | "spell"
    base: str                       # card key (towers: "princess" / "king")
    x: float
    y: float
    r_atk: float
    r_sight: float
    r_body: float = 0.5
    hp: float = 1.0
    hp_max: float = 1.0
    value: float = 0.0
    speed: float = 0.0              # tiles / s
    flying: bool = False
    building_only: bool = False
    alive: bool = True
    king: bool = False
    target_xy: Optional[Tuple[float, float]] = None
    deploying: bool = False
    active: bool = True             # towers: king AWAKE (princesses always active)
    splash: bool = False
    siege: bool = False
    roles: Tuple[str, ...] = ()     # KB roles, most salient first (card_threat.ThreatProfile.roles)


@dataclass
class Board:
    objs: List[BoardObj]
    team: int
    t: float = 0.0
    tiles: Tuple[float, float] = DEFAULT_TILES
    river_y: float = DEFAULT_RIVER_Y
    bridges_x: Tuple[float, ...] = DEFAULT_BRIDGES_X
    tower_range: float = DEFAULT_TOWER_RANGE
    king_range: float = DEFAULT_KING_RANGE
    river_half: float = DEFAULT_RIVER_HALF     # tiles

    # -- views -----------------------------------------------------------------------------
    def own(self) -> List[BoardObj]:
        return [o for o in self.objs if o.team == self.team and o.alive]

    def enemy(self) -> List[BoardObj]:
        return [o for o in self.objs if o.team != self.team and o.alive]

    def own_towers(self) -> List[BoardObj]:
        return [o for o in self.own() if o.kind == "tower"]

    def enemy_towers(self) -> List[BoardObj]:
        return [o for o in self.enemy() if o.kind == "tower"]

    def own_side(self, y: float) -> bool:
        """Is normalised y on the scorer's side of the river? Team 0 owns HIGH y."""
        return (y >= self.river_y) if self.team == 0 else (y <= self.river_y)


# =============================================================================================
# the curve, the metric
# =============================================================================================
def band(x: float, lo: float, hi: float, w: float) -> float:
    """1 for lo <= x <= hi, linear to 0 over `w` on each side, 0 beyond (doc §1)."""
    if lo <= x <= hi:
        return 1.0
    if w <= 0.0:
        return 0.0
    if x < lo:
        return max(0.0, 1.0 - (lo - x) / w)
    return max(0.0, 1.0 - (x - hi) / w)


def clip01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else float(v))


def tile_dist(ax: float, ay: float, bx: float, by: float, tiles=DEFAULT_TILES) -> float:
    """Distance in TILES between two normalised points (engine `_dist`)."""
    return math.hypot((ax - bx) * tiles[0], (ay - by) * tiles[1])


def gap(ax: float, ay: float, ref: BoardObj, tiles=DEFAULT_TILES) -> float:
    """Distance in TILES from a point to `ref`'s hitbox EDGE, clamped at 0 (engine `_gap`)."""
    return max(0.0, tile_dist(ax, ay, ref.x, ref.y, tiles) - float(ref.r_body))


def nearest_bridge(board: Board, x: float) -> float:
    return min(board.bridges_x, key=lambda b: abs(x - b))


def march_gap(board: Board, ax: float, ay: float, ref_x: float, ref_y: float,
              ref_body: float = 0.0) -> float:
    """Lane-aware travel distance in TILES from (ax, ay) to the hitbox edge of a body of radius
    `ref_body` at (ref_x, ref_y): straight when on the same side of the river, else through the
    bridge nearest `ax` (engine `_march_gap`)."""
    tx, ty = board.tiles
    r = board.river_y
    if (ay - r) * (ref_y - r) >= 0.0:
        return max(0.0, tile_dist(ax, ay, ref_x, ref_y, board.tiles) - ref_body)
    bx = nearest_bridge(board, ax)
    leg1 = math.hypot((bx - ax) * tx, (r - ay) * ty)
    leg2 = math.hypot((ref_x - bx) * tx, (ref_y - r) * ty)
    return max(0.0, leg1 + leg2 - ref_body)


# =============================================================================================
# radii: the ONE source of truth
# =============================================================================================
def radii_of(spec_like, *, siege_sight: float = DEFAULT_SIEGE_SIGHT,
             tower_range: float = DEFAULT_TOWER_RANGE,
             king_range: float = DEFAULT_KING_RANGE) -> Tuple[float, float]:
    """(r_atk, r_sight) in TILES for a CardSpec, an engine Tower, a Unit, or a BoardObj.

    * BoardObj  -> its stored radii.
    * Tower     -> reach = king_range if king else tower_range; a tower aggros at its reach.
    * Unit      -> its spec.
    * CardSpec  -> troop/building: (reach, sight or 5.5); siege: (reach, siege_sight);
                   spell: (spell_radius, 0.0) -- a spell has a blast, not an aggro circle.
    """
    if isinstance(spec_like, BoardObj):
        return float(spec_like.r_atk), float(spec_like.r_sight)
    spec = getattr(spec_like, "spec", None)
    if spec is not None:                                    # a Unit
        return radii_of(spec, siege_sight=siege_sight, tower_range=tower_range, king_range=king_range)
    if not hasattr(spec_like, "reach") and hasattr(spec_like, "king"):   # a Tower
        r = float(king_range if getattr(spec_like, "king", False) else tower_range)
        return r, r
    kind = getattr(spec_like, "kind", "troop")
    if kind == "spell":
        return float(getattr(spec_like, "spell_radius", 0.0) or 0.0), 0.0
    reach = float(getattr(spec_like, "reach", 0.0) or 0.0)
    if getattr(spec_like, "siege", False):
        return reach, float(siege_sight)
    sight = getattr(spec_like, "sight", None)
    return reach, float(sight if sight else DEFAULT_SIGHT)


# =============================================================================================
# adapters (lazy imports: this module stays importable without the engine or the KB)
# =============================================================================================
def board_from_engine(engine, team: int) -> Board:
    """Ground-truth Board from a SimEngine: every living unit (deploying ones INCLUDED, flagged
    `deploying=True` so the timing term can see them) and every ALIVE tower."""
    from .card_threat import profile as _profile      # lazy: KB roles for the bridge-block table

    db = getattr(engine, "db", None)
    ss = float(getattr(engine, "siege_sight", DEFAULT_SIEGE_SIGHT))
    tr = float(getattr(engine, "tower_range", DEFAULT_TOWER_RANGE))
    kr = float(getattr(engine, "king_range", DEFAULT_KING_RANGE))
    objs: List[BoardObj] = []
    for u in engine.units:
        if u.hp <= 0:
            continue
        s = u.spec
        ra, rs = radii_of(s, siege_sight=ss, tower_range=tr, king_range=kr)
        roles: Tuple[str, ...] = ()
        if db is not None:
            try:
                roles = tuple(_profile(db, s.base).roles())
            except Exception:              # noqa: BLE001 -- the KB is advisory here
                roles = ()
        tgt = getattr(u, "target", None)
        txy = None
        if tgt is not None and float(getattr(tgt, "hp", 0.0)) > 0.0 and getattr(tgt, "alive", True):
            txy = (float(tgt.x), float(tgt.y))
        objs.append(BoardObj(
            team=int(u.team), kind=str(s.kind), base=str(s.base), x=float(u.x), y=float(u.y),
            r_atk=ra, r_sight=rs, r_body=float(s.radius), hp=float(u.hp), hp_max=float(s.hp or 1.0),
            value=float(s.elixir or 0.0), speed=float(s.speed or 0.0), flying=bool(s.flying),
            building_only=bool(s.building_only), alive=True, king=False, target_xy=txy,
            deploying=bool(getattr(u, "deploy_left", 0.0) > 0.0), active=True,
            splash=bool(getattr(s, "splash", False)), siege=bool(getattr(s, "siege", False)),
            roles=roles))
    for tm, tws in engine.towers.items():
        for tw in tws:
            if not tw.alive or tw.hp <= 0:
                continue                                   # doc §7.5: a taken tower is not on the board
            ra, rs = radii_of(tw, siege_sight=ss, tower_range=tr, king_range=kr)
            objs.append(BoardObj(
                team=int(tm), kind="tower", base="king" if tw.king else "princess",
                x=float(tw.x), y=float(tw.y), r_atk=ra, r_sight=rs, r_body=float(tw.radius),
                hp=float(tw.hp), hp_max=float(tw.max_hp or 1.0), value=0.0, speed=0.0,
                alive=True, king=bool(tw.king), active=bool(getattr(tw, "active", True)),
                roles=("tower",)))
    tiles = (float(getattr(engine, "tiles_x", DEFAULT_TILES[0])),
             float(getattr(engine, "tiles_y", DEFAULT_TILES[1])))
    lanes = tuple(float(b) for b in getattr(engine, "lanes", DEFAULT_BRIDGES_X))
    return Board(objs=objs, team=int(team), t=float(getattr(engine, "t", 0.0)), tiles=tiles,
                 river_y=DEFAULT_RIVER_Y, bridges_x=lanes, tower_range=tr, king_range=kr,
                 river_half=float(getattr(engine, "river_width", 2.0)) / 2.0)


def placement_from_spec(spec, x: float, y: float, *, siege_sight: float = DEFAULT_SIEGE_SIGHT,
                        tower_range: float = DEFAULT_TOWER_RANGE,
                        king_range: float = DEFAULT_KING_RANGE, db=None,
                        roles: Optional[Sequence[str]] = None) -> dict:
    """The `placement` dict :func:`score_placement` takes, from a CardSpec + landing tile.

    `roles` = the placed card's KB roles (P7 is skipped for a swarm card). Given explicitly, or read
    from `db` through the SAME source `role_average_radii` uses (`card_threat.profile(...).roles()`);
    with neither, the placement carries no roles and P7 is charged as before."""
    ra, rs = radii_of(spec, siege_sight=siege_sight, tower_range=tower_range, king_range=king_range)
    if roles is None and db is not None:
        try:
            from .card_threat import profile as _profile
            roles = tuple(_profile(db, str(spec.base)).roles())
        except Exception:              # noqa: BLE001 -- the KB is advisory here
            roles = ()
    return dict(
        roles=tuple(roles or ()),
        base=str(spec.base), kind=str(spec.kind), x=float(x), y=float(y), r_atk=ra, r_sight=rs,
        r_body=float(getattr(spec, "radius", 0.5) or 0.5),
        deploy_time=float(getattr(spec, "deploy_time", 1.0) or 0.0),
        speed=float(getattr(spec, "speed", 0.0) or 0.0),
        building_only=bool(getattr(spec, "building_only", False)),
        is_spell=(spec.kind == "spell"),
        spell_radius=float(getattr(spec, "spell_radius", 0.0) or 0.0),
        pull_radius=float(getattr(spec, "pull_radius", 0.0) or 0.0),
        siege=bool(getattr(spec, "siege", False)),
        splash=bool(getattr(spec, "splash", False)),
        hp=float(getattr(spec, "hp", 0.0) or 0.0),
        value=float(getattr(spec, "elixir", 0.0) or 0.0),
    )


_ROLE_CACHE: Dict[str, Tuple[float, float]] = {}


def role_average_radii(base_key: str, db=None) -> Tuple[float, float]:
    """(r_atk, r_sight) averaged over every KB troop/building sharing `base_key`'s PRIMARY role
    (doc §7.1 / §7.8: the band the model can derive from role bits alone). Cached per role."""
    from . import cards as _cards
    from .card_threat import profile as _profile

    if db is None:
        db = _cards.shared()
    role = _profile(db, base_key).roles()[0]
    hit = _ROLE_CACHE.get(role)
    if hit is not None:
        return hit
    atk: List[float] = []
    sight: List[float] = []
    for key, c in db.cards.items():
        if not isinstance(c, dict) or c.get("kind") not in ("troop", "building"):
            continue
        if _profile(db, key).roles()[0] != role:
            continue
        atk.append(float(db.attack_range_tiles(key)))
        s = float(db.sight_range_tiles(key))
        if "siege" in (c.get("flags") or []):
            s = max(s, DEFAULT_SIEGE_SIGHT)
        sight.append(s)
    if not atk:                                             # unknown role: the card's own numbers
        out = (float(db.attack_range_tiles(base_key)), float(db.sight_range_tiles(base_key)))
    else:
        out = (sum(atk) / len(atk), sum(sight) / len(sight))
    _ROLE_CACHE[role] = out
    return out


# =============================================================================================
# geometry helpers used by the terms
# =============================================================================================
def _nearest_own_tower_by_march(board: Board, o: BoardObj, towers: Sequence[BoardObj]) -> Optional[BoardObj]:
    """The scorer's tower this ENEMY body would march to (min lane-aware distance)."""
    if not towers:
        return None
    if o.flying:
        return min(towers, key=lambda tw: gap(o.x, o.y, tw, board.tiles))
    return min(towers, key=lambda tw: march_gap(board, o.x, o.y, tw.x, tw.y, tw.r_body))


def threat_path(board: Board, t: BoardObj) -> List[Tuple[float, float]]:
    """The threat's march line as normalised waypoints: [pos, (bridge), goal]. Its locked target
    if it has one; else through its lane's bridge (ground only) to the scorer's nearest ALIVE
    tower. CHOICE: a building-targeter's path ignores our buildings (the tower is the reference)."""
    pts = [(t.x, t.y)]
    if t.target_xy is not None:
        gx, gy = t.target_xy
    else:
        tw = _nearest_own_tower_by_march(board, t, board.own_towers())
        if tw is None:
            return pts
        gx, gy = tw.x, tw.y
    r = board.river_y
    if not t.flying and (t.y - r) * (gy - r) < 0.0:
        pts.append((nearest_bridge(board, t.x), r))
    pts.append((gx, gy))
    return pts


def _path_len(board: Board, pts: Sequence[Tuple[float, float]]) -> float:
    return sum(tile_dist(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], board.tiles)
               for i in range(len(pts) - 1))


def _project(board: Board, pts: Sequence[Tuple[float, float]], x: float, y: float):
    """Closest point on the polyline to (x, y). Returns (dist_tiles, s_tiles, total_len, (px, py))
    with `s` the arc length from the threat to the foot of the perpendicular."""
    tx, ty = board.tiles
    best = (float("inf"), 0.0, (x, y))
    acc = 0.0
    for i in range(len(pts) - 1):
        ax, ay = pts[i][0] * tx, pts[i][1] * ty
        bx, by = pts[i + 1][0] * tx, pts[i + 1][1] * ty
        qx, qy = x * tx, y * ty
        dx, dy = bx - ax, by - ay
        seg = math.hypot(dx, dy)
        if seg <= 1e-9:
            u = 0.0
        else:
            u = max(0.0, min(1.0, ((qx - ax) * dx + (qy - ay) * dy) / (seg * seg)))
        fx, fy = ax + u * dx, ay + u * dy
        d = math.hypot(qx - fx, qy - fy)
        if d < best[0]:
            best = (d, acc + u * seg, (fx / tx, fy / ty))
        acc += seg
    if len(pts) < 2:
        return tile_dist(x, y, pts[0][0], pts[0][1], board.tiles), 0.0, 0.0, (pts[0][0], pts[0][1])
    return best[0], best[1], acc, best[2]


def is_threat(o: BoardObj) -> bool:
    """The doc's 'significant threat' (owner): value >= 3 elixir, or a building-targeting wincon.
    A lone Skeleton / Goblin never qualifies. Troops only; an enemy building is not an approach."""
    return (o.kind == "troop" and o.alive and o.hp > 0.0
            and (o.value >= THREAT_MIN_VALUE or o.building_only))


def pick_threat(board: Board, placement: dict) -> Optional[BoardObj]:
    """CHOICE: the most URGENT qualifying enemy -- smallest lane-aware distance to the scorer's
    nearest alive tower (the identity block's 'deepest recognised enemy' convention). Ties break
    toward the one nearest the placement."""
    towers = board.own_towers()
    cands = [o for o in board.enemy() if is_threat(o)]
    if not cands:
        return None
    px, py = float(placement["x"]), float(placement["y"])

    def key(o: BoardObj):
        tw = _nearest_own_tower_by_march(board, o, towers)
        d = (march_gap(board, o.x, o.y, tw.x, tw.y, tw.r_body) if tw is not None else 99.0)
        return (round(d, 3), tile_dist(o.x, o.y, px, py, board.tiles))
    return min(cands, key=key)


# =============================================================================================
# the terms
# =============================================================================================
def _p2_cover(board: Board, px: float, py: float, r_body: float) -> float:
    """P2: sum over own ALIVE princess towers of band(d; 0, r_atk(tower), 1.5), then min(., 2)/2.
    CHOICE: d is measured the way the tower measures reach -- tower centre to the placed body's
    hitbox edge (centre distance minus the placement's r_body)."""
    cover = 0.0
    for tw in board.own_towers():
        if tw.king:
            continue
        d = max(0.0, tile_dist(px, py, tw.x, tw.y, board.tiles) - r_body)
        cover += band(d, 0.0, tw.r_atk, P2_W)
    return min(cover, 2.0) / 2.0


def _bridge_block(board: Board, placement: dict, threat: Optional[BoardObj]) -> Tuple[float, float, Optional[float]]:
    """§7.4: (detected, case, bridge_x). Detected = placement within 1.5 tiles of a bridge tile
    while an enemy ground unit in that lane is within r_sight + 3 tiles of the bridge and
    approaching it (CHOICE: 'moving toward' = still on the far side of the river)."""
    px, py = float(placement["x"]), float(placement["y"])
    tx, ty = board.tiles
    bx = nearest_bridge(board, px)
    if abs(px - bx) * tx > BRIDGE_BLOCK_TILES or abs(py - board.river_y) * ty > BRIDGE_BLOCK_TILES:
        return 0.0, 0.0, None
    approaching = [
        o for o in board.enemy()
        if o.kind == "troop" and not o.flying and nearest_bridge(board, o.x) == bx
        and not board.own_side(o.y)
        and tile_dist(o.x, o.y, bx, board.river_y, board.tiles) <= o.r_sight + BRIDGE_APPROACH_PAD]
    if not approaching:
        return 0.0, 0.0, None
    # the unit being blocked: the qualifying threat if it is one of them, else the nearest approacher
    t = threat if (threat is not None and threat in approaching) else \
        min(approaching, key=lambda o: tile_dist(o.x, o.y, bx, board.river_y, board.tiles))
    case = _block_case(board, placement, t, approaching, bx)
    return 1.0, case, bx


def _block_case(board: Board, placement: dict, t: BoardObj, lane: Sequence[BoardObj], bx: float) -> float:
    """B1-B8 from KB roles (1.0) with the anti-cases (B9, >= 3 trailing supports) zeroing it."""
    if t.base in BRIDGE_NO_BLOCK_BASES:                                   # B9
        return 0.0
    roles = set(t.roles)
    # anti-case (1): a lot of support behind the tank -> the block hands them a deployed push
    behind = [o for o in lane if o is not t and not o.flying
              and ((o.y < t.y) if board.team == 0 else (o.y > t.y))]
    if len(behind) >= BRIDGE_SUPPORT_ANTI:
        return 0.0
    ground_escort = any(o is not t and not o.flying for o in lane)
    if t.building_only and not t.flying:                                  # B1: Hog-role wincon
        return 1.0
    if t.flying and t.building_only and ground_escort:                    # B2: Balloon + escort
        return 1.0
    if "tank" in roles and not t.flying:                                  # B3 mini-tank / B5 tank + escort
        return 1.0
    if t.base in BRIDGE_WALL_BREAKER_BASES and not placement.get("splash", False):   # B7
        return 1.0
    if t.base in BRIDGE_PRINCESS_BASES:                                   # B8
        return 1.0
    return 0.0


def score_placement(board: Board, placement: dict,
                    threat: Optional[BoardObj] = None) -> Dict[str, float]:
    """Grade one placement. Returns one value per term (0.0 when a term does not apply) plus
    `threat_base` (the enemy the P1/P3/P5 terms were scored against) and `d_threat` (tiles)."""
    out: Dict[str, float] = {k: 0.0 for k in TERM_KEYS}
    out["threat_base"] = ""        # type: ignore[assignment]
    px, py = float(placement["x"]), float(placement["y"])
    kind = str(placement.get("kind", "troop"))
    is_spell = bool(placement.get("is_spell", kind == "spell"))
    is_building = (kind == "building") and not is_spell
    is_troop = (kind == "troop") and not is_spell
    r_body = float(placement.get("r_body", 0.5) or 0.5)
    r_sight_c = float(placement.get("r_sight", DEFAULT_SIGHT) or DEFAULT_SIGHT)
    deploy_time = float(placement.get("deploy_time", 1.0) or 0.0)
    speed_c = float(placement.get("speed", 0.0) or 0.0)
    siege = bool(placement.get("siege", str(placement.get("base", "")) in ("x_bow", "mortar")))

    # L59: the sim env passes ITS assessed threat (the `_threat_pos()` unit) so both halves of the
    # threat-response term grade the same body; standalone callers keep the module's own pick.
    threat = threat if threat is not None else pick_threat(board, placement)
    detected, case, bridge_x = _bridge_block(board, placement, threat)
    out["bridge_block_detected"], out["bridge_block_case"] = detected, case

    # ---- P2: cover of the engagement point (building: itself; troop: the intercept) ----------
    eng_pt = (px, py)
    path: List[Tuple[float, float]] = []
    if threat is not None:
        out["threat_base"] = threat.base    # type: ignore[assignment]
        out["d_threat"] = gap(px, py, threat, board.tiles)
        # overlay hooks (doc 7.2): where the threat is and the P1 band it defines, in the same
        # units the terms are scored in (normalised position, tile radii)
        out["threat_x"], out["threat_y"] = threat.x, threat.y
        out["p1_band_lo"] = threat.r_atk + P1_LO_PAD
        out["p1_band_hi"] = threat.r_sight
        path = threat_path(board, threat)
        if is_troop and len(path) >= 2:
            eng_pt = _project(board, path, px, py)[3]
        if detected and case and bridge_x is not None:
            eng_pt = (bridge_x, board.river_y)          # §7.4: the bridge tile is the intercept
    # L59: P2 is a BUILDING term only (gate.md 1d.1/1d.2: on troops it ranks the pros' river-bank
    # skeletons below the behind-the-king cell, on spells the enemy-half cast point has cover 0).
    # The intercept-point cover is still computed for the P3 kite check below, not reported.
    out["p2_cover"] = _p2_cover(board, eng_pt[0], eng_pt[1], r_body) if is_building else 0.0

    if threat is not None and not is_spell:
        # ---- P1: building pull band --------------------------------------------------------
        if is_building:
            towers = board.own_towers()
            # snapshot distance: the threat's CURRENT march distance to the building's hitbox edge
            x = march_gap(board, threat.x, threat.y, px, py, r_body)
            if threat.flying:
                x = max(0.0, tile_dist(threat.x, threat.y, px, py, board.tiles) - r_body)
            tw = _nearest_own_tower_by_march(board, threat, towers)
            d_tower = (march_gap(board, threat.x, threat.y, tw.x, tw.y, tw.r_body)
                       if tw is not None else float("inf"))
            # pull_ok: the building is acquired before the tower (nearer by march distance). A
            # building BEHIND the tower on the threat's path is further by march than the tower.
            pull_ok = 1.0 if x < d_tower else 0.0
            lo = threat.r_atk + P1_LO_PAD
            # L59 PATH-based P1 (HANDOFF 5cs.29 (b)(1)): the band is on `d_path` = the distance from
            # the building's hitbox edge to the FORWARD part of the threat's march path (current
            # position -> its lane's bridge if the river is between -> the own alive tower it would
            # target, or its locked target) -- `_project` clamps to the polyline, so nothing behind
            # the threat counts. The pros pre-place while the threat is still outside the snapshot
            # band; the path band fires as soon as the tile sits beside the lane it will walk.
            if len(path) >= 2:
                d_path = max(0.0, _project(board, path, px, py)[0] - r_body)
            else:
                d_path = x
            out["d_path"] = d_path
            out["p1_pull_band"] = band(d_path, lo, threat.r_sight, P1_W) * pull_ok
            out["p1_snapshot"] = band(x, lo, threat.r_sight, P1_W) * pull_ok
            if threat.r_atk <= MELEE_REACH_MAX:            # dropped on top of a MELEE wincon
                # CHOICE (brief): "unchanged in form but measured on d_path". NOTE this also fires for
                # a building placed IN the lane ahead of the threat (d_path ~ 0 while the threat is
                # still far) -- the snapshot version is kept beside it for the gate to compare.
                out["p1_close_penalty"] = -clip01((lo - d_path) / lo) if lo > 0 else 0.0
                out["p1_close_snapshot"] = -clip01((lo - x) / lo) if lo > 0 else 0.0
        # ---- P3: troop intercept -----------------------------------------------------------
        if is_troop and not placement.get("building_only", False) and len(path) >= 2:
            if detected and case and bridge_x is not None:
                x = tile_dist(px, py, bridge_x, board.river_y, board.tiles)
                ahead = 1.0
            else:
                x, s, total, _ = _project(board, path, px, py)
                if s <= 1e-6 or s >= total - 1e-6:
                    ahead = 0.0                             # behind the threat, or behind its goal
                elif x <= r_body + threat.r_body + 0.5:
                    ahead = 1.0                             # a body IN the path
                else:
                    ahead = 0.5                             # beside it
            p3 = band(x, 0.0, r_sight_c, P3_W) * ahead
            if threat.r_sight <= P3_KITE_SIGHT_MAX and _p2_cover(board, px, py, r_body) > 0.0:
                d = gap(px, py, threat, board.tiles)
                p3 += band(d, threat.r_sight - 1.0, threat.r_sight, P3_KITE_W)
            out["p3_intercept"] = min(1.0, p3)              # CHOICE: the kite bonus is capped at 1
        # ---- P5: timing gradient -----------------------------------------------------------
        if detected:
            out["p5_timing"] = 1.0 if case else 0.0         # §7.4: full when a block case, else 0, never negative
        elif threat.speed > 0.0 and len(path) >= 2:
            v = threat.speed
            tw_goal = path[-1]
            if len(path) >= 3:
                t_cross = tile_dist(threat.x, threat.y, path[1][0], path[1][1], board.tiles) / v
            elif threat.flying and not board.own_side(threat.y):
                t_cross = abs(threat.y - board.river_y) * board.tiles[1] / v
            else:
                t_cross = 0.0
            tw = _nearest_own_tower_by_march(board, threat, board.own_towers())
            tw_body = tw.r_body if tw is not None else 0.0
            total = _path_len(board, path) - tw_body          # to the goal's hitbox edge
            t_hit = max(0.0, total - threat.r_atk) / v
            travel = 0.0
            if is_troop and speed_c > 0.0:
                travel = tile_dist(px, py, eng_pt[0], eng_pt[1], board.tiles) / speed_c
            t_resp = deploy_time + travel
            out["p5_timing"] = band(t_resp, t_cross + P5_LO_PAD, t_hit + P5_HI_PAD, P5_W)
            # L59 env hooks: the window edges the sim env's timing gate reads (not in TERM_KEYS)
            out["t_cross"], out["t_hit"], out["t_resp"] = t_cross, t_hit, t_resp
        # ---- P7: fragility -----------------------------------------------------------------
        hp_c = float(placement.get("hp", 0.0) or 0.0)
        is_swarm = SWARM_ROLE in tuple(placement.get("roles", ()) or ())
        # L59: a SWARM card (skeletons; KB role "swarm") is never charged -- the pros drop skeletons ON
        # the threat to surround it (gate.md 1d.4: 0.1% for / 7.6% against). Kept for ranged low-HP
        # counters (ice wizard).
        if (is_troop and not is_swarm and 0.0 < hp_c <= FRAGILE_HP_MAX and not threat.building_only
                and (threat.splash or threat.r_atk <= MELEE_REACH_MAX)):
            out["p7_fragility"] = -band(gap(px, py, threat, board.tiles), 0.0, threat.r_atk, P7_W)

    # ---- P4: spells ----------------------------------------------------------------------
    if is_spell:
        r_blast = float(placement.get("spell_radius", 0.0) or 0.0)
        r_pull = float(placement.get("pull_radius", 0.0) or 0.0)
        enemies = [o for o in board.enemy() if o.kind == "troop" and o.hp > 0.0]
        push = [o for o in enemies if board.own_side(o.y)] or enemies   # CHOICE: the push = enemy troops on our half
        push_value = sum(o.value for o in push)
        if push_value > 0.0 and r_blast > 0.0:
            inside = sum(o.value for o in push if gap(px, py, o, board.tiles) <= r_blast)
            out["p4_spell_frac"] = clip01(inside / push_value)
        if push_value > 0.0 and r_pull > 0.0:
            towers = board.own_towers()
            num = 0.0
            pulled = 0
            for u in push:
                d_u = tile_dist(u.x, u.y, px, py, board.tiles)
                if d_u > r_pull:
                    continue
                pulled += 1
                num += u.value * clip01(1.0 - d_u / r_pull) * tornado_away(board, u, px, py, towers)
            out["p4_nado"] = clip01(num / push_value)
            king = next((tw for tw in towers if tw.king), None)
            if (pulled >= 1 and king is not None and not king.active
                    and gap(px, py, king, board.tiles) <= king.r_atk):
                out["p4_king_activation"] = 1.0
        out["p2_cover"] = 0.0     # L59: the pull / blast centre's cover is NOT a spell term (gate 1d.1)

    # ---- P6: offensive siege ---------------------------------------------------------------
    if is_building and siege:
        etw = board.enemy_towers()
        princesses = [tw for tw in etw if not tw.king]
        pool = princesses or [tw for tw in etw if tw.king]
        if pool:
            tower = min(pool, key=lambda tw: gap(px, py, tw, board.tiles))
            d = gap(px, py, tower, board.tiles)
            credit = band(d, tower.r_atk + P6_LO_PAD, r_sight_c, P6_W)
            under = 0.0
            for b in board.enemy():
                if b.kind == "building" and b.r_atk > 0.0:
                    under = max(under, band(gap(px, py, b, board.tiles), 0.0, b.r_atk, P6_BUILDING_W))
            out["p6_siege"] = credit * (1.0 - under)
    return out


def placement_credit(terms: Dict[str, float], kind: str, p7_enabled: bool = False) -> float:
    """The PLACEMENT part of the graded reward (L59 / HANDOFF 5cs.29), per kind:
      building: min(CAP, p1_pull_band * (0.5 + 0.5 * p2_cover) + p6_siege) + max(FLOOR, p1_close_snapshot)
                (L59 lead ruling 6.3: the close penalty is for dropping ON TOP of the unit -- the snapshot
                gap -- not for sitting in its path; `p1_close_penalty` (d_path form) stays logged)
      troop:    p3_intercept (+ max(FLOOR, p7_fragility) only when `p7_enabled`)
      spell:    0.0 (P4 is LOGGED only in run 1; the spell ledger is untouched)
    Range: [CREDIT_FLOOR, CREDIT_CAP] = [-0.3, 1.0] for every kind. The cap exists because a placement
    can be BOTH a pull (P1 > 0) and an offensive bow (P6 > 0): an X-Bow on the bank vs a bridge hog."""
    def g(k):
        return float(terms.get(k, 0.0) or 0.0)
    kind = str(kind)
    if kind == "building":
        pos = g("p1_pull_band") * (0.5 + 0.5 * g("p2_cover")) + g("p6_siege")
        return min(CREDIT_CAP, max(0.0, pos)) + max(CREDIT_FLOOR, min(0.0, g("p1_close_snapshot")))
    if kind == "troop":
        pos = min(CREDIT_CAP, max(0.0, g("p3_intercept")))
        if p7_enabled:
            pos += max(CREDIT_FLOOR, min(0.0, g("p7_fragility")))
        return pos
    return 0.0


def timing_credit(terms: Dict[str, float]) -> float:
    """The play-TIMING part: P5 (a bridge-block case is already 1.0 inside P5, doc 7.4)."""
    return min(1.0, max(0.0, float(terms.get("p5_timing", 0.0) or 0.0)))


def tornado_away(board: Board, u: BoardObj, cx: float, cy: float, towers: Sequence[BoardObj]) -> float:
    """§7.3 `away` = 0.5 * (1 - dot(dir_u, goal_u)): 1 when the pull (u -> centre) points straight
    AWAY from the unit's goal (u -> the next waypoint of its march to our nearest alive tower)."""
    tx, ty = board.tiles
    dx, dy = (cx - u.x) * tx, (cy - u.y) * ty
    n = math.hypot(dx, dy)
    if n <= 1e-9:
        return 0.5
    pts = threat_path(board, u)
    if len(pts) < 2:
        return 0.5
    gx, gy = (pts[1][0] - u.x) * tx, (pts[1][1] - u.y) * ty
    m = math.hypot(gx, gy)
    if m <= 1e-9:
        return 0.5
    dot = (dx * gx + dy * gy) / (n * m)
    return clip01(0.5 * (1.0 - dot))


def nonzero_terms(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    """(name, value) for every numeric term that is not 0 -- what the overlay prints."""
    out = []
    for k in TERM_KEYS:
        v = scores.get(k, 0.0)
        if isinstance(v, (int, float)) and abs(float(v)) > 1e-9 and k not in ("d_threat", "d_path"):
            out.append((k, float(v)))
    return out
