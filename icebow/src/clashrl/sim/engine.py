"""Headless Clash-Royale-ish match engine (no vision, no rendering by itself).

Medium-fidelity, STAT-DRIVEN from the card knowledge base (clashrl.cards.CardDB): elixir economy,
lane movement with bridge crossing, target acquisition with an AGGRO/SIGHT range + target commitment
(building-only + siege rules), a ~1s DEPLOY delay, DISCRETE hit-speed combat with splash, slow/stun/
freeze crowd-control, soft-collision body-blocking, princess/king towers (the king wakes on ANY
damage), and area/rolling spells. It is deliberately NOT a faithful CR clone -- exact pathfinding,
champions, evolutions, and card-specific quirks (charge / ramp-up) are still out of scope. The point
is enough fidelity that a policy trained here transfers as a PRIOR to the real game (then fine-tuned
live). See icebow/DECK_SWITCH.md (Stage: simulator) and log.txt.

Coordinates are NORMALISED [0,1] on each axis (so the obs render, ActionSpace cells and reward
geometry are unchanged), but the BOARD IS A TILE GRID -- 18 tiles wide x 32 tall in real Clash
Royale -- and every DISTANCE here (reach, sight, splash, blast, pull, speed) is measured in TILES.
Those two facts together mean the axes have DIFFERENT scales: one normalised unit spans 18 tiles
across and 32 tiles up, so :func:`_dist` converts to tiles before measuring. A plain hypot on
normalised coordinates -- what this engine used to do -- silently made every range ~1.78x shorter
HORIZONTALLY than vertically. (The old constants were all calibrated on the y axis: medium speed
0.031 normalised/s x 32 tiles = 0.99 tiles/s, i.e. vertical behaviour was right and only x was
compressed. Converting by x32 therefore preserves the tuned vertical behaviour exactly.)

The tower anchors are DERIVED FROM TILES and symmetric about the river, rather than borrowed from
`env.my_towers` / `env.enemy_towers`. Those are LIVE SCREEN coordinates carrying the real game's
perspective foreshortening (the far end is compressed on screen); importing them into a flat
top-down sim put your towers 0.115 from the river and the enemy's 0.295 -- and broke the self-play
mirror, which reflects about y=0.5.

enemy side is the TOP (y<0.5), your side the BOTTOM (y>0.5), the river at y=0.5.
team 0 = you (bottom/blue), team 1 = opponent (top/red).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

# --- BOARD GEOMETRY (tiles) -------------------------------------------------------------------
# Set once per process from `sim.board` by SimEngine.__init__ (every env in a process shares one
# config, so module-level is safe and keeps `_dist` / `build_spec` free of an engine reference).
_TILES_X = 18.0
_TILES_Y = 32.0
_BRIDGES = (3.5 / 18.0, 14.5 / 18.0)     # bridge centres, normalised x (tile-derived; set below)


def configure_board(tiles_x: float, tiles_y: float, bridge_tiles) -> None:
    """Set the tile grid + bridge lanes. Called by SimEngine.__init__ from `sim.board`."""
    global _TILES_X, _TILES_Y, _BRIDGES
    _TILES_X, _TILES_Y = float(tiles_x), float(tiles_y)
    _BRIDGES = tuple(float(b) / _TILES_X for b in bridge_tiles)


# speed word -> TILES/second (CR: medium ~= 1 tile/s; matches the old 0.031 normalised x 32)
_SPEED = {"slow": 0.75, "medium": 1.0, "fast": 1.5, "very_fast": 2.0, None: 1.0}
# attack reach word -> TILES (melee ~1, short ~3, long 5.5)
_REACH = {"melee": 1.0, "short": 3.0, "long": 5.5, None: 1.0}
_REACH_SLOP = 0.6         # tiles of tolerance on "target is in reach"
_TANK_RADIUS = 0.9        # collision radius (tiles) at/above which a unit counts as a heavy tank
_RIVER = 0.5              # the board is symmetric about this now that anchors are tile-derived
_SPLASH_R = 1.9           # splash radius, tiles
# The Log (rolling spell): a forward CORRIDOR from the cast point -- ground-only, with knockback.
_LOG_ROLL_LEN = 9.6       # how far forward it rolls (tiles)
_LOG_ROLL_HALFW = 2.2     # corridor half-width (tiles, ~a lane)
_LOG_KNOCKBACK = 1.6      # pushes ground troops this far in the roll direction (tiles)
_LOG_BACK_SLOP = 1.0      # tiles BEHIND the cast point still caught by the corridor


@dataclass
class CardSpec:
    key: str
    base: str
    kind: str                 # troop | building | spell
    elixir: int
    hp: float
    dps: float
    reach: float
    speed: float
    count: int
    flying: bool
    attacks_air: bool
    splash: bool
    building_only: bool       # targets enemy towers only (Miner / Hog ...)
    siege: bool               # stationary long-range building that can hit the tower (X-Bow / Mortar)
    kamikaze: bool            # dies after one hit (spirits)
    lifetime: Optional[float] # buildings expire; troops = None
    spell_radius: float       # spells only
    spell_dmg: float
    spell_tower_dmg: float
    spell_delay: float        # Royal Delivery lands after a delay; Rocket ~instant
    rolls: bool = False       # a ROLLING spell (The Log): a forward corridor, not a point blast
    ground_only: bool = False # hits GROUND troops only (The Log -- no air)
    knockback: float = 0.0    # a rolling spell pushes ground troops this far in the roll direction
    roll_len: float = 0.0     # forward length of the roll corridor (tiles)
    hit_speed: float = 1.0    # seconds between attacks (discrete hits)
    hit_dmg: float = 0.0      # damage per hit (= dps * hit_speed; preserves average DPS)
    tower_hit_dmg: float = 0.0  # damage per hit vs CROWN TOWERS -- reduced when the KB carries a
                              # crown_tower_damage (Miner's signature nerf); else = hit_dmg. Without
                              # this the sim let Miner chip towers at FULL damage -> king-snipe exploit.
    deploy_time: float = 1.0  # seconds before a freshly-placed unit can act (spells = 0)
    radius: float = 0.64      # collision radius, TILES (soft body-block)
    deploy_anywhere: bool = False   # KB flag: tunnels/drills to ANY tile (Miner, Goblin Drill) -- it does not
                                    # walk the lane, so it is placed straight onto the defender's tower
    slows: bool = False       # applies a SLOW on hit (Ice Wizard)
    stuns: bool = False       # applies a brief STUN (Zap / Tesla-evo pulse / Electro)
    freezes: bool = False     # applies a FREEZE -- a longer stun (Ice Spirit / Freeze)
    level: int = 11           # card level (HP + damage scaled by 1.1^(level-11))
    sight: float = 5.5        # AGGRO/SIGHT radius, TILES (from the KB per-card table, 5.5 default)
    pulse_dmg: float = 0.0    # Evo Tesla area-shock: damage per pulse
    pulse_r: float = 0.0      # pulse radius (tiles)
    pulse_stun: float = 0.0   # STUN seconds applied by each pulse
    pulse_interval: float = 0.0  # seconds between pulses (0 = no pulse)
    spawn_spec: Optional["CardSpec"] = None  # a unit dropped when the SPELL lands (Royal Delivery -> a Royal Recruit)
    spawn_count: int = 0      # how many spawn_spec units to drop at the landing point
    shield_hp: float = 0.0    # SHIELD pool (Royal Recruits / Guards / Dark Prince): absorbs damage before hp
    damage_reduction: float = 0.0  # fraction of incoming damage negated WHILE NOT ATTACKING (Evo Knight = 0.60)
    pulls: bool = False       # TORNADO: an active VORTEX, not an instant blast -- pulls enemies to its centre
    pull_radius: float = 0.0  # vortex effect radius (5.5 tiles -- much wider than a damage spell)
    pull_duration: float = 0.0  # seconds the vortex stays active (damage is spread over this)
    gen_every: float = 0.0    # ELIXIR COLLECTOR: +1 elixir to its OWNER every this many seconds (0 = none)


_SHIELD_FRAC = 0.5   # shielded units get a shield pool ~ this x their (level-scaled) body HP. Coarse approximation:
                     # the exact per-card CR shield HP isn't in the KB, so it's derived from the `shield` flag.

# TORNADO (the deck's clump enabler): a 1.05s vortex, 5.5-tile radius, that drags enemies to its centre.
# The pull is VIOLENT in real CR (edge-to-centre well inside the duration) -- that clumping is what turns
# Ice Wizard's splash into an everything-hitter and makes centre-Rocket hit a whole push. Heavy tanks
# (collision radius 0.03 = the 'tank' flag) resist at half speed.
_TORNADO_RADIUS = 5.5                   # tiles
_TORNADO_DURATION = 1.05
_TORNADO_PULL = 11.2                    # tiles/s (edge reaches centre in ~0.5s)
_ROCKET_RADIUS = 2.0                    # rocket's REAL 2-tile blast


def build_spec(db, key: str, level: int = 11) -> CardSpec:
    base = key[:-4] if key.endswith("_evo") else key
    is_evo = key.endswith("_evo")
    c = db.get(base) or {}
    flags = set(db.flags(base))
    kind = c.get("kind", "troop")
    elixir = int(c.get("elixir") or db.elixir(base) or 4)
    hp = float(c.get("hitpoints") or 300)
    dmg = float(c.get("damage") or 0.0)
    hit = float(c.get("hit_speed") or 1.0)
    dps = float(c.get("dps") or (dmg / hit if hit else dmg))
    tower_dmg = float(db.tower_damage(base) or dmg)
    reach = _REACH.get(db.attack_range(base), _REACH["melee"])     # TILES
    speed = _SPEED.get(c.get("speed"), _SPEED["medium"])           # TILES/s
    count = int(c.get("count") or 1)
    building_only = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    siege = "siege" in flags
    spell_radius = 3.5 if base == "royal_delivery" else 2.9   # tiles
    if base == "rocket":
        spell_radius = _ROCKET_RADIUS                         # honest 2-tile blast
    spell_delay = 3.0 if base == "royal_delivery" else 0.4
    ground_only = kind == "spell" and c.get("attacks") == ["ground"]
    # a ROLLING spell (The Log / Barbarian Barrel) = knockback AND ground-only corridor. Knockback alone
    # is NOT enough: Rocket/Snowball also knock back but are POINT blasts hitting air -- classifying
    # Rocket as a roll gave it a forward CORRIDOR (and the Log's 0.07 half-width) instead of its blast.
    rolls = kind == "spell" and "knockback" in flags and ground_only
    pulls = kind == "spell" and "pull" in flags               # Tornado: an active pulling vortex
    if rolls:
        spell_radius = _LOG_ROLL_HALFW                        # corridor HALF-WIDTH for a rolling spell
    lifetime = 40.0 if kind == "building" else None
    if c.get("lifetime"):                                     # curated per-card lifetime (Elixir Collector 70s)
        lifetime = float(c["lifetime"])
    gen_every = float(c.get("gen_every_s") or 0.0)            # pump economy: +1 owner elixir every this many s
    p_dmg = p_r = p_stun = p_int = 0.0
    dmg_reduc = 0.0
    evo = c.get("evolution")
    if is_evo and isinstance(evo, dict):                      # Evolution stat OVERRIDES (level-11 base)
        hp = float(evo.get("hitpoints", hp))
        dmg = float(evo.get("damage", dmg))
        hit = float(evo.get("hit_speed", hit))
        dps = float(evo.get("dps", dmg / hit if hit else dps))
        tower_dmg = float(evo.get("tower_damage", tower_dmg))
        if evo.get("lifetime"):
            lifetime = float(evo["lifetime"])
        p_dmg = float(evo.get("pulse_damage", 0.0))
        p_r = float(evo.get("pulse_radius", 0.0))            # already in TILES in the KB
        p_stun = float(evo.get("pulse_stun", 0.0))
        p_int = float(evo.get("pulse_interval", 0.0))
        dmg_reduc = float(evo.get("damage_reduction", 0.0))  # Evo Knight: takes this fraction LESS damage while not attacking
    sc = 1.1 ** (int(level) - 11)                             # CR level scaling: HP + damage only
    hp *= sc; dmg *= sc; dps *= sc; tower_dmg *= sc; p_dmg *= sc
    sight = float(db.sight_range_tiles(base))                  # per-troop aggro radius, TILES (from the KB)
    deploy_time = 0.0 if kind == "spell" else 1.0             # troops/buildings take ~1s to appear; spells use spell_delay
    hit_dmg = dps * hit                                        # DPS delivered as one discrete hit every `hit` seconds
    ct = db.crown_tower_damage(base)                           # troops with a reduced crown value (Miner) hit towers softer
    tower_hit_dmg = float(ct) * sc if ct is not None else hit_dmg
    radius = 0.96 if "tank" in flags else (0.45 if count >= 3 else 0.64)   # collision radius, TILES
    spawn_spec, spawn_count = None, 0
    if base == "royal_delivery":                              # RD drops ONE shielded Royal Recruit where it lands
        spawn_spec = build_spec(db, "royal_recruits", level)  # single-recruit combat stats (the Royal Recruits card)
        spawn_count = 1
    return CardSpec(
        key=key, base=base, kind=kind, elixir=elixir, hp=hp, dps=dps, reach=reach, speed=speed,
        count=count, flying=db.is_flying(base), attacks_air=db.attacks_air(base),
        splash=db.has_splash(base), building_only=building_only, siege=siege,
        deploy_anywhere=("deploy_anywhere" in flags),
        kamikaze="kamikaze" in flags, lifetime=lifetime,
        spell_radius=spell_radius, spell_dmg=dmg,
        spell_tower_dmg=tower_dmg, spell_delay=spell_delay,
        rolls=rolls, ground_only=ground_only,
        knockback=(_LOG_KNOCKBACK if rolls else 0.0), roll_len=(_LOG_ROLL_LEN if rolls else 0.0),
        hit_speed=hit, hit_dmg=hit_dmg, tower_hit_dmg=tower_hit_dmg, deploy_time=deploy_time, radius=radius,
        slows=("slow" in flags), stuns=("stun" in flags), freezes=("freeze" in flags),
        level=int(level), sight=sight, pulse_dmg=p_dmg, pulse_r=p_r, pulse_stun=p_stun, pulse_interval=p_int,
        spawn_spec=spawn_spec, spawn_count=spawn_count,
        shield_hp=(hp * _SHIELD_FRAC if "shield" in flags else 0.0),
        damage_reduction=dmg_reduc,
        pulls=pulls,
        pull_radius=(_TORNADO_RADIUS if pulls else 0.0),
        pull_duration=(_TORNADO_DURATION if pulls else 0.0),
        gen_every=gen_every)


@dataclass
class Unit:
    spec: CardSpec
    team: int
    x: float
    y: float
    hp: float
    age: float = 0.0
    reach_extra: float = 0.0     # siege sees far (big engage range) even if it hits from reach
    target: object = None        # locked target (Unit or Tower) -- commitment; re-acquired when it dies / leashes
    cooldown: float = 0.0        # time until this unit's next discrete hit
    deploy_left: float = 0.0     # deploy delay remaining (can't act while > 0)
    slow_left: float = 0.0       # SLOW status timer (halved move + attack speed)
    stun_left: float = 0.0       # STUN / FREEZE status timer (can't act while > 0)
    pulse_cd: float = 0.0        # Evo Tesla: time until its next area-shock pulse
    shield_left: float = 0.0     # SHIELD pool remaining -- absorbs damage before hp (init from spec.shield_hp)
    dmg_mult: float = 1.0        # per-unit damage multiplier (Royal Chef pancake buff; 1.0 = normal)
    attacking: bool = False      # engaged (target in reach) this step -> Evo Knight's damage reduction is OFF
    gen_count: int = 0           # elixir units this pump has already paid out (spec.gen_every > 0 only)

    def __post_init__(self):
        self.shield_left = self.spec.shield_hp


@dataclass
class Tower:
    x: float
    y: float
    hp: float
    max_hp: float
    king: bool = False
    active: bool = True
    alive: bool = True
    # --- tower-troop combat model (discrete single-target hits; stats from the CR wiki) ---
    troop: str = "princess"
    hit_dmg: float = 158.0        # damage per shot (= dps * hit_speed, level-scaled)
    hit_speed: float = 0.8        # seconds between shots
    first_hit: float = 0.8        # delay before the first shot after (re)acquiring a target
    reload_left: float = 0.0      # time until the next shot is ready
    acquired: bool = False        # currently locked onto a target (first-hit bookkeeping)
    ammo: float = 0.0             # Dagger Duchess: daggers left in the loaded clip
    ammo_max: float = 0.0         # clip size (0 = not a Dagger Duchess)
    empty_hit_speed: float = 0.0  # slower cadence once the clip is empty
    ammo_regen_s: float = 0.0     # seconds to reload one dagger while idle
    cook_period: float = 0.0      # Royal Chef: seconds between pancakes (0 = not a Royal Chef)
    cook_left: float = 0.0        # time until the next pancake
    buff_mult: float = 1.0        # pancake buff (~+1 level) applied to HP + damage
    buff_min_frac: float = 0.33   # only feed a troop above this fraction of its max HP


@dataclass
class _Spell:
    team: int
    x: float
    y: float
    spec: CardSpec
    t: float                      # time remaining until it lands


@dataclass
class _Vortex:
    """A LANDED tornado: an active area that pulls enemies to its centre and deals its damage
    spread over the duration (the instant-blast model could never produce the clump synergies
    this deck is built on: clumped troops -> Ice Wizard splash hits everything, centre-Rocket
    hits the whole push)."""
    team: int
    x: float
    y: float
    spec: CardSpec
    left: float                   # active seconds remaining


def _dist(ax, ay, bx, by) -> float:
    """Distance in TILES between two normalised points (the axes have different tile scales)."""
    return math.hypot((ax - bx) * _TILES_X, (ay - by) * _TILES_Y)


tile_dist = _dist          # public alias: reward geometry must measure in tiles too


# Tower-troop stat fallback (Clash Royale Fandom wiki, LEVEL 15) if config omits `tower_troops`/`king_tower`.
# hit_dmg is derived as dps*hit_speed; HP + damage scale by 1.1^(level - my_tower_level).
_DEFAULT_TOWER_TROOPS = {
    "princess":       {"hp": 4424, "dps": 197, "hit_speed": 0.8},
    "dagger_duchess": {"hp": 4013, "dps": 312, "hit_speed": 0.5, "ammo": 8, "empty_dps": 111, "reload_s": 0.9},
    "cannoneer":      {"hp": 3792, "dps": 211, "hit_speed": 2.2},
    "royal_chef":     {"hp": 3918, "dps": 158, "hit_speed": 1.0, "cook_period_s": 30.0,
                        "cook_delay_s": 7.0, "buff_mult": 1.1, "buff_min_frac": 0.33},
}
_DEFAULT_KING_TOWER = {"hp": 7032, "dps": 158, "hit_speed": 1.0}
_DEFAULT_OPP_TOWER_WEIGHTS = {"princess": 6, "dagger_duchess": 2, "cannoneer": 2, "royal_chef": 1}


class SimEngine:
    """One match. Advance with :meth:`advance(dt)`; deploy with :meth:`deploy`."""

    def __init__(self, cfg, db, rng):
        self.cfg = cfg
        self.db = db
        self.rng = rng
        # Tower Troops: per-troop HP + discrete-hit attack (CR wiki, L15). Your side plays my_tower_troop at
        # my_tower_level; the opponent rolls a troop (weighted) + a ladder level per match (see reset()).
        self.tower_ref_level = int(cfg.get("sim", "my_tower_level", default=15))
        self.my_tower_troop = str(cfg.get("sim", "my_tower_troop", default="princess"))
        self.tower_first_hit = float(cfg.get("sim", "tower_first_hit", default=0.8))
        self.tower_troops = dict(cfg.get("sim", "tower_troops", default=None) or _DEFAULT_TOWER_TROOPS)
        self.king_profile = dict(cfg.get("sim", "king_tower", default=None) or _DEFAULT_KING_TOWER)
        self.opp_tower_weights = dict(cfg.get("sim", "opponent_tower_weights", default=None)
                                      or _DEFAULT_OPP_TOWER_WEIGHTS)
        self.tower_range = float(cfg.get("sim", "tower_range", default=7.5))   # tiles
        self.king_range = float(cfg.get("sim", "king_range", default=7.0))     # tiles
        self.regulation = float(cfg.get("sim", "regulation_s", default=180.0))
        self.overtime = float(cfg.get("sim", "overtime_s", default=60.0))
        self.siege_sight = float(cfg.get("sim", "siege_sight", default=11.5))  # X-Bow, tiles
        self.sight_range = float(cfg.get("sim", "sight_tiles", default=5.5))   # troop aggro radius, tiles
        self.slow_factor = float(cfg.get("sim", "slow_factor", default=0.5))   # SLOW -> this x move + attack speed
        self.slow_dur = float(cfg.get("sim", "slow_duration", default=2.0))
        self.stun_dur = float(cfg.get("sim", "stun_duration", default=0.5))
        self.freeze_dur = float(cfg.get("sim", "freeze_duration", default=1.0))
        self.collide = bool(cfg.get("sim", "collision", default=True))         # soft body-block separation
        # BOARD: a tile grid, and the towers are placed FROM IT -- so the two halves are exactly
        # symmetric about the river and the self-play mirror (reflect about y=0.5) is exact. Do NOT
        # reuse `env.my_towers`/`env.enemy_towers` here: those are live SCREEN coordinates and carry
        # the real game's perspective foreshortening.
        board = dict(cfg.get("sim", "board", default=None) or {})
        self.tiles_x = float(board.get("tiles_x", 18.0))
        self.tiles_y = float(board.get("tiles_y", 32.0))
        self.bridge_tiles = list(board.get("bridge_tiles", [3.5, 14.5]))
        pt = list(board.get("princess_tile", [3.5, 6.5]))      # [x from the side wall, y from the back wall]
        kt = list(board.get("king_tile", [9.0, 3.0]))
        configure_board(self.tiles_x, self.tiles_y, self.bridge_tiles)
        px_l, px_r = pt[0] / self.tiles_x, (self.tiles_x - pt[0]) / self.tiles_x
        py, kx, ky = pt[1] / self.tiles_y, kt[0] / self.tiles_x, kt[1] / self.tiles_y
        self._anchors = {                                      # [L princess, R princess, king]
            1: [[px_l, py], [px_r, py], [kx, ky]],                          # enemy: TOP
            0: [[px_l, 1.0 - py], [px_r, 1.0 - py], [kx, 1.0 - ky]],        # you: BOTTOM (mirrored)
        }
        self.lanes = tuple(float(b) / self.tiles_x for b in self.bridge_tiles)   # bridge lane centres, normalised x
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        self.t = 0.0
        self.done = False
        self.outcome: Optional[str] = None       # from team 0's view: win | loss | draw
        self.units: List[Unit] = []
        self.spells: List[_Spell] = []
        self.vortices: List[_Vortex] = []        # landed tornadoes (active pull areas)
        self.elixir = {0: 5.0, 1: 5.0}
        self.towers = {}
        # Your side always plays your equipped troop at your level; the opponent's tower troop + level are
        # rolled per match (princess most common). Both of a side's princess towers share its troop + level.
        self.tower_setup = {0: (self.my_tower_troop, self.tower_ref_level), 1: self._roll_opponent_tower()}
        for team in (0, 1):
            a = self._anchors[team]
            troop, lvl = self.tower_setup[team]
            self.towers[team] = [
                self._make_tower(a[0][0], a[0][1], troop, lvl, king=False),
                self._make_tower(a[1][0], a[1][1], troop, lvl, king=False),
                self._make_tower(a[2][0], a[2][1], "king", lvl, king=True),
            ]
        self.chip = {0: 0.0, 1: 0.0}             # enemy-tower HP you removed this step (both views)
        self.kills = {0: 0, 1: 0}
        self.last_deploy = {0: None, 1: None}    # (spec, x, y, t) of each team's most recent deploy

    def _make_tower(self, x: float, y: float, troop: str, level: int, king: bool) -> Tower:
        """Build one Tower from a tower-troop profile (config/wiki stats at my_tower_level), scaling HP +
        damage by CR's 1.1^(level-ref) so an opponent's rolled level tunes its tower like its cards do."""
        prof = self.king_profile if king else self.tower_troops.get(troop, self.tower_troops.get("princess", {}))
        sc = 1.1 ** (int(level) - self.tower_ref_level)
        hp = float(prof.get("hp", 4424.0)) * sc
        hit_speed = float(prof.get("hit_speed", 0.8))
        dps = float(prof.get("dps", 197.0))
        tw = Tower(x, y, hp, hp, king=king, active=(not king),
                   troop=("king" if king else troop),
                   hit_dmg=dps * hit_speed * sc, hit_speed=hit_speed,
                   first_hit=min(hit_speed, self.tower_first_hit))
        ammo = float(prof.get("ammo", 0.0))                        # Dagger Duchess: loaded-dagger opening burst
        if ammo > 0.0:
            empty_dps = float(prof.get("empty_dps", dps)) or dps
            tw.ammo = tw.ammo_max = ammo
            tw.empty_hit_speed = dps * hit_speed / empty_dps      # slower cadence once the clip is empty
            tw.ammo_regen_s = float(prof.get("reload_s", hit_speed))
        cook = float(prof.get("cook_period_s", 0.0))              # Royal Chef: periodic +1-level ally buff
        if cook > 0.0 and not king:
            tw.cook_period = cook
            tw.cook_left = float(prof.get("cook_delay_s", 7.0))
            tw.buff_mult = float(prof.get("buff_mult", 1.1))
            tw.buff_min_frac = float(prof.get("buff_min_frac", 0.33))
        return tw

    def _roll_opponent_tower(self) -> "tuple[str, int]":
        """Sample the opponent's tower troop (weighted, princess most common) + a ladder level (enemy_levels)."""
        w = self.opp_tower_weights or {"princess": 1}
        troops = list(w.keys())
        weights = [max(0.0, float(w[t])) for t in troops]
        if sum(weights) <= 0.0:
            troops, weights = ["princess"], [1.0]
        troop = self.rng.choices(troops, weights=weights, k=1)[0]
        lv = list(self.cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16]))
        lw = list(self.cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1]))
        level = self.rng.choices(lv, weights=lw, k=1)[0]
        return troop, int(level)

    def elixir_rate(self) -> float:
        if self.t >= self.regulation:
            return 1.0 / 0.93                     # triple (overtime)
        if self.t >= self.regulation - 60.0:
            return 1.0 / 1.4                       # double
        return 1.0 / 2.8                          # single

    def can_afford(self, team: int, spec: CardSpec) -> bool:
        return self.elixir[team] >= spec.elixir

    def deploy(self, team: int, spec: CardSpec, x: float, y: float) -> bool:
        if self.done or not self.can_afford(team, spec):
            return False
        self.elixir[team] -= spec.elixir
        self.last_deploy[team] = (spec, x, y, self.t)
        if spec.kind == "spell":
            delay = spec.spell_delay
            if spec.base == "rocket":                      # rocket FLIGHT TIME grows with distance from its
                oy = 1.0 if team == 0 else 0.0             # launcher -> the policy must LEAD a marching target
                delay = 0.4 + _dist(x, y, 0.5, oy) / _TILES_Y   # (live-parity physics; ~1.4s at max range)
            self.spells.append(_Spell(team, x, y, spec, delay))
            return True
        n = max(1, spec.count)
        # TILE SNAP: troops/buildings land on a tile centre, as in the real game (spells stay
        # continuous -- they are aimed, not placed).
        x = (math.floor(x * _TILES_X) + 0.5) / _TILES_X
        y = (math.floor(y * _TILES_Y) + 0.5) / _TILES_Y
        # SWARM FORMATION. A multi-unit card spawns its members in a compact cluster CENTRED on the
        # drop point, spread by unit size -- so each body is separately killable, blockable and
        # splash-able, which is the whole point of a swarm.
        # (Was: `ox = x + off` then `Unit(..., x + ox)` = x DOUBLED. A swarm asked for (0.30, 0.60)
        #  spawned at (0.58-0.62, 0.97) and one asked for the centre landed every member on the
        #  (0.97, 0.97) clamp corner. Every multi-unit card in the game was affected -- your own
        #  Skeletons, and the opponents' Archers / Barbarians / Minions / Minion Horde / Skeleton
        #  Army -- and for team 1 the doubling threw their swarms across the river into YOUR half.)
        cols = int(math.ceil(math.sqrt(n)))
        step = max(0.4, spec.radius * 2.2)            # touching-but-not-overlapping bodies (TILES)
        # Lay the members out row by row (each row centred), then subtract the cluster's mean so the
        # formation is centred on the drop point EXACTLY -- a partly-filled last row (3 bodies in a
        # 2x2, the Skeletons case) would otherwise bias the whole squad up and to one side.
        offs = [((i % cols) - (min(cols, n - (i // cols) * cols) - 1) / 2.0, float(i // cols))
                for i in range(n)]
        mx = sum(o[0] for o in offs) / n
        my = sum(o[1] for o in offs) / n
        for ox, oy in offs:
            dx = (ox - mx) * step / _TILES_X             # tiles -> normalised, per axis
            dy = (oy - my) * step / _TILES_Y
            u = Unit(spec, team, min(max(x + dx, 0.03), 0.97), min(max(y + dy, 0.03), 0.97), spec.hp)
            u.deploy_left = spec.deploy_time              # ~1s before it can act (you can't instant-block)
            u.pulse_cd = spec.pulse_interval              # Evo Tesla: first area-shock after one interval
            if spec.siege:
                u.reach_extra = self.siege_sight - spec.reach
            self.units.append(u)
        return True

    # -- per-tick simulation ----------------------------------------------
    def _enemy_towers(self, team: int) -> List[Tower]:
        return [t for t in self.towers[1 - team] if t.alive]

    def _valid_foe(self, u: Unit, e: Unit) -> bool:
        return e.hp > 0 and (not e.spec.flying or u.spec.attacks_air or u.spec.flying)

    def _acquire(self, u: Unit):
        """(kind, ref) this unit heads for -- with target COMMITMENT + an aggro/sight range: real CR units
        lock onto a target and only notice enemy UNITS within sight, otherwise they march at the tower.
        Building-only troops (Miner / Hog) ignore troops and always go for the tower."""
        towers = self._enemy_towers(u.team)
        if u.spec.building_only:
            tw = min(towers, key=lambda t: _dist(u.x, u.y, t.x, t.y)) if towers else None
            u.target = tw
            return ("tower", tw) if tw else (None, None)
        sight = self.siege_sight if u.spec.siege else (u.spec.sight or self.sight_range)
        t = u.target                                          # stay COMMITTED to a live unit target (with a leash)
        if isinstance(t, Unit) and t.hp > 0 and self._valid_foe(u, t) \
                and _dist(u.x, u.y, t.x, t.y) <= sight * 1.8:
            return ("unit", t)
        foes = [e for e in self.units if e.team != u.team and self._valid_foe(u, e)
                and _dist(u.x, u.y, e.x, e.y) <= sight]
        if foes:                                              # an enemy unit is within aggro range -> engage nearest
            e = min(foes, key=lambda e: _dist(u.x, u.y, e.x, e.y))
            u.target = e
            return ("unit", e)
        if towers:                                            # nothing in sight -> march at the nearest tower
            tw = min(towers, key=lambda t: _dist(u.x, u.y, t.x, t.y))
            u.target = tw
            return ("tower", tw)
        u.target = None
        return (None, None)

    def _move_toward(self, u: Unit, tx: float, ty: float, dt: float, spd_mult: float = 1.0) -> None:
        # ground units cross the river only at a bridge
        if not u.spec.flying and (u.y - _RIVER) * (ty - _RIVER) < 0:
            bx = min(_BRIDGES, key=lambda b: abs(u.x - b))
            if abs(u.x - bx) * _TILES_X > 0.4:               # not yet in the bridge lane (tiles)
                tx, ty = bx, _RIVER
            else:
                tx, ty = bx, ty                              # aligned with the bridge -> cross straight
        # step in TILES, then convert back per axis (one normalised unit != one tile on both axes)
        dxt, dyt = (tx - u.x) * _TILES_X, (ty - u.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d < 1e-6:
            return
        step = min(u.spec.speed * spd_mult * dt, d)
        u.x += (dxt / d) * step / _TILES_X
        u.y += (dyt / d) * step / _TILES_Y

    def _separate(self) -> None:
        """Soft collision so units can't stack -- approximate body-blocking: a wall of troops physically
        holds up a tank because it can't pass straight through them. Gentle (push apart by the overlap);
        buildings + still-spawning units don't move; air and ground don't collide."""
        us = [u for u in self.units if u.hp > 0 and u.deploy_left <= 0]
        for i in range(len(us)):
            a = us[i]
            for j in range(i + 1, len(us)):
                b = us[j]
                if a.spec.flying != b.spec.flying:
                    continue
                dx, dy = (a.x - b.x) * _TILES_X, (a.y - b.y) * _TILES_Y   # TILES
                d = math.hypot(dx, dy)
                mind = a.spec.radius + b.spec.radius
                if d >= mind or d <= 1e-6:
                    continue
                overlap = mind - d
                ux, uy = dx / d, dy / d
                am = 0.0 if a.spec.kind == "building" else 1.0
                bm = 0.0 if b.spec.kind == "building" else 1.0
                s = am + bm
                if s <= 0:
                    continue
                px, py = ux * overlap / _TILES_X, uy * overlap / _TILES_Y  # back to normalised, per axis
                a.x = min(max(a.x + px * (am / s), 0.03), 0.97)
                a.y = min(max(a.y + py * (am / s), 0.03), 0.97)
                b.x = min(max(b.x - px * (bm / s), 0.03), 0.97)
                b.y = min(max(b.y - py * (bm / s), 0.03), 0.97)

    def advance(self, dt: float) -> None:
        if self.done:
            return
        self.t += dt
        self.chip = {0: 0.0, 1: 0.0}
        self.kills = {0: 0, 1: 0}
        # elixir
        rate = self.elixir_rate()
        for team in (0, 1):
            self.elixir[team] = min(10.0, self.elixir[team] + rate * dt)
        # ELIXIR COLLECTOR: an alive pump GENERATES +1 elixir for its OWNER every spec.gen_every seconds
        # (after its deploy delay). Killing it early denies the remaining production -- that real economy
        # is what makes rocketing a fresh pump genuinely valuable, not just reward-shaped.
        for u in self.units:
            if u.spec.gen_every > 0 and u.deploy_left <= 0:
                n = int(max(0.0, u.age - u.spec.deploy_time) // u.spec.gen_every)
                if n > u.gen_count:
                    self.elixir[u.team] = min(10.0, self.elixir[u.team] + (n - u.gen_count))
                    u.gen_count = n
        # spells land
        landed = []
        for s in self.spells:
            s.t -= dt
            if s.t <= 0:
                self._resolve_spell(s)
                landed.append(s)
        for s in landed:
            self.spells.remove(s)
        # active tornado vortices: pull enemies to the centre + deal damage over the duration
        for v in list(self.vortices):
            self._tick_vortex(v, dt)
            v.left -= dt
            if v.left <= 0:
                self.vortices.remove(v)
        # units act (deploy delay -> stun/freeze -> slow-aware move + discrete cooldown attacks)
        for u in list(self.units):
            if u.hp <= 0:
                continue
            u.age += dt
            u.cooldown = max(0.0, u.cooldown - dt)
            u.attacking = False                             # default; set True only when engaged (target in reach)
            if u.deploy_left > 0:                            # still spawning -> can't act yet (~1s)
                u.deploy_left -= dt
                continue
            if u.stun_left > 0:                              # stunned / frozen -> can't act
                u.stun_left = max(0.0, u.stun_left - dt)
                continue
            if u.spec.pulse_interval > 0:                    # Evo Tesla area-shock: periodic AoE damage + stun
                u.pulse_cd -= dt
                if u.pulse_cd <= 0:
                    self._pulse(u)
                    u.pulse_cd = u.spec.pulse_interval
            spd = self.slow_factor if u.slow_left > 0 else 1.0
            if u.slow_left > 0:
                u.slow_left = max(0.0, u.slow_left - dt)
            kind, ref = self._acquire(u)
            if ref is None:
                continue
            rx, ry = (ref.x, ref.y)
            reach = u.spec.reach + u.reach_extra
            if _dist(u.x, u.y, rx, ry) <= reach + _REACH_SLOP:
                u.attacking = True                          # engaged (in reach) -> Evo Knight's damage reduction is OFF
                if u.cooldown <= 0:                          # one discrete hit, then wait hit_speed (slow -> longer)
                    self._attack(u, kind, ref)
                    u.cooldown = u.spec.hit_speed / spd
                    if u.spec.kamikaze:
                        u.hp = 0.0
            elif u.spec.kind != "building":                  # buildings are stationary
                self._move_toward(u, rx, ry, dt, spd)
        if self.collide:
            self._separate()
        # towers fire (+ Royal Chef cooks periodic ally buffs)
        for team in (0, 1):
            for tw in self.towers[team]:
                if not tw.alive:
                    continue
                if tw.active or not tw.king:
                    self._tower_fire(team, tw, dt)
                if tw.cook_period > 0.0:
                    self._tower_cook(team, tw, dt)
        # cull dead + expired
        alive = []
        for u in self.units:
            if u.hp <= 0:
                self.kills[1 - u.team] += 1                  # the other team gets the kill credit
                continue
            if u.spec.lifetime is not None and u.age >= u.spec.lifetime:
                continue
            alive.append(u)
        self.units = alive
        self._check_end()

    def _hurt(self, u: "Unit", dmg: float) -> None:
        """Apply damage to a UNIT. Two defensive mechanics can reduce it first:
        - DAMAGE REDUCTION while NOT attacking (Evo Knight -- 60% less from ALL sources whenever it isn't
          engaged; it drops the moment it deals a hit, tracked by `u.attacking`). NOT a numerical HP pool.
        - a SHIELD pool (Royal Recruits / Guards ...) that absorbs the WHOLE hit; like real Clash Royale the
          OVERFLOW that breaks the shield is DISCARDED, not carried to hp (a big hit only STRIPS the shield).
        A unit with neither behaves exactly as `u.hp -= dmg`."""
        if u.spec.damage_reduction > 0.0 and not u.attacking:
            dmg *= (1.0 - u.spec.damage_reduction)           # Evo Knight: 60% less while moving/approaching
        if u.shield_left > 0.0:
            u.shield_left = max(0.0, u.shield_left - dmg)
            return
        u.hp -= dmg

    def _attack(self, u: Unit, kind: str, ref) -> None:
        dmg = u.spec.hit_dmg * u.dmg_mult                    # one discrete hit (DPS x hit_speed; x Royal Chef buff)
        if kind == "tower":
            # crown towers take the REDUCED per-hit value when the card has one (Miner) -- real CR's
            # crown-tower damage reduction; most troops have no reduced value so this equals hit_dmg
            self._damage_tower(ref, u.spec.tower_hit_dmg * u.dmg_mult, u.team)
            return
        self._hurt(ref, dmg)
        self._apply_status(u.spec, ref)
        if u.spec.splash:
            for e in self.units:
                if e.team != u.team and e is not ref and _dist(e.x, e.y, ref.x, ref.y) <= _SPLASH_R:
                    self._hurt(e, dmg)
                    self._apply_status(u.spec, e)

    def _apply_status(self, spec: CardSpec, e: Unit) -> None:
        """Apply a hitter's/spell's crowd-control to a struck ground/air unit."""
        if spec.freezes:
            e.stun_left = max(e.stun_left, self.freeze_dur)
        elif spec.stuns:
            e.stun_left = max(e.stun_left, self.stun_dur)
        if spec.slows:
            e.slow_left = max(e.slow_left, self.slow_dur)

    def _pulse(self, u: Unit) -> None:
        """Evo Tesla area-shock: damage + STUN every enemy within pulse_r of the tower."""
        for e in self.units:
            if e.team == u.team or e.hp <= 0 or e.deploy_left > 0:
                continue
            if _dist(e.x, e.y, u.x, u.y) <= u.spec.pulse_r:
                self._hurt(e, u.spec.pulse_dmg)
                if u.spec.pulse_stun > 0:
                    e.stun_left = max(e.stun_left, u.spec.pulse_stun)

    def _tower_fire(self, team: int, tw: Tower, dt: float) -> None:
        """DISCRETE single-target tower shots. Cadence + damage come from the tower troop; Dagger Duchess
        bursts through a loaded dagger clip (fast) then fires slower until it reloads while it has no target."""
        rng = self.king_range if tw.king else self.tower_range
        foes = [e for e in self.units if e.team != team and e.hp > 0 and e.deploy_left <= 0.0
                and _dist(tw.x, tw.y, e.x, e.y) <= rng]
        if not foes:
            tw.acquired = False
            if tw.ammo_max > 0.0:                                # reload the dagger clip while there's no target
                tw.ammo = min(tw.ammo_max, tw.ammo + dt / tw.ammo_regen_s)
            return
        if not tw.acquired:                                     # first shot after (re)acquiring is delayed
            tw.acquired = True
            tw.reload_left = tw.first_hit
        tw.reload_left -= dt
        if tw.reload_left > 0.0:
            return
        tgt = min(foes, key=lambda e: _dist(tw.x, tw.y, e.x, e.y))
        self._hurt(tgt, tw.hit_dmg)                             # towers are single-target (no splash)
        # accumulate (+=) rather than reset (=) the cooldown so the fractional remainder carries and the
        # AVERAGE cadence stays exact on the 0.1s physics grid (a reset would round every shot up a tick).
        if tw.ammo_max > 0.0 and tw.ammo >= 1.0:                # Dagger Duchess: fast while the clip has daggers
            tw.ammo -= 1.0
            tw.reload_left += tw.hit_speed
        elif tw.ammo_max > 0.0:                                 # ...then the slower empty cadence
            tw.reload_left += tw.empty_hit_speed
        else:
            tw.reload_left += tw.hit_speed

    def _tower_cook(self, team: int, tw: Tower, dt: float) -> None:
        """Royal Chef: every cook_period, throw a pancake to the FRIENDLY troop with the most HP (above
        buff_min_frac of its max), raising it ~1 level (HP + damage x buff_mult). A coarse model of the
        real cooking ability -- enough that a Royal Chef opponent's pushes hit harder."""
        tw.cook_left -= dt
        if tw.cook_left > 0.0:
            return
        tw.cook_left = tw.cook_period
        cands = [u for u in self.units if u.team == team and u.deploy_left <= 0.0
                 and u.hp > u.spec.hp * tw.buff_min_frac]
        if not cands:
            return
        u = max(cands, key=lambda e: e.hp)
        u.hp *= tw.buff_mult
        u.dmg_mult *= tw.buff_mult

    def _resolve_spell(self, s: _Spell) -> None:
        if s.spec.rolls:
            self._resolve_roll(s)
            return
        if s.spec.pulls:
            # TORNADO: not a blast -- it becomes an ACTIVE VORTEX (pull + damage spread over the
            # duration). Tiny crown chip only if the cast point itself overlaps a tower.
            self.vortices.append(_Vortex(s.team, s.x, s.y, s.spec, s.spec.pull_duration))
            for tw in self._enemy_towers(s.team):
                if _dist(tw.x, tw.y, s.x, s.y) <= 1.6:        # tiles: the cast point overlaps the tower
                    self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)
            return
        for e in self.units:
            if e.team != s.team and _dist(e.x, e.y, s.x, s.y) <= s.spec.spell_radius:
                self._hurt(e, s.spec.spell_dmg)
                self._apply_status(s.spec, e)                 # Zap/Freeze stun; slow spells
        for tw in self._enemy_towers(s.team):
            if _dist(tw.x, tw.y, s.x, s.y) <= s.spec.spell_radius:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)
        sp = s.spec.spawn_spec                                # Royal Delivery drops a shielded Royal Recruit here
        for i in range(s.spec.spawn_count if sp is not None else 0):
            ox = (0.64 * ((i % 3) - 1) / _TILES_X) if s.spec.spawn_count > 1 else 0.0   # tiles -> normalised
            u = Unit(sp, s.team, min(max(s.x + ox, 0.03), 0.97), min(max(s.y, 0.03), 0.97), sp.hp)
            u.deploy_left = sp.deploy_time
            u.pulse_cd = sp.pulse_interval
            self.units.append(u)

    def _tick_vortex(self, v: _Vortex, dt: float) -> None:
        """One step of an active tornado: drag every enemy unit toward the centre and deal the
        spell's damage SPREAD over the duration. Ground AND air are pulled (tornado hits both);
        heavy tanks ('tank' collision radius) resist at half pull speed. Pulled units are the
        CLUMP the deck's synergies feed on -- Ice Wizard splash and a centre Rocket hit them all."""
        frac = min(dt, max(v.left, 0.0)) / max(v.spec.pull_duration, 1e-6)   # last tick pro-rated -> total == spell_dmg
        step = _TORNADO_PULL * dt                             # tiles this tick
        for e in self.units:
            if e.team == v.team or e.hp <= 0:
                continue
            dxt, dyt = (v.x - e.x) * _TILES_X, (v.y - e.y) * _TILES_Y
            d = math.hypot(dxt, dyt)                          # tiles
            if d > v.spec.pull_radius:
                continue
            self._hurt(e, v.spec.spell_dmg * frac)            # DoT slice of the total damage
            if d > 1e-6:
                pull = step * (0.5 if e.spec.radius >= _TANK_RADIUS else 1.0)   # tanks resist
                if pull >= d:
                    e.x, e.y = v.x, v.y                       # reached the centre (clumped)
                else:
                    e.x += (dxt / d) * pull / _TILES_X        # tiles -> normalised, per axis
                    e.y += (dyt / d) * pull / _TILES_Y

    def _resolve_roll(self, s: _Spell) -> None:
        """A ROLLING spell (The Log): a forward CORRIDOR from the cast point that damages + KNOCKS BACK
        ground troops in its path (no air). 'Forward' = toward the enemy (up for team 0, down for team 1),
        so a defensive Log shoves the enemy push back UP the arena, away from your tower (buying time). A
        Log whose corridor reaches an enemy tower chips it (poor crown damage) -- the bridge cycle-chip."""
        fdir = -1.0 if s.team == 0 else 1.0
        halfw = s.spec.spell_radius                           # tiles
        for e in self.units:
            if e.team == s.team or (s.spec.ground_only and e.spec.flying):
                continue
            dy = (e.y - s.y) * fdir * _TILES_Y                # forward distance along the roll (tiles)
            if -_LOG_BACK_SLOP <= dy <= s.spec.roll_len and abs(e.x - s.x) * _TILES_X <= halfw:
                self._hurt(e, s.spec.spell_dmg)
                e.y += fdir * s.spec.knockback / _TILES_Y     # knock back in the roll direction
        for tw in self._enemy_towers(s.team):
            dy = (tw.y - s.y) * fdir * _TILES_Y
            if -_LOG_BACK_SLOP <= dy <= s.spec.roll_len and abs(tw.x - s.x) * _TILES_X <= halfw:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)

    def _damage_tower(self, tw: Tower, dmg: float, by_team: int) -> None:
        if not tw.alive:
            return
        if tw.king:
            tw.active = True                                 # ANY hit on the king wakes it (Miner / spell chip) -- real CR
        dmg = min(dmg, tw.hp)
        tw.hp -= dmg
        self.chip[by_team] += dmg
        if tw.hp <= 0:
            tw.alive = False
            tw.hp = 0.0
            if not tw.king:                                  # a princess falling activates its king
                self.towers[1 - by_team][2].active = True

    def _check_end(self) -> None:
        for team in (0, 1):
            if not self.towers[team][2].alive:               # king down -> that team loses
                self.done = True
                self.outcome = "loss" if team == 0 else "win"
                return
        if self.t >= self.regulation + self.overtime:
            self.done = True
            self.outcome = self._score_outcome()

    def _score_outcome(self) -> str:
        my_crowns = self.crowns(0)
        op_crowns = self.crowns(1)
        if my_crowns != op_crowns:
            return "win" if my_crowns > op_crowns else "loss"
        # Crowns tied -> CR tiebreak on the LEAST-healthy Crown Tower (lowest HP fraction loses). Fractions,
        # not absolute HP, so asymmetric tower-troop/level max-HP between the two sides stays fair.
        my_min = min((t.hp / t.max_hp for t in self.towers[0] if t.max_hp > 0), default=1.0)
        op_min = min((t.hp / t.max_hp for t in self.towers[1] if t.max_hp > 0), default=1.0)
        if abs(my_min - op_min) < 1e-3:
            return "draw"
        return "win" if op_min < my_min else "loss"

    # -- reward / observation accessors ------------------------------------
    def crowns(self, team: int) -> int:
        return sum(1 for t in self.towers[1 - team] if not t.alive)

    def tower_hp_total(self, team: int) -> float:
        return sum(t.hp for t in self.towers[team])

    def enemy_mass(self, team: int) -> float:
        """Fraction-ish mass of the OPPONENT's units on `team`'s side of the river."""
        m = 0.0
        for u in self.units:
            if u.team != team and ((team == 0 and u.y >= _RIVER) or (team == 1 and u.y <= _RIVER)):
                m += min(1.0, u.hp / 800.0)
        return m
