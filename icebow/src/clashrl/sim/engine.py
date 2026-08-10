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
from dataclasses import dataclass, field, replace
from typing import List, Optional

# --- BOARD GEOMETRY (tiles) -------------------------------------------------------------------
# Set once per process from `sim.board` by SimEngine.__init__ (every env in a process shares one
# config, so module-level is safe and keeps `_dist` / `build_spec` free of an engine reference).
_TILES_X = 18.0
_TILES_Y = 32.0
_BRIDGES = (3.5 / 18.0, 14.5 / 18.0)     # bridge centres, normalised x (tile-derived; set below)
_BRIDGE_HALF = 1.5                       # bridge deck HALF-width in TILES (set by configure_board)


def configure_board(tiles_x: float, tiles_y: float, bridge_tiles, bridge_width: float = 3.0) -> None:
    """Set the tile grid + bridge lanes. Called by SimEngine.__init__ from `sim.board`."""
    global _TILES_X, _TILES_Y, _BRIDGES, _BRIDGE_HALF
    _TILES_X, _TILES_Y = float(tiles_x), float(tiles_y)
    _BRIDGES = tuple(float(b) / _TILES_X for b in bridge_tiles)
    _BRIDGE_HALF = float(bridge_width) / 2.0


# speed word -> TILES/second (CR: medium ~= 1 tile/s; matches the old 0.031 normalised x 32)
_SPEED = {"slow": 0.75, "medium": 1.0, "fast": 1.5, "very_fast": 2.0, None: 1.0}
# attack reach word -> TILES (melee ~1, short ~3, long 5.5)
# Attack reach is now PER CARD (cards.CardDB.attack_range_tiles, from cr-api-data `range`) rather
# than one constant per melee/short/long bucket -- real melee spans 0.5-1.6 tiles.
_REACH_SLOP = 0.6         # tiles of tolerance on "target is in reach"
_TANK_RADIUS = 0.9        # collision radius (tiles) at/above which a unit counts as a heavy tank
# TOWER FOOTPRINTS (half-size, tiles). Towers are BUILDINGS with real bodies -- a princess is 3x3
# tiles and the king 4x4 -- so an attacker must stop OUTSIDE that box. Measuring reach to the tower
# CENTRE (what this engine used to do) let a melee unit walk its whole body inside the tower before
# it would swing.
_PRINCESS_HALF = 1.5
_KING_HALF = 2.0
_TOWER_CLEAR = 0.15       # tiles of daylight left when rounding a tower's shoulder
_RIVER = 0.5              # the board is symmetric about this now that anchors are tile-derived
# MULTI-HIT geometry, in TILES. Neither is published by the wiki, so both are estimates: how far a
# chain bolt will arc to its next target, and how far Firecracker's sparks spray from the impact.
_CHAIN_TILES = 3.0
_SPARK_TILES = 2.5
_SPLASH_R = 1.9           # splash radius, tiles
# The Log (rolling spell): a forward CORRIDOR from the cast point -- ground-only, with knockback.
_LOG_ROLL_LEN = 9.6       # how far forward it rolls (tiles)
_LOG_ROLL_HALFW = 2.2     # corridor half-width (tiles, ~a lane)
_LOG_BACK_SLOP = 1.0      # tiles BEHIND the cast point still caught by the corridor
# KNOCKBACK fallback for a card the wiki says HAS pushback but publishes no range for (Rocket).
# 1 tile is Fireball's CURRENT published value (2/8/2022 balance: "decreased the Fireball's pushback
# range to 1 tile (from 1.8 tiles)"), so it is the measured value of the nearest documented sibling
# rather than a guess. Per-card values live in the KB as `knockback_tiles`.
_KNOCKBACK_DEFAULT = 1.0


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
    # KNOCKBACK REACHES EVERY TROOP, not just the light ones. The Log's 19/9/2016 entry -- "allowed
    # The Log to push back ALL ground troops. This allowed The Log to reset the charge attacks of the
    # Prince and Dark Prince" -- names the two units the Bowler page lists as knockback-IMMUNE, so
    # vulnerability is per-SPELL, not purely a property of the target.
    knockback_all: bool = False
    # This BODY shrugs off the small-to-medium pushback (Fireball / Giant Snowball / Rocket / Bowler).
    # Curated: CR's underlying mass is not published as a field, only named in prose. See cards.yaml.
    knockback_immune: bool = False
    roll_len: float = 0.0     # forward length of the roll corridor (tiles)
    hit_speed: float = 1.0    # seconds between attacks (discrete hits)
    hit_dmg: float = 0.0      # damage per hit (= dps * hit_speed; preserves average DPS)
    tower_hit_dmg: float = 0.0  # damage per hit vs CROWN TOWERS -- reduced when the KB carries a
                              # crown_tower_damage (Miner's signature nerf); else = hit_dmg. Without
    # RAMP-UP: per-hit damage for stages 1..3 while locked on ONE target (Inferno Tower / Inferno
    # Dragon / Mighty Miner). Empty = flat damage. The ramp resets whenever the target changes.
    dmg_stages: tuple = ()
    stage_time: float = 2.0   # seconds on one target before stepping up a stage
    # DEATH DAMAGE: an area hit centred on the body when it dies (Balloon 240 in 3 tiles, Giant
    # Skeleton 688 in 3, Bomb Tower 222, Ice Golem 84). Published per level by the wiki; the engine
    # previously had the `death_damage` role FLAG but never the number, so these cards died silently
    # -- and for Balloon and Giant Skeleton the death blast is most of what the card is for.
    death_dmg: float = 0.0
    death_radius: float = 0.0
    # PER-CARD crowd control. These were single global constants, so a Freeze (4s) and an Ice Spirit
    # (1.1s) stunned for the same time and every slow was the same strength -- when the published
    # values run from -15% (Evo Firecracker) to -70% (Ram Rider). 0 = fall back to the global.
    stun_dur: float = 0.0
    freeze_dur: float = 0.0
    slow_dur: float = 0.0
    slow_mult: float = 0.0    # movement/attack multiplier while slowed (-30% -> 0.70)
    # CHARGE: a unit that covers `charge_range` tiles unobstructed lands `charge_dmg` on its next
    # hit instead of its normal one, then resets. A Prince connecting for 783 rather than his base
    # hit is effectively a different card, and it is the entire reason a charge is worth blocking.
    charge_dmg: float = 0.0
    charge_range: float = 0.0
    # MULTI-HIT. `hits_per_attack` is ONE number covering four different mechanics, so the KIND is
    # curated per card and each is modelled (and labelled for sim-view) separately:
    #   chain     -- the bolt arcs to further targets      (electro_dragon 3, electro_wizard 2)
    #   boomerang -- the axe flies out AND back, hitting both ways   (executioner 2)
    #   spark     -- sparks spray outward from the impact point      (firecracker 5)
    #   shotgun   -- a cone of pellets; more connect the closer you are (hunter 10)
    # The wiki's `damage` is PER HIT and its `dps` counts only ONE (verified: dps == damage/hit_speed
    # for all of them), so these cards were 2-10x too weak -- a point-blank Hunter should land 10 x 84.
    multi_kind: str = ""
    multi_hits: int = 0
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
    # --- TROOP PRODUCTION (spawners). A spawner does NOT attack towers itself: its damage comes from
    # the units it summons, which is why a Goblin Drill modelled as a plain attacker was hitting the
    # tower directly. Timings are imported from the wiki; the summoned card's identity is curated.
    spawner_spec: Optional["CardSpec"] = None  # the troop this keeps producing
    spawner_count: int = 0        # units per production tick
    spawner_interval: float = 0.0  # seconds between ticks (0 = not a spawner)
    spawner_delay: float = 0.0    # extra wait before the FIRST tick, on top of deploy_time
    spawner_range: Optional[float] = None  # PROXIMITY GATE in tiles: only tick while an enemy is inside
    spawner_death: int = 0        # burst summoned when the spawner dies or its lifetime expires
    shield_hp: float = 0.0    # SHIELD pool (Royal Recruits / Guards / Dark Prince): absorbs damage before hp
    damage_reduction: float = 0.0  # fraction of incoming damage negated WHILE NOT ATTACKING (Evo Knight = 0.60)
    pulls: bool = False       # TORNADO: an active VORTEX, not an instant blast -- pulls enemies to its centre
    pull_radius: float = 0.0  # vortex effect radius (5.5 tiles -- much wider than a damage spell)
    pull_duration: float = 0.0  # seconds the vortex stays active (damage is spread over this)
    gen_every: float = 0.0    # ELIXIR COLLECTOR: +1 elixir to its OWNER every this many seconds (0 = none)
    river_jump: bool = False  # crosses the river WITHOUT a bridge (Hog/Royal Hogs/Ram Rider/Prince/Dark Prince)
    # --- projectile (0 speed = the hit lands instantly, which is how everything used to work) ---
    proj_speed: float = 0.0   # TILES/second the shot travels
    proj_radius: float = 0.0  # blast radius of the shot in tiles (0 = single target)
    proj_range: float = 0.0   # how far the shot flies (> reach for the piercing shots)
    proj_pierce: bool = False # keeps going past its target (Firecracker rocket / Magic Archer / Bowler)
    # MIXED SQUADS: one card that fields SEVERAL UNIT TYPES AT ONCE, each its own CardSpec carrying
    # its own count. Empty for the ~160 cards that field one body type (including swarms -- 15
    # identical Skeletons stay on the plain `count` path). Only Goblin Gang, Rascals and Goblinstein
    # populate it. Without this the squad took row 0's stats and merely SUMMED the counts, so the
    # Rascal girls fought with the boy's 1940 hp -- ~2.4x the card's real effective HP, in about 1 of
    # every 20 opponent decks.
    components: tuple = ()
    # TOTAL bodies the whole card fields, set only on a component spec (0 = use `count`). Board-value
    # accounting splits a card's elixir across its bodies, and a component's `count` is only ITS OWN
    # share -- so billing by that would charge Rascals 5/1 for the boy PLUS 5/2 each for the girls,
    # i.e. 10 elixir for a 5-elixir card, inflating every position/counterfactual reading.
    squad_count: int = 0


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

# The spec carried by a CROWN TOWER's shot. Towers are not cards, so they have no CardSpec of their
# own -- this is a neutral one: single target, no splash, no status. Only the fields a projectile
# actually reads matter.
_TOWER_SHOT = CardSpec(
    key="tower_shot", base="tower_shot", kind="tower", elixir=0, hp=0.0, dps=0.0, reach=0.0,
    speed=0.0, count=1, flying=False, attacks_air=True, splash=False, building_only=False,
    siege=False, kamikaze=False, lifetime=None, spell_radius=0.0, spell_dmg=0.0,
    spell_tower_dmg=0.0, spell_delay=0.0)


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
    reach = float(db.attack_range_tiles(base))                 # TILES, attacker centre -> target EDGE
    # Move speed: the wiki publishes an exact rating per card ("Very Fast (120)", 60 units = 1 tile/s),
    # imported as `speed_tiles`. The categorical bucket is only a fallback for cards that parse missed.
    speed = db.speed_tiles(base) or _SPEED.get(c.get("speed"), _SPEED["medium"])   # TILES/s
    count = int(c.get("count") or 1)
    building_only = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    siege = "siege" in flags
    # Spell blast radius, live from the wiki (Fireball 2.5, Rocket 2.0, Arrows 3.5, Zap 2.5) -- the old
    # flat 2.9 default was wrong for every one of them.
    spell_radius = float(c.get("radius_tiles") or (3.5 if base == "royal_delivery" else 2.9))
    spell_delay = 3.0 if base == "royal_delivery" else 0.4
    ground_only = kind == "spell" and c.get("attacks") == ["ground"]
    # a ROLLING spell (The Log / Barbarian Barrel) = a forward ground-only CORRIDOR. This used to be
    # derived as "has knockback AND ground_only", which COUPLED two independent facts: Barbarian
    # Barrel still rolls but its pushback was REMOVED on 3/9/2018, so it was being modelled as a
    # POINT BLAST, and adding/removing a knockback flag silently changed whether a spell rolled.
    rolls = kind == "spell" and "rolls" in flags and ground_only
    pulls = kind == "spell" and "pull" in flags               # Tornado: an active pulling vortex
    # PUSHBACK RANGE, sourced per card from the wiki's balance history rather than one constant:
    # The Log 0.7 (7/2/2023, from 1), Giant Snowball 1.8 (6/9/2021, from 1.5), Fireball 1.0
    # (2/8/2022, from 1.8), Barbarian Barrel 0 (REMOVED 3/9/2018). Arrows and Zap publish no
    # pushback range and have no balance entry for one, so they get none -- the Arrows page's
    # "knockback and slow effects" line is stale Strategy prose describing Giant Snowball (Arrows
    # has no slow either), which is why HISTORY is trusted over prose here.
    knockback_tiles = float(c.get("knockback_tiles") or 0.0)
    if knockback_tiles <= 0.0 and "knockback" in flags:
        knockback_tiles = _KNOCKBACK_DEFAULT
    if rolls:
        spell_radius = _LOG_ROLL_HALFW                        # corridor HALF-WIDTH for a rolling spell
    # BUILDING LIFETIME. Precedence: a curated override, then the wiki's own `life` vardefine
    # (imported as `lifetime_s`), then a generic building default. The imported key was NEVER being
    # read -- build_spec looked for `lifetime` while card_import writes `lifetime_s` -- so every
    # building silently took the 40s default: Goblin Drill ran 40s instead of 10, Tesla 40 vs 25,
    # Goblin Cage 40 vs 20. Buildings lived up to 4x too long.
    lifetime = 40.0 if kind == "building" else None
    if c.get("lifetime_s"):
        lifetime = float(c["lifetime_s"])
    if c.get("lifetime"):                                     # curated override wins (Elixir Collector)
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
    radius = float(db.collision_radius_tiles(base))             # body radius, TILES (cr-api-data)
    proj = db.projectile(base) or {}
    spawn_spec, spawn_count = None, 0
    if base == "royal_delivery":                              # RD drops ONE shielded Royal Recruit where it lands
        spawn_spec = build_spec(db, "royal_recruits", level)  # single-recruit combat stats (the Royal Recruits card)
        spawn_count = 1
    # TROOP PRODUCTION. `db.spawner()` merges the wiki timings with the curated unit identity. The
    # guard on `unit != base` stops a self-referential curation from recursing forever, and a
    # missing/unknown unit key degrades to "not a spawner" rather than raising during a match.
    spw = db.spawner(base) or {}
    spawner_spec = None
    if spw and spw.get("unit") and spw["unit"] != base:
        try:
            spawner_spec = build_spec(db, spw["unit"], level)
        except Exception:                                     # noqa: BLE001 - unknown key: not a spawner
            spawner_spec = None
    spec = CardSpec(
        key=key, base=base, kind=kind, elixir=elixir, hp=hp, dps=dps, reach=reach, speed=speed,
        count=count, flying=db.is_flying(base), attacks_air=db.attacks_air(base),
        splash=db.has_splash(base), building_only=building_only, siege=siege,
        deploy_anywhere=("deploy_anywhere" in flags),
        kamikaze=("kamikaze" in flags or bool(db.is_kamikaze(base))), lifetime=lifetime,
        spell_radius=spell_radius, spell_dmg=dmg,
        spell_tower_dmg=tower_dmg, spell_delay=spell_delay,
        rolls=rolls, ground_only=ground_only,
        # PUBLISHED pushback range per card (KB `knockback_tiles`), falling back to the nearest
        # documented sibling for a card that has the effect with no stated range. The old code hard-
        # coded 1.6 tiles for the Log -- its CURRENT value is 0.7 (7/2/2023 balance, down from 1),
        # so a defensive Log was shoving a push 2.3x too far up the arena.
        knockback=knockback_tiles,
        knockback_all=("knockback_all" in flags),
        knockback_immune=("knockback_immune" in flags),
        roll_len=(float(c.get("roll_tiles") or _LOG_ROLL_LEN) if rolls else 0.0),
        hit_speed=hit, hit_dmg=hit_dmg, tower_hit_dmg=tower_hit_dmg, deploy_time=deploy_time, radius=radius,
        dmg_stages=tuple(float(x) * sc for x in (c.get("damage_stages") or ())),
        stage_time=float(c.get("stage_time_s") or 2.0),
        # A card counts as slowing if it publishes EITHER a duration or a strength -- Ram Rider gives
        # a -70% snare with no duration column, so keying only on the duration missed it entirely.
        slows=("slow" in flags or bool(c.get("slow_duration_s")) or bool(c.get("slow_pct"))),
        stuns=("stun" in flags or bool(c.get("stun_duration_s"))),
        freezes=("freeze" in flags or bool(c.get("freeze_duration_s"))),
        level=int(level), sight=sight, pulse_dmg=p_dmg, pulse_r=p_r, pulse_stun=p_stun, pulse_interval=p_int,
        spawn_spec=spawn_spec, spawn_count=spawn_count,
        spawner_spec=spawner_spec,
        spawner_count=(int(spw.get("count") or 1) if spawner_spec is not None else 0),
        spawner_interval=(float(spw.get("interval") or 0.0) if spawner_spec is not None else 0.0),
        spawner_delay=(float(spw.get("delay") or 0.0) if spawner_spec is not None else 0.0),
        spawner_range=(spw.get("range") if spawner_spec is not None else None),
        spawner_death=(int(spw.get("on_death") or 0) if spawner_spec is not None else 0),
        shield_hp=(float(db.shield_hp(base)) * sc if db.shield_hp(base)
                   else (hp * _SHIELD_FRAC if "shield" in flags else 0.0)),
        death_dmg=float(c.get("death_damage") or 0.0) * sc,
        # Most death-damage cards publish a splash radius; a few (Ice Golem) publish the damage but
        # not the radius, and a 0 radius would silently make the blast inert. 2.0 tiles is the modal
        # published value (the range is 1.5-3.0) -- an APPROXIMATION, not a sourced number.
        death_radius=float(c.get("death_radius_tiles")
                           or (2.0 if c.get("death_damage") else 0.0)),
        stun_dur=float(c.get("stun_duration_s") or 0.0),
        freeze_dur=float(c.get("freeze_duration_s") or 0.0),
        slow_dur=float(c.get("slow_duration_s") or 0.0),
        slow_mult=(1.0 - abs(float(c["slow_pct"])) / 100.0) if c.get("slow_pct") else 0.0,
        charge_dmg=float(c.get("charge_damage") or 0.0) * sc,
        charge_range=float(c.get("charge_range") or 0.0),
        multi_kind=str((db.get(base) or {}).get("multi") or ""),
        multi_hits=int(c.get("hits_per_attack") or 0),
        damage_reduction=dmg_reduc,
        pulls=pulls,
        pull_radius=(_TORNADO_RADIUS if pulls else 0.0),
        pull_duration=(_TORNADO_DURATION if pulls else 0.0),
        gen_every=gen_every,
        river_jump=bool(db.river_jump(base)),
        proj_speed=float(proj.get("speed") or 0.0),
        proj_radius=float(proj.get("radius") or 0.0),
        proj_range=float(proj.get("range") or 0.0),
        proj_pierce=bool(proj.get("pierce")))
    # MIXED SQUADS. Each component is the SAME card with its own body swapped in, so it inherits
    # everything the wiki publishes once for the whole card (elixir, splash, collision radius, the
    # crown-tower ratio) and overrides only what its own attributes row states. `damage` here is
    # PER HIT, exactly as in the parent path, so dps is derived rather than trusted.
    comps = c.get("components") or ()
    if kind != "spell" and len(comps) > 1:
        subs = []
        total = sum(max(1, int(cm.get("count") or 1)) for cm in comps)
        for cm in comps:
            c_hp = float(cm.get("hitpoints") or 0.0) * sc
            if c_hp <= 0.0:                                   # a half-resolved squad would field
                subs = []                                     # phantom bodies -- take none of it
                break
            c_hit = float(cm.get("hit_speed") or hit) or 1.0
            c_dmg = float(cm.get("damage") or 0.0) * sc
            atk = cm.get("attacks") or ()
            # Keep the parent's crown-tower RATIO (Miner-style reductions are published once for the
            # card, not per body), defaulting to full damage when it takes none.
            ratio = (tower_hit_dmg / hit_dmg) if hit_dmg else 1.0
            subs.append(replace(
                spec,
                count=max(1, int(cm.get("count") or 1)),
                squad_count=total,
                hp=c_hp, hit_speed=c_hit, hit_dmg=c_dmg, dps=(c_dmg / c_hit),
                tower_hit_dmg=c_dmg * ratio,
                reach=float(cm.get("range_tiles") if cm.get("range_tiles") is not None else reach),
                speed=float(cm.get("speed_tiles") or speed),
                flying=(cm.get("movement") == "air"),
                attacks_air=("air" in atk) if atk else db.attacks_air(base),
                # TARGETING IS PER BODY. Goblinstein carries a card-level `building_targeting` flag
                # that is only true of its Monster -- inheriting it would leave the Doctor unable to
                # shoot troops at all, which is most of what he does.
                building_only=("buildings" in atk) if atk else building_only,
                # The wiki publishes projectile speed in its own units; the KB divides by 60 to get
                # TILES/s (see CardDB.projectile) and this is the same number off the row.
                proj_speed=float(cm.get("projectile_speed") or 0.0) / 60.0,
                # A component never nests further, and its shield is its own body's -- a flat
                # fraction of the parent's HP would hand the Rascal girls the boy's shield.
                components=(),
                shield_hp=(c_hp * _SHIELD_FRAC if "shield" in flags else 0.0)))
        if subs:
            spec = replace(spec, components=tuple(subs))
    return spec


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
    locked: bool = False         # has ENGAGED its target (got in reach) -- a locked unit does not switch
                                 # targets just because something wandered closer; only an aggro RESET frees it
    aggro_reset: bool = False    # set by a stun/freeze, a Log knockback, or being SHOVED out of reach of what
                                 # it was hitting -- consumed by _acquire, which then re-picks from scratch
    gen_count: int = 0           # elixir units this pump has already paid out (spec.gen_every > 0 only)
    spawn_cd: float = 0.0        # time until this spawner's next production tick
    focus_time: float = 0.0      # seconds locked on the CURRENT target -- drives ramp-up damage
    slow_mult: float = 1.0       # movement/attack multiplier from whatever slowed this unit
    charge_dist: float = 0.0     # tiles walked without attacking -- arms the charge bonus

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
    radius: float = _PRINCESS_HALF   # footprint half-size in TILES (princess 3x3, king 4x4)
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


@dataclass
class Projectile:
    """A shot IN FLIGHT. Attacks used to land instantly, which is wrong in two ways that matter:
    a Mortar shell (300 = 5 tiles/s) took the same zero time to arrive as a Musketeer bullet
    (1000 = 16.7 tiles/s), and area shots could never be walked out of.

    Two flight models, chosen by whether the shot has a blast radius -- which is exactly how the
    game behaves:
      * radius == 0  -> a TRACKING shot. It follows its target and cannot miss, but FIZZLES if the
                        target dies mid-flight (the damage is simply never dealt).
      * radius >  0  -> an AREA shot at the ground POINT the target occupied when it was fired.
                        It explodes there whatever happens, so a push that keeps moving walks out
                        of it -- the reason Mortar and Bomber miss fast troops.
    `pierce` shots (Firecracker's rocket, Magic Archer, Executioner's axe, Bowler's boulder) keep
    travelling their full projectile_range along the launch heading, hitting each enemy once.
    """
    label: str                    # "<card>_projectile" / "<tower troop>_projectile" (for the debugger)
    team: int
    x: float
    y: float
    tx: float                     # aim point (area shots) -- updated each tick for tracking shots
    ty: float
    target: object                # intended Unit/Tower; None once it no longer matters
    spec: CardSpec                # the FIRING card (splash flag + status effects it applies)
    dmg: float
    tower_dmg: float
    radius: float                 # blast radius in TILES (0 = single target)
    speed: float                  # TILES/second
    left: float                   # TILES of flight remaining (piercing shots fly their full range)
    ground_only: bool = False     # some shots cannot touch air (the KB's `attacks` list says so)
    pierce: bool = False
    hit: set = field(default_factory=set)   # ids already damaged by a piercing shot
    ox: float = 0.0            # where it was fired from -- the BOOMERANG flies back to here
    oy: float = 0.0
    returning: bool = False    # on the return leg (Executioner's axe hits again on the way back)


def _dist(ax, ay, bx, by) -> float:
    """Distance in TILES between two normalised points (the axes have different tile scales)."""
    return math.hypot((ax - bx) * _TILES_X, (ay - by) * _TILES_Y)


tile_dist = _dist          # public alias: reward geometry must measure in tiles too


def _clamp_xy(x: float, y: float, r: float):
    """Keep a body of radius ``r`` TILES inside the arena walls.

    Per AXIS, because one normalised unit is 18 tiles across but 32 up -- the old flat
    `clamp(v, 0.03, 0.97)` meant 0.54 tiles of margin in x but 0.96 in y, which is wider than the
    strip behind the king tower and left a troop placed there permanently clipping it.
    """
    mx, my = r / _TILES_X, r / _TILES_Y
    return min(max(x, mx), 1.0 - mx), min(max(y, my), 1.0 - my)


def _body_radius(ref) -> float:
    """Hitbox radius (tiles) of a Unit or a Tower."""
    spec = getattr(ref, "spec", None)
    return float(spec.radius) if spec is not None else float(getattr(ref, "radius", 0.0))


def _gap(ax: float, ay: float, ref) -> float:
    """Distance in TILES from (ax, ay) to ``ref``'s hitbox EDGE.

    CR measures attack + aggro range from the attacker's CENTRE to the TARGET'S HITBOX EDGE, so a
    bigger target is engaged from further out and a melee unit stops clear of a tower instead of
    standing inside it. Clamped at 0 for a point already inside the body.
    """
    return max(0.0, _dist(ax, ay, ref.x, ref.y) - _body_radius(ref))


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
        # Crown-tower shot speed, TILES/s. Tower troops are not cards, so the wiki's per-card
        # projectile table does not cover them; 10 t/s matches the Archers-class arrow (600 game
        # units / 60) the Princess Tower fires.
        self.tower_proj_speed = float(cfg.get("sim", "tower_projectile_tiles_s", default=10.0))
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
        self.bridge_width = float(board.get("bridge_width_tiles", 3.0))
        pt = list(board.get("princess_tile", [3.5, 6.5]))      # [x from the side wall, y from the back wall]
        kt = list(board.get("king_tile", [9.0, 3.0]))
        configure_board(self.tiles_x, self.tiles_y, self.bridge_tiles, self.bridge_width)
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
        self.projectiles: List[Projectile] = []  # shots in flight (travel time is real)
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
                   radius=(_KING_HALF if king else _PRINCESS_HALF),
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
        """Elixir per second. FOUR phases, not three -- overtime does NOT start at triple:
             0 s .. reg-60      single   (2.8 s/elixir)
             reg-60 .. reg      DOUBLE   -- the last minute of regulation
             reg .. end-60      DOUBLE   -- overtime CONTINUES at 2x for its first minute
             end-60 .. end      TRIPLE   (0.93 s/elixir) -- only the LAST minute of overtime
        This used to flip to triple the instant regulation ended, handing both sides a third more
        elixir for a whole minute that in the real game is still double -- and overtime is exactly
        where a 6-cost win condition finally becomes affordable, so the phase the policy learns to
        bank for was mistimed by 60 s."""
        triple_at = self.regulation + max(0.0, self.overtime - 60.0)
        if self.t >= triple_at:
            return 1.0 / 0.93                     # triple: last minute of overtime only
        if self.t >= self.regulation - 60.0:
            return 1.0 / 1.4                       # double: last minute of regulation THROUGH overtime
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
        # MIXED SQUAD: each unit type gets its OWN ROW, ordered SHORTEST ATTACK RANGE FIRST so the
        # melee bodies stand between the enemy and the ranged ones. That single rule reproduces all
        # three real formations -- Rascal boy ahead of the girls, Goblins ahead of the Spear
        # Goblins, Goblinstein's Monster ahead of the Doctor -- without hardcoding any of them, and
        # it is what makes the squad's shape (not just its stats) worth playing around.
        if spec.components:
            fwd = -1.0 if team == 0 else 1.0                  # team 0 attacks toward y = 0
            rows = sorted(spec.components, key=lambda s: s.reach)
            for ri, sub in enumerate(rows):
                m = max(1, sub.count)
                step = max(0.4, sub.radius * 2.2)
                dy = ((len(rows) - 1) / 2.0 - ri) * step * fwd
                for k in range(m):
                    dx = (k - (m - 1) / 2.0) * step
                    cx, cy = _clamp_xy(x + dx / _TILES_X, y + dy / _TILES_Y, sub.radius)
                    self._place(sub, team, cx, cy)
            return True
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
            cx, cy = _clamp_xy(x + dx, y + dy, spec.radius)
            self._place(spec, team, cx, cy)
        return True

    def _place(self, spec: CardSpec, team: int, cx: float, cy: float) -> None:
        """Put ONE body on the board, already positioned. Shared by the swarm and mixed-squad paths."""
        u = Unit(spec, team, cx, cy, spec.hp)
        u.deploy_left = spec.deploy_time              # ~1s before it can act (you can't instant-block)
        u.pulse_cd = spec.pulse_interval              # Evo Tesla: first area-shock after one interval
        # A spawner's FIRST production tick waits its own spawn delay on top of the deploy delay
        # (Goblin Hut 0.5s, Goblin Drill 1s), so it cannot summon the instant it lands.
        u.spawn_cd = spec.spawner_delay if spec.spawner_interval > 0.0 else 0.0
        if spec.siege:
            u.reach_extra = self.siege_sight - spec.reach
        self.units.append(u)

    # -- per-tick simulation ----------------------------------------------
    def _enemy_towers(self, team: int) -> List[Tower]:
        return [t for t in self.towers[1 - team] if t.alive]

    def _valid_foe(self, u: Unit, e: Unit) -> bool:
        return e.hp > 0 and (not e.spec.flying or u.spec.attacks_air or u.spec.flying)

    def _acquire(self, u: Unit):
        """(kind, ref) this unit heads for.

        Real CR targeting is STICKY, and stickier still once a unit is actually swinging:

        * A unit that has ENGAGED its target (``u.locked``) keeps it. Dropping a defender next to a
          troop that is already hitting your tower does NOT make it turn round -- only an aggro
          RESET does (see ``u.aggro_reset``: stuns/freezes, a Log knockback, or being shoved out of
          reach by a body spawned between it and its target).
        * A unit still WALKING re-evaluates, but a new enemy only steals aggro if it is genuinely
          CLOSER than whatever the unit is already heading for. This is what stops the old bug where
          a defender parked BEHIND the princess tower dragged an attacker past the tower to reach
          it -- the tower is nearer, so the attacker hits the tower.
        * Building-only troops (Miner / Hog) ignore troops entirely and always go for the tower.

        All ranges are measured to the target's hitbox EDGE (:func:`_gap`), so a big body is noticed
        and engaged from further out than a skeleton standing in the same spot."""
        towers = self._enemy_towers(u.team)
        if u.spec.building_only:
            # BUILDING-TARGETERS (Hog Rider, Royal Hogs, Battle Ram, Ram Rider, Miner...) ignore
            # TROOPS -- but they emphatically do not ignore BUILDINGS. The old code looked at crown
            # towers ONLY, so a Tesla or Cannon dropped in the lane was invisible and the wincon
            # walked straight past it into the tower. That deleted the most important defensive play
            # in the game: you could not PULL a wincon with a building, which is the entire reason
            # defensive buildings exist. `interactions.py` already predicted the real behaviour
            # ("nearest of {building unit, tower}"), so the policy's OBSERVATION disagreed with the
            # PHYSICS -- it was being shown a pull that never happened, which is a good way to never
            # learn to answer a wincon with a building.
            #
            # Re-evaluated every tick WHILE TRAVELLING, so a building placed into its path steals it
            # mid-run. Once it is actually swinging (u.locked) it commits, and only an aggro reset
            # (stun / freeze) breaks that -- same rule as every other unit.
            if u.aggro_reset:
                u.aggro_reset = False
                u.locked = False
                u.target = None
            t = u.target
            if u.locked:
                if isinstance(t, Unit) and t.hp > 0 and t.team != u.team \
                        and t.spec.kind == "building":
                    return ("unit", t)
                if isinstance(t, Tower) and t.alive and t in towers:
                    return ("tower", t)
                u.locked = False                              # target died -> re-pick
            best, best_gap, best_kind = None, float("inf"), None
            for e in self.units:
                if e.team != u.team and e.hp > 0 and e.spec.kind == "building" \
                        and self._valid_foe(u, e):
                    g = _gap(u.x, u.y, e)
                    if g < best_gap:
                        best, best_gap, best_kind = e, g, "unit"
            for tw in towers:                                 # crown towers are buildings too
                g = _gap(u.x, u.y, tw)
                if g < best_gap:
                    best, best_gap, best_kind = tw, g, "tower"
            u.target = best
            return (best_kind, best) if best is not None else (None, None)
        if u.spec.kind == "building":
            # STATIONARY BUILDINGS lock onto the first thing that enters range and STAY on it. They
            # cannot walk, so the generic fallback below (nothing in sight -> march at a tower) is a
            # TROOP behaviour: a troop that picks a distant tower walks to it, while a building would
            # sit aiming at something permanently out of reach.
            # MEASURED: an X-Bow reaches an enemy princess only from y <= ~0.56 (11.18 tiles to its
            # edge vs 11.50 reach); at y=0.60 it is 12.34 and cannot hit. Placed behind that it still
            # latched onto a princess, which in sim-view reads as an X-Bow aimed and never firing.
            #
            # STICKINESS IS THE REAL RULE, and it is stricter than a troop's. A building holds its
            # target until that target DIES or stops being targetable (out of reach, gone invisible);
            # it does NOT re-pick whatever happens to be nearest each tick. The only external break
            # is a STUN or FREEZE -- knockback does nothing, because a building is anchored (see
            # _resolve_roll). Re-picking every tick would let a passing swarm yank an X-Bow off the
            # tower it was chewing through, which is not how it behaves in game.
            #
            # Crown towers are candidates only for SIEGE buildings (X-Bow / Mortar); a Tesla or
            # Cannon cannot hit one at any range, so they rank units alone.
            reach = u.spec.reach + u.reach_extra
            if u.aggro_reset:                                 # stun / freeze: the only thing that breaks it
                u.aggro_reset = False
                u.locked = False
                u.target = None
            t = u.target
            if isinstance(t, Unit):
                if t.hp > 0 and self._valid_foe(u, t) and _gap(u.x, u.y, t) <= reach:
                    return ("unit", t)
            elif isinstance(t, Tower):
                if t.alive and t in towers and _gap(u.x, u.y, t) <= reach:
                    return ("tower", t)
            best, best_gap, best_kind = None, float("inf"), None
            for e in self.units:
                if e.team != u.team and self._valid_foe(u, e):
                    g = _gap(u.x, u.y, e)
                    if g <= reach and g < best_gap:
                        best, best_gap, best_kind = e, g, "unit"
            if u.spec.siege:
                for tw in towers:
                    g = _gap(u.x, u.y, tw)
                    if g <= reach and g < best_gap:
                        best, best_gap, best_kind = tw, g, "tower"
            u.target, u.locked = best, False
            return (best_kind, best) if best is not None else (None, None)
        sight = self.siege_sight if u.spec.siege else (u.spec.sight or self.sight_range)
        if u.aggro_reset:                                     # knocked/stunned/shoved -> forget the lock
            u.aggro_reset = False
            u.locked = False
            u.target = None
        t = u.target
        if isinstance(t, Unit):
            cur_kind = "unit"
            cur_ok = t.hp > 0 and self._valid_foe(u, t) and _gap(u.x, u.y, t) <= sight * 1.8
        elif isinstance(t, Tower):
            cur_kind = "tower"
            cur_ok = t.alive and t in towers
        else:
            cur_kind, cur_ok = None, False
        if cur_ok and u.locked:                               # already swinging -> nothing else exists
            return (cur_kind, t)
        cur_gap = _gap(u.x, u.y, t) if cur_ok else float("inf")
        foes = [e for e in self.units if e.team != u.team and self._valid_foe(u, e)
                and _gap(u.x, u.y, e) <= sight]
        if foes:
            e = min(foes, key=lambda e: _gap(u.x, u.y, e))
            if _gap(u.x, u.y, e) < cur_gap:                   # ...only if it is CLOSER than the current target
                u.target, u.locked = e, False
                return ("unit", e)
        if cur_ok:
            return (cur_kind, t)
        if towers:                                            # nothing in sight -> march at a tower
            tw = min(towers, key=lambda t: _gap(u.x, u.y, t))
            u.target, u.locked = tw, False
            return ("tower", tw)
        u.target = None
        return (None, None)

    def _steer_around_towers(self, u: Unit, tx: float, ty: float):
        """Aim a GROUND unit around any tower body sitting on its straight path.

        Towers are SOLID -- a troop walks around one, it never passes through. That single rule is
        also what makes a multi-unit card placed BEHIND a tower split: the members spawn a little
        either side of the centre line, each rounds the nearer shoulder, and they arrive in opposite
        lanes, exactly as Archers/Skeletons/Goblins do in game. Nothing about splitting is special-
        cased; it falls out of the collision.

        Air units fly over everything, and the unit's own target is never avoided (it has to be able
        to walk up and hit it).
        """
        if u.spec.flying:
            return tx, ty
        dxt, dyt = (tx - u.x) * _TILES_X, (ty - u.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d < 1e-6:
            return tx, ty
        ux, uy = dxt / d, dyt / d                            # travel direction, tiles
        best = None
        for tw in self.towers[0] + self.towers[1]:
            if not tw.alive or tw is u.target:
                continue
            block = tw.radius + u.spec.radius
            wx, wy = (tw.x - u.x) * _TILES_X, (tw.y - u.y) * _TILES_Y
            along = wx * ux + wy * uy                        # how far ahead the tower sits
            if along <= 0.0 or along - block > d:
                continue                                     # behind us, or past where we are going
            lx, ly = wx - along * ux, wy - along * uy         # perpendicular offset to its centre
            lat = math.hypot(lx, ly)
            if lat >= block:
                continue                                     # the path already clears it
            if best is None or along < best[0]:
                best = (along, tw, lx, ly, lat, block)       # dodge the NEAREST blocker first
        if best is None:
            return tx, ty
        _along, tw, lx, ly, lat, block = best
        if lat > 1e-6:
            px, py = lx / lat, ly / lat                      # from the path line toward the tower
        else:
            # Dead-on: round the shoulder this unit is ALREADY on. Two members of one card sitting
            # a hair either side of the centre therefore peel off in opposite directions.
            side = 1.0 if u.x <= tw.x else -1.0
            px, py = -uy * side, ux * side
        m = block + _TOWER_CLEAR
        return (tw.x - px * m / _TILES_X, tw.y - py * m / _TILES_Y)

    def _move_toward(self, u: Unit, tx: float, ty: float, dt: float, spd_mult: float = 1.0) -> None:
        # Ground units cross the river only at a bridge -- unless they JUMP it. Hog Rider, Royal Hogs,
        # Ram Rider, Prince and Dark Prince vault the river anywhere along it (imported per card from
        # the wiki as `river_jump`), which is why a Hog dropped at the edge does not walk to the lane
        # first. Air ignores the river entirely.
        if not u.spec.flying and not u.spec.river_jump and (u.y - _RIVER) * (ty - _RIVER) < 0:
            bx = min(_BRIDGES, key=lambda b: abs(u.x - b))
            # Aim at the nearest point on the bridge DECK, not at its centre line. Funnelling every
            # body to `bx` made a swarm converge on ONE coordinate at the river mouth, and since
            # collision holds two 0.5-radius bodies 1.0 tile apart while the old release tolerance was
            # 0.4 tiles, they could never all be "aligned" at once: they shoved each other sideways
            # forever with y pinned at exactly 0.5000. Measured on 4 goblins -- stuck from t=6s to the
            # end of the match, x oscillating 3.00..4.00. Clamping into the deck band instead lets
            # them cross abreast, and a unit already on the deck keeps its own x.
            half = max(0.0, _BRIDGE_HALF - u.spec.radius) / _TILES_X
            lane_x = min(max(u.x, bx - half), bx + half)
            if abs(u.x - lane_x) * _TILES_X > 1e-3:
                tx, ty = lane_x, _RIVER                      # off the deck -> walk to its near edge
            else:
                tx, ty = u.x, ty                             # on the deck -> straight across
        tx, ty = self._steer_around_towers(u, tx, ty)        # towers are solid -> walk around them
        # step in TILES, then convert back per axis (one normalised unit != one tile on both axes)
        dxt, dyt = (tx - u.x) * _TILES_X, (ty - u.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d < 1e-6:
            return
        step = min(u.spec.speed * spd_mult * dt, d)
        u.charge_dist += step                                # tiles covered without swinging -> arms a charge
        u.x += (dxt / d) * step / _TILES_X
        u.y += (dyt / d) * step / _TILES_Y

    def _separate_towers(self) -> None:
        """Towers are SOLID BODIES: shove any ground unit that has ended up inside one back out to
        its edge. Steering keeps a walking troop clear; this catches the other ways a unit can end up
        overlapping -- a deploy right against a tower, Log knockback, a tornado pull. Air flies over.
        Unconditional (not under `sim.collision`, which toggles the SOFT unit-vs-unit push): a troop
        standing inside a crown tower is never legal."""
        towers = self.towers[0] + self.towers[1]
        for u in self.units:
            if u.hp <= 0 or u.spec.flying:
                continue
            for tw in towers:
                if not tw.alive:
                    continue
                mind = tw.radius + u.spec.radius
                dxt, dyt = (u.x - tw.x) * _TILES_X, (u.y - tw.y) * _TILES_Y
                d = math.hypot(dxt, dyt)
                if d >= mind:
                    continue
                if d <= 1e-6:                                # dead centre -> push out the near side
                    dxt, dyt, d = 0.0, (1.0 if u.y >= tw.y else -1.0), 1.0
                u.x, u.y = _clamp_xy(tw.x + (dxt / d) * mind / _TILES_X,
                                     tw.y + (dyt / d) * mind / _TILES_Y, u.spec.radius)

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
                if d >= mind:
                    continue
                if d <= 1e-6:
                    # EXACTLY coincident (two copies of a 1-unit card dropped on one tile, or a
                    # tornado pull collapsing bodies onto the centre). Skipping these -- what this
                    # used to do -- meant perfectly stacked units NEVER unstacked. Pick a stable
                    # per-pair direction so they always resolve, and deterministically. NB the
                    # overlap below must still use the TRUE distance (0), not the unit direction.
                    ang = 2.0 * math.pi * (((i * 7 + j * 13) % 16) / 16.0)
                    ux, uy = math.cos(ang), math.sin(ang)
                else:
                    ux, uy = dx / d, dy / d
                overlap = mind - d
                am = 0.0 if a.spec.kind == "building" else 1.0
                bm = 0.0 if b.spec.kind == "building" else 1.0
                s = am + bm
                if s <= 0:
                    continue
                px, py = ux * overlap / _TILES_X, uy * overlap / _TILES_Y  # back to normalised, per axis
                a.x, a.y = _clamp_xy(a.x + px * (am / s), a.y + py * (am / s), a.spec.radius)
                b.x, b.y = _clamp_xy(b.x - px * (bm / s), b.y - py * (bm / s), b.spec.radius)
                # Being SHOVED off what you were hitting resets aggro. This is the real mechanic
                # behind dropping a body between a melee attacker and the tower it is chewing on:
                # the attacker is pushed out, loses its lock, and re-picks -- and the thing now in
                # its face is the nearest target, so it turns on the defender. Only fires when the
                # push actually breaks reach, so a crowd milling around one target can't thrash.
                for m in (a, b):
                    if m.locked and m.target is not None \
                            and _gap(m.x, m.y, m.target) > m.spec.reach + m.reach_extra + _REACH_SLOP:
                        m.aggro_reset = True

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
        # BUILDING DECAY. A building bleeds hitpoints continuously across its lifetime -- it does not
        # sit at full HP and then blink out. The rate is exactly max_hp / lifetime, which reproduces
        # the wiki's published "Hitpoints lost per second" for every building (goblin_hut 1228/30 =
        # 40.9, inferno_tower 1748/30 = 58.3, goblin_drill 1313/10 = 131.3), so no extra data is
        # needed. This is what makes chip damage finish a building EARLY, and it is why the decay --
        # not a separate age check -- is what ends a building's life.
        for u in self.units:
            if u.spec.lifetime and u.deploy_left <= 0.0:
                u.hp -= (u.spec.hp / u.spec.lifetime) * dt
        self._tick_spawners(dt)
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
            spd = u.slow_mult if u.slow_left > 0 else 1.0
            if u.slow_left > 0:
                u.slow_left = max(0.0, u.slow_left - dt)
            prev_target = u.target
            kind, ref = self._acquire(u)
            # RAMP-UP bookkeeping: the damage stages climb only while this unit stays on ONE target,
            # and drop straight back to stage 1 the instant the target changes -- which is why a stun,
            # a knockback or simply feeding a fresh body resets an Inferno.
            if u.target is not prev_target:
                u.focus_time = 0.0
            if ref is None:
                continue
            rx, ry = (ref.x, ref.y)
            reach = u.spec.reach + u.reach_extra
            if _gap(u.x, u.y, ref) <= reach + _REACH_SLOP:
                u.attacking = True                          # engaged (in reach) -> Evo Knight's damage reduction is OFF
                u.locked = True                             # ...and committed: only an aggro reset breaks it now
                u.focus_time += dt                          # ...and the beam charges while it is actually firing
                if u.cooldown <= 0:                          # one discrete hit, then wait hit_speed (slow -> longer)
                    self._attack(u, kind, ref)
                    u.charge_dist = 0.0                      # the charge is SPENT (and stopping cancels a run-up)
                    u.cooldown = u.spec.hit_speed / spd
                    if u.spec.kamikaze:
                        u.hp = 0.0
            elif u.spec.kind != "building":                  # buildings are stationary
                self._move_toward(u, rx, ry, dt, spd)
        if self.collide:
            self._separate()
        self._separate_towers()             # towers are solid whatever the soft-collision toggle says
        self._tick_projectiles(dt)          # shots in flight advance AFTER everything has moved
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
                self._death_blast(u)                         # Balloon / Giant Skeleton / Bomb Tower
                self._spawn_from(u, u.spec.spawner_death)    # death burst (Tombstone's 4, the Drill's 2)
                continue
            alive.append(u)
        self.units = alive
        self._check_end()

    def _death_blast(self, u: "Unit") -> None:
        """Area damage centred on a body that has just died.

        This is the whole point of a Balloon (240 over 3 tiles) or a Giant Skeleton (688 over 3):
        killing them is not free, and dropping them ON something is the play. It hits enemy UNITS and
        also a crown tower in radius, so a Balloon that dies at the tower still delivers. Ground-only
        death damage cannot touch flyers, matching the normal splash rule.
        """
        s = u.spec
        if s.death_dmg <= 0.0 or s.death_radius <= 0.0:
            return
        for e in self.units:
            if e.team == u.team or e.hp <= 0:
                continue
            if s.ground_only and e.spec.flying:
                continue
            if _dist(u.x, u.y, e.x, e.y) <= s.death_radius + e.spec.radius:
                self._hurt(e, s.death_dmg)
        for tw in self._enemy_towers(u.team):
            if tw.alive and _gap(u.x, u.y, tw) <= s.death_radius:
                self._damage_tower(tw, s.death_dmg, u.team)

    def _tick_spawners(self, dt: float) -> None:
        """Produce troops from spawners (Goblin Hut, Tombstone, Barbarian Hut, Goblin Drill, Furnace,
        Witch, Night Witch...). A spawner's damage comes from its UNITS, not from the building -- a
        Goblin Drill has no attack of its own, so modelling it as a plain attacker had it hitting the
        crown tower directly.

        `spawner_range` is a PROXIMITY GATE: Goblin Hut only summons while an enemy is within 6 tiles
        (it stopped spawning automatically in the May 2025 update). Spawners without one produce
        unconditionally. The first tick waits deploy_time + spawner_delay, set on deploy.
        """
        for u in list(self.units):
            s = u.spec
            if s.spawner_spec is None or s.spawner_interval <= 0.0 or u.hp <= 0:
                continue
            if u.deploy_left > 0.0 or u.stun_left > 0.0:
                continue
            if s.spawner_range is not None and not self._enemy_within(u, s.spawner_range):
                continue                                     # gate shut: bank nothing, just wait
            u.spawn_cd -= dt
            if u.spawn_cd <= 0.0:
                u.spawn_cd += s.spawner_interval
                self._spawn_from(u, s.spawner_count)

    def _enemy_within(self, u: "Unit", tiles: float) -> bool:
        """Any live enemy body inside `tiles` of this unit (the spawner proximity gate)."""
        return any(e.team != u.team and e.hp > 0 and e.deploy_left <= 0.0
                   and _dist(u.x, u.y, e.x, e.y) <= tiles
                   for e in self.units)

    def _spawn_from(self, u: "Unit", n: int) -> None:
        """Drop `n` of this spawner's troop around it, on the side it is pushing toward."""
        sp = u.spec.spawner_spec
        if sp is None or n <= 0:
            return
        fwd = -1.0 if u.team == 0 else 1.0                   # team 0 attacks up the board
        step = (u.spec.radius + sp.radius + 0.1)
        for i in range(n):
            ox = ((i % 3) - 1) * step / _TILES_X
            oy = (fwd * (u.spec.radius + sp.radius) - (i // 3) * step * fwd) / _TILES_Y
            x, y = _clamp_xy(u.x + ox, u.y + oy, sp.radius)
            nu = Unit(spec=sp, team=u.team, x=x, y=y, hp=sp.hp)
            nu.deploy_left = sp.deploy_time
            self.units.append(nu)

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
        mult = self._ramp_mult(u)
        dmg = u.spec.hit_dmg * u.dmg_mult * mult             # one discrete hit (DPS x hit_speed; x Royal Chef buff)
        tower_dmg = u.spec.tower_hit_dmg * u.dmg_mult * mult
        # CHARGE: a completed run-up REPLACES this hit's damage (Prince 783 vs a ~200 base hit). It
        # is a flat published value, not a multiplier, so it overrides rather than scales -- and it
        # applies to towers too, which is what makes an unblocked Prince so punishing.
        if u.spec.charge_dmg > 0.0 and u.spec.charge_range > 0.0 \
                and u.charge_dist >= u.spec.charge_range:
            dmg = u.spec.charge_dmg * u.dmg_mult
            tower_dmg = dmg
        if u.spec.proj_speed > 0.0:                          # the shot has to TRAVEL -- it lands later
            self._launch(f"{u.spec.base}_projectile", u.team, u.x, u.y, ref, u.spec, dmg, tower_dmg)
            return
        self._land_hit(u.team, kind, ref, u.spec, dmg, tower_dmg)
        self._multi_hit(u.spec, u.team, u.x, u.y, ref, dmg)   # chain arcs / shotgun pellets

    @staticmethod
    def _ramp_mult(u: Unit) -> float:
        """Ramp-up multiplier on this unit's per-hit damage.

        Inferno Tower, Inferno Dragon and Mighty Miner climb through three damage stages while they
        stay locked on ONE target -- 2 seconds per stage -- and drop back to stage 1 the moment the
        target changes. That is what makes a stun/reset or a fresh body such a strong answer to them,
        and why they melt tanks but barely scratch a swarm. The KB stores the stage damage per level
        (e.g. Inferno Tower 43 / 158 / 847), so this returns stage_damage / stage_1_damage and lets
        the normal hit_dmg path carry level scaling and the Royal Chef buff.
        """
        st = u.spec.dmg_stages
        if len(st) < 2 or not st[0]:
            return 1.0
        idx = min(int(u.focus_time // max(0.1, u.spec.stage_time)), len(st) - 1)
        return float(st[idx]) / float(st[0])

    def _land_hit(self, team: int, kind: str, ref, spec: CardSpec, dmg: float,
                  tower_dmg: float) -> None:
        """Deal one hit that has ARRIVED (either instantly, or as a projectile reaching its target)."""
        if kind == "tower":
            # crown towers take the REDUCED per-hit value when the card has one (Miner) -- real CR's
            # crown-tower damage reduction; most troops have no reduced value so this equals hit_dmg
            self._damage_tower(ref, tower_dmg, team)
            return
        self._hurt(ref, dmg)
        self._apply_status(spec, ref)
        if spec.splash:
            for e in self.units:
                if e.team != team and e is not ref and _dist(e.x, e.y, ref.x, ref.y) <= _SPLASH_R:
                    self._hurt(e, dmg)
                    self._apply_status(spec, e)

    def _launch(self, label: str, team: int, x: float, y: float, ref, spec: CardSpec,
                dmg: float, tower_dmg: float) -> None:
        radius = spec.proj_radius
        rng = spec.proj_range or (spec.reach + _REACH_SLOP)
        self.projectiles.append(Projectile(
            label=label, team=team, x=x, y=y, tx=ref.x, ty=ref.y, target=ref, spec=spec,
            dmg=dmg, tower_dmg=tower_dmg, radius=radius, speed=spec.proj_speed,
            left=max(rng, _dist(x, y, ref.x, ref.y)),
            ground_only=not spec.attacks_air,
            # SPARK and SHOTGUN shots must not pierce: a piercing shot is deleted at max range and
            # never reaches _impact, so their extra hits would never fire. Both burst ON the target.
            pierce=spec.proj_pierce and spec.multi_kind not in ("spark", "shotgun"), ox=x, oy=y))

    def _tick_projectiles(self, dt: float) -> None:
        for p in list(self.projectiles):
            if p.target is not None and not p.pierce and p.radius <= 0.0:
                alive = (p.target.hp > 0) if isinstance(p.target, Unit) else p.target.alive
                if not alive:
                    self.projectiles.remove(p)      # single-target shot whose target died mid-flight fizzles
                    continue
                p.tx, p.ty = p.target.x, p.target.y  # tracking shot follows it
            step = p.speed * dt
            dxt, dyt = (p.tx - p.x) * _TILES_X, (p.ty - p.y) * _TILES_Y
            d = math.hypot(dxt, dyt)
            if d > 1e-9:
                move = min(step, d) if not p.pierce else step
                p.x += (dxt / d) * move / _TILES_X
                p.y += (dyt / d) * move / _TILES_Y
            p.left -= step
            if p.pierce:                              # damages everything it passes through, once each
                for e in self.units:
                    if e.team == p.team or e.hp <= 0 or id(e) in p.hit:
                        continue
                    if p.ground_only and e.spec.flying:
                        continue
                    if _dist(p.x, p.y, e.x, e.y) <= max(p.radius, 0.5) + e.spec.radius:
                        p.hit.add(id(e))
                        self._hurt(e, p.dmg)
                        self._apply_status(p.spec, e)
                if p.left <= 0.0:
                    # BOOMERANG: the axe does not stop at max range, it turns around and hits
                    # everything again on the way back. Clearing `hit` is what lets it re-damage the
                    # same bodies -- that return leg is the whole reason Executioner trades so well
                    # into a line of troops.
                    if (p.spec.multi_kind == "boomerang" and not p.returning
                            and p.spec.multi_hits >= 2):
                        p.returning = True
                        p.label = f"{p.spec.base}_axe_return"
                        p.target = None
                        p.tx, p.ty = p.ox, p.oy
                        p.left = _dist(p.x, p.y, p.ox, p.oy)
                        p.hit.clear()
                        continue
                    self.projectiles.remove(p)
                continue
            if d <= step or p.left <= 0.0:            # ARRIVED
                self._impact(p)
                self.projectiles.remove(p)

    def _impact(self, p: Projectile) -> None:
        spark = p.spec.multi_kind == "spark" and p.label.endswith("_projectile")
        if p.radius > 0.0:                            # AREA shot: explodes where it landed, hit or miss
            for e in self.units:
                if e.team == p.team or e.hp <= 0:
                    continue
                if p.ground_only and e.spec.flying:
                    continue
                if _dist(p.x, p.y, e.x, e.y) <= p.radius + e.spec.radius:
                    self._hurt(e, p.dmg)
                    self._apply_status(p.spec, e)
            for tw in self._enemy_towers(p.team):
                if _gap(p.x, p.y, tw) <= p.radius:
                    self._damage_tower(tw, p.tower_dmg, p.team)
            if spark:
                self._spark_burst(p)              # ...and THEN it splits into shrapnel
            return
        ref = p.target
        if ref is None:
            return
        # Only the card's PRIMARY shot spawns extra hits. Without this guard a chain arc's own
        # impact called _multi_hit again and spawned further arcs, which grows exponentially and
        # hangs the match -- the derived projectiles are consequences of an attack, not attacks.
        primary = p.label.endswith("_projectile")
        if isinstance(ref, Tower):
            if ref.alive:
                self._damage_tower(ref, p.tower_dmg, p.team)
                if primary:
                    self._multi_hit(p.spec, p.team, p.ox, p.oy, ref, p.tower_dmg)
            return
        if ref.hp > 0:
            self._land_hit(p.team, "unit", ref, p.spec, p.dmg, p.tower_dmg)
            if primary:
                self._multi_hit(p.spec, p.team, p.ox, p.oy, ref, p.dmg)

    def _multi_hit(self, spec: CardSpec, team: int, fx: float, fy: float, ref, dmg: float) -> None:
        """The extra hits of a multi-hit attack, one branch per mechanic.

        `hits_per_attack` is a single wiki number covering four unrelated behaviours, so a blanket
        multiplier would be wrong for at least three of them. Each emits a distinctly LABELLED
        projectile so sim-view can draw them apart. Called from BOTH the instant-hit path and the
        projectile IMPACT path -- every one of these cards actually shoots, so wiring it only into
        the instant path left all of them landing a single hit.
        """
        s = spec
        n = s.multi_hits
        if n < 2 or not s.multi_kind:
            return
        if s.multi_kind == "chain":
            # The bolt arcs from the struck body to the next nearest enemies (Electro Dragon 3,
            # Electro Wizard 2). Each arc carries the card's stun, which is why a chain resets a
            # whole line of attackers rather than just the one it hit.
            if not isinstance(ref, Unit):
                return
            near = sorted((e for e in self.units
                           if e.team != team and e.hp > 0 and e is not ref
                           and _dist(ref.x, ref.y, e.x, e.y) <= _CHAIN_TILES
                           and not (not s.attacks_air and e.spec.flying)),
                          key=lambda e: _dist(ref.x, ref.y, e.x, e.y))
            for e in near[:n - 1]:
                self._hurt(e, dmg)
                self._apply_status(s, e)
                self.projectiles.append(Projectile(
                    label=f"{s.base}_chain", team=team, x=ref.x, y=ref.y, tx=e.x, ty=e.y,
                    target=e, spec=s, dmg=0.0, tower_dmg=0.0, radius=0.0,
                    speed=max(s.proj_speed, 20.0), left=_dist(ref.x, ref.y, e.x, e.y),
                    ground_only=not s.attacks_air))
        elif s.multi_kind == "shotgun":
            # A CONE of pellets: they all converge at point-blank and spread out with distance, so
            # the same attack is devastating up close and weak at range. That distance falloff is
            # the entire identity of the Hunter -- one flat hit made him a mediocre single-target.
            rng = s.proj_range or (s.reach + _REACH_SLOP)
            gap = _gap(fx, fy, ref)
            extra = max(0, int(round(n * max(0.0, 1.0 - gap / max(rng, 1e-6)))) - 1)
            for _ in range(extra):
                if isinstance(ref, Tower):
                    if ref.alive:
                        self._damage_tower(ref, dmg, team)
                elif ref.hp > 0:
                    self._hurt(ref, dmg)

    def _spark_burst(self, p: Projectile) -> None:
        """Firecracker: the rocket hits its target, THEN splits into shrapnel.

        Per the wiki: "once it hits its target, splits into 5 ADDITIONAL shrapnel, which continue to
        travel, while piercing through enemies". Three things that matters for:
          * the rocket deals its OWN area damage on impact (projectile radius 0.4) -- the sparks are
            extra, not a replacement for it;
          * the sparks PIERCE rather than explode, so each one damages everything along its path;
          * they radiate from the LANDING POINT, which is why the card punishes a clump behind the
            body it aimed at rather than just that body.
        """
        s = p.spec
        n = s.multi_hits
        if s.multi_kind != "spark" or n < 2:
            return
        for i in range(n):
            ang = 2.0 * math.pi * i / n
            ex = p.x + math.cos(ang) * _SPARK_TILES / _TILES_X
            ey = p.y + math.sin(ang) * _SPARK_TILES / _TILES_Y
            ex, ey = _clamp_xy(ex, ey, 0.0)
            self.projectiles.append(Projectile(
                label=f"{s.base}_spark", team=p.team, x=p.x, y=p.y, tx=ex, ty=ey, target=None,
                spec=s, dmg=p.dmg, tower_dmg=p.tower_dmg, radius=s.proj_radius,
                speed=max(s.proj_speed, 8.0), left=_SPARK_TILES,
                ground_only=not s.attacks_air, pierce=True, ox=p.x, oy=p.y))

    def _can_knock(self, e: Unit, spec: CardSpec) -> bool:
        """Whether `spec`'s pushback moves THIS body at all.

        Two independent exclusions, both sourced:
          BUILDINGS are anchored -- once placed, a building holds its tile for its whole lifetime.
          HEAVY TROOPS shrug off the small-to-medium pushback. Per the Bowler page, its knockback
          "functions identically to a Fireball, Giant Snowball, or Rocket, pushing back small to
          medium sized ground troops, and minimally damaging heavy troops such as the Prince,
          Sparky, Dark Prince, Skeleton King, Giant Skeleton, Goblin Machine, P.E.K.K.A, Mega
          Knight, Cannon Cart, and the Mighty Miner" -- and "his inability to knock back tanks means
          he can separate the tanks and the support units".
        The Log is the documented EXCEPTION (knockback_all): it "push[es] back all ground troops",
        explicitly including the Prince and Dark Prince charges. So immunity is not a pure property
        of the target -- the spell decides whether it applies.
        """
        if spec.knockback <= 0.0 or e.spec.kind == "building":
            return False
        return spec.knockback_all or not e.spec.knockback_immune

    def _knock(self, e: Unit, spec: CardSpec, fx: float, fy: float) -> None:
        """RADIAL pushback from a point blast (Fireball / Giant Snowball / Rocket) -- away from the
        impact point, unlike a rolling spell which shoves everything the same way down its corridor.
        The shove also RESETS the attack animation ("troops vulnerable to knockback will have their
        attack animations reset"), which is the whole reason a Snowball answers a charge or an
        Inferno's ramp -- modelled here by the same aggro_reset the Log already set."""
        if not self._can_knock(e, spec):
            return
        dxt, dyt = (e.x - fx) * _TILES_X, (e.y - fy) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d <= 1e-6:                                    # dead centre: no radial direction exists
            dxt, dyt, d = 0.0, 1.0, 1.0                  # deterministic fallback
        e.x, e.y = _clamp_xy(e.x + (dxt / d) * spec.knockback / _TILES_X,
                             e.y + (dyt / d) * spec.knockback / _TILES_Y, e.spec.radius)
        e.aggro_reset = True

    def _apply_status(self, spec: CardSpec, e: Unit) -> None:
        """Apply a hitter's/spell's crowd-control to a struck ground/air unit.

        Durations and slow strength are PER CARD where the wiki publishes them, falling back to the
        global config value. That difference is not cosmetic: a Freeze holds for 4s and an Ice Spirit
        for 1.1s, and a Ram Rider's snare (-70%) is more than twice a Giant Snowball's (-30%).
        """
        if spec.freezes:
            e.stun_left = max(e.stun_left, spec.freeze_dur or self.freeze_dur)
            e.aggro_reset = True          # RESET CARDS: a stun/freeze breaks the target lock -- that is the
        elif spec.stuns:                  # whole point of an Ice/Electro Spirit or a Zap on a locked attacker
            e.stun_left = max(e.stun_left, spec.stun_dur or self.stun_dur)
            e.aggro_reset = True
        if spec.slows:
            e.slow_left = max(e.slow_left, spec.slow_dur or self.slow_dur)
            e.slow_mult = spec.slow_mult or self.slow_factor

    def _pulse(self, u: Unit) -> None:
        """Evo Tesla area-shock: damage + STUN every enemy within pulse_r of the tower."""
        for e in self.units:
            if e.team == u.team or e.hp <= 0 or e.deploy_left > 0:
                continue
            if _dist(e.x, e.y, u.x, u.y) <= u.spec.pulse_r:
                self._hurt(e, u.spec.pulse_dmg)
                if u.spec.pulse_stun > 0:
                    e.stun_left = max(e.stun_left, u.spec.pulse_stun)
                    e.aggro_reset = True

    def _tower_fire(self, team: int, tw: Tower, dt: float) -> None:
        """DISCRETE single-target tower shots. Cadence + damage come from the tower troop; Dagger Duchess
        bursts through a loaded dagger clip (fast) then fires slower until it reloads while it has no target."""
        rng = self.king_range if tw.king else self.tower_range
        foes = [e for e in self.units if e.team != team and e.hp > 0 and e.deploy_left <= 0.0
                and _gap(tw.x, tw.y, e) <= rng]
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
        tgt = min(foes, key=lambda e: _gap(tw.x, tw.y, e))
        # Crown towers shoot a real, travelling, TRACKING shot -- so a Princess Tower arrow crossing 7
        # tiles takes about as long as it does on screen, and the debugger can draw it.
        self.projectiles.append(Projectile(
            label=f"{tw.troop}_projectile", team=team, x=tw.x, y=tw.y, tx=tgt.x, ty=tgt.y,
            target=tgt, spec=_TOWER_SHOT, dmg=tw.hit_dmg, tower_dmg=tw.hit_dmg,
            radius=0.0, speed=self.tower_proj_speed,
            left=rng + 2.0, ground_only=False))
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
                self._knock(e, s.spec, s.x, s.y)              # Fireball / Giant Snowball / Rocket pushback
        for tw in self._enemy_towers(s.team):
            if _dist(tw.x, tw.y, s.x, s.y) <= s.spec.spell_radius:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)
        sp = s.spec.spawn_spec                                # Royal Delivery drops a shielded Royal Recruit here
        for i in range(s.spec.spawn_count if sp is not None else 0):
            ox = (0.64 * ((i % 3) - 1) / _TILES_X) if s.spec.spawn_count > 1 else 0.0   # tiles -> normalised
            sx, sy = _clamp_xy(s.x + ox, s.y, sp.radius)
            u = Unit(sp, s.team, sx, sy, sp.hp)
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
            # BUILDINGS ARE ANCHORED. A Tornado damages a Tesla / Cannon / X-Bow but CANNOT drag one:
            # once a building is placed it holds that tile for its whole lifetime. Without this a
            # Tornado could haul an enemy Tesla out of the lane it was built to cover -- and, worse,
            # haul YOUR X-Bow off its firing position, which is not a play that exists in the game.
            # Same rule as the Log's knockback guard in _resolve_roll.
            if e.spec.kind == "building":
                continue
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
                if self._can_knock(e, s.spec):
                    # BUILDINGS ARE ANCHORED and HEAVIES RESIST -- except the Log, which is the one
                    # spell documented to push back ALL ground troops (see _can_knock). Damage still
                    # lands on everything the corridor covers.
                    e.x, e.y = _clamp_xy(e.x, e.y + fdir * s.spec.knockback / _TILES_Y, e.spec.radius)
                    e.aggro_reset = True                       # the shove breaks its lock -- it re-picks from
                                                               # where it LANDS, so a Log can pull a locked
                                                               # attacker onto whatever is now nearest
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
        """The real CR match clock.

        * ANY TIME: a KING falling ends it -- that is the third crown.
        * AT REGULATION (180 s): if the crowns are UNEQUAL the match is OVER. The sim used to play
          regulation + overtime unconditionally, so a 1-0 lead at 3:00 kept playing and could be
          handed back; overtime was reachable from a winning position, which it never is in game.
        * CROWNS LEVEL AT 180 s -> OVERTIME, 120 s of SUDDEN DEATH: the first crown taken wins
          instantly. Because crowns are equal by construction once overtime starts, "the crowns are
          now unequal" IS the sudden-death condition -- so the single test above covers both rules
          and there is no separate overtime branch to keep in sync.
        * STILL LEVEL AT 300 s -> the tiebreak on the least-healthy STANDING tower (_score_outcome).
        """
        for team in (0, 1):
            if not self.towers[team][2].alive:               # king down -> that team loses
                self.done = True
                self.outcome = "loss" if team == 0 else "win"
                return
        if self.t < self.regulation:
            return                                            # regulation runs its full length
        my_c, op_c = self.crowns(0), self.crowns(1)
        if my_c != op_c:
            self.done = True
            self.outcome = "win" if my_c > op_c else "loss"
            return
        if self.t >= self.regulation + self.overtime:
            self.done = True
            self.outcome = self._score_outcome()

    def _score_outcome(self) -> str:
        """Crowns first, then CR's overtime TIEBREAK on the least-healthy REMAINING Crown Tower.

        Real rule: when overtime expires level, every tower still STANDING starts taking damage
        together, and the side whose weakest one falls first loses. So the comparison is over ALIVE
        towers only.

        THE BUG THIS FIXES: the filter used to be `t.max_hp > 0`, which a DESTROYED tower also
        passes (hp 0, max_hp unchanged) -- so it contributed a fraction of 0.0. The moment each side
        had lost one princess (crowns 1-1, the most common way a close match stands), both minima
        were 0.0, the equality band fired, and the match was declared a DRAW no matter how far ahead
        one side was on the towers still standing. MEASURED: 7 of 40 matches ended
        `TRUE DRAW (both weakest at 0.000)`, i.e. 17.5% of matches returned a terminal reward of 0
        instead of +-w_win. It erased exactly the win the rocket-cycle plan is built to produce --
        chip damage that never finishes a tower is precisely what the tiebreak is supposed to read.

        Fractions rather than absolute HP, so asymmetric tower-troop/level max-HP between the two
        sides stays comparable.
        """
        my_crowns = self.crowns(0)
        op_crowns = self.crowns(1)
        if my_crowns != op_crowns:
            return "win" if my_crowns > op_crowns else "loss"
        my_min = min((t.hp / t.max_hp for t in self.towers[0] if t.alive and t.max_hp > 0), default=1.0)
        op_min = min((t.hp / t.max_hp for t in self.towers[1] if t.alive and t.max_hp > 0), default=1.0)
        if abs(my_min - op_min) < 1e-3:
            return "draw"                                    # genuinely level on every standing tower
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
