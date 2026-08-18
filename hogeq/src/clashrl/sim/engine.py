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

from .. import levels as _lv

# --- BOARD GEOMETRY (tiles) -------------------------------------------------------------------
# Set once per process from `sim.board` by SimEngine.__init__ (every env in a process shares one
# config, so module-level is safe and keeps `_dist` / `build_spec` free of an engine reference).
_TILES_X = 18.0
_TILES_Y = 32.0
_BRIDGES = (3.5 / 18.0, 14.5 / 18.0)     # bridge centres, normalised x (tile-derived; set below)
_BRIDGE_HALF = 1.5                       # bridge deck HALF-width in TILES (set by configure_board)
# THE RIVER IS A BAND, NOT A LINE. It is 2 TILES TALL in the real arena (rows 15..17, centre 16), so
# the water a troop crosses has real THICKNESS and the bank it steps onto is a tile off the centre.
# Modelling it as the single line y=16 made the whole 15..17 strip walkable-and-deployable: the
# front-most deployable row centre sat at 16.67 tiles, i.e. IN THE WATER, about a tile further
# forward than the game allows.
_RIVER_HALF = 1.0                        # half-thickness in TILES (set by configure_board)


def configure_board(tiles_x: float, tiles_y: float, bridge_tiles, bridge_width: float = 3.0,
                    river_width: float = 2.0) -> None:
    """Set the tile grid + bridge lanes + river thickness. Called by SimEngine.__init__ from `sim.board`."""
    global _TILES_X, _TILES_Y, _BRIDGES, _BRIDGE_HALF, _RIVER_HALF
    _TILES_X, _TILES_Y = float(tiles_x), float(tiles_y)
    _BRIDGES = tuple(float(b) / _TILES_X for b in bridge_tiles)
    _BRIDGE_HALF = float(bridge_width) / 2.0
    _RIVER_HALF = float(river_width) / 2.0


def river_bank(y: float) -> float:
    """The normalised y of the river EDGE on the same side as `y` -- the tile a troop steps onto."""
    return _RIVER - _RIVER_HALF / _TILES_Y if y < _RIVER else _RIVER + _RIVER_HALF / _TILES_Y


# speed word -> TILES/second (CR: medium ~= 1 tile/s; matches the old 0.031 normalised x 32)
_SPEED = {"slow": 0.75, "medium": 1.0, "fast": 1.5, "very_fast": 2.0, None: 1.0}
# attack reach word -> TILES (melee ~1, short ~3, long 5.5)
# Attack reach is now PER CARD (cards.CardDB.attack_range_tiles, from cr-api-data `range`) rather
# than one constant per melee/short/long bucket -- real melee spans 0.5-1.6 tiles.
_REACH_SLOP = 0.6         # tiles of tolerance on "target is in reach"
_PELLET_R = 0.1           # a shotgun pellet is a POINT, not a blast -- the target's own body does the work
_PELLET_TOWER_R = 0.6     # tower crown body that can catch a pellet (smaller than the full 3x3 footprint)
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
_SKELETON_BASES = {"skeletons", "skeleton_army", "guards"}   # Evo Witch's Healing Bones triggers
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
    # DEPLOY / SURFACE BLAST: area damage the moment the body finishes appearing. Mega Knight "will
    # deal damage to enemy units around him in a 360 deg area ... and inflict knockback" as he lands,
    # and Goblin Drill does the same "when it surfaces". Both are published (`spawn_damage`), and
    # both are a large part of why the card is played at all -- a Mega Knight that lands for nothing
    # is not the card people answer with a swarm.
    spawn_dmg: float = 0.0
    spawn_radius: float = 0.0
    spawn_crown_dmg: float = 0.0
    # COMBO: every Nth normal attack carries the knockback (Monk's 3-strike). This has to be its own
    # marker rather than "has the knockback flag", because for Golem / Giant Skeleton / Phoenix /
    # Skeleton Barrel / Goblin Demolisher the knockback rides the DEATH blast and their melee swing
    # must NOT push.
    combo_every: int = 0
    # LEAP -- Bandit's DASH and Mega Knight's JUMP are the SAME mechanic with different numbers, and
    # the wiki states both in identical language: "If there are ground units between X and Y tiles of
    # [them], [they] will stop moving and begin charging a [dash|jump] attack which takes T seconds
    # to execute, and will deal DOUBLE DAMAGE". The leap closes the gap, so it is the reason both
    # cards punish a defender placed at mid range instead of touching them -- and the reason a
    # Bandit cannot be chip-damaged out of it.
    leap_dmg: float = 0.0     # published dash_damage / jump_damage (already ~2x the base hit)
    leap_time: float = 0.0    # WIND-UP: seconds charging, stationary, before he leaves the ground.
                              # The balance log is explicit that this is the charge, not the flight:
                              # "decreased the time required for CHARGING his jump to 0.9 seconds".
    leap_speed: float = 0.0   # TRAVEL speed in tiles/s, from the leap row's own Speed column
                              # (Mega Knight 250 -> 4.17 t/s, Bandit 500 -> 8.33 t/s, at 60 = 1 t/s)
    leap_splash: float = 0.0  # the LEAP's own splash radius -- Mega Knight's jump is 2.2 tiles vs
                              # his 1.3 on a normal swing, so the jump covers a much wider group
    leap_min: float = 0.0     # closer than this and it just walks in and swings normally
    leap_max: float = 0.0     # further than this and it keeps walking
    leap_invuln: bool = False  # "She is immune to damage during her dash" (Bandit only)
    # Can the leap target a CROWN TOWER? True for every leaper we model. NB the Mega Knight's "Mega
    # Power Jump" modifier ("can target a unit or tower for a jump attack AT ANY DISTANCE") is NOT
    # evidence that his base jump cannot hit a tower -- the upgrade is the AT ANY DISTANCE part,
    # which lifts the 3.5-5 tile band. He does jump crown towers in game.
    leap_towers: bool = False
    # SELF-PRESERVATION ABILITY (Boss Bandit's "Getaway Grenade", 1 elixir): "get invisible for one
    # second, then teleport 6 tiles behind her current spot", 3 s cooldown after the duration, and
    # it "can only be activated twice". Modelled as an AUTOMATIC reaction rather than a player
    # action: exposing it to the policy would need a whole new action type (and a retrain), while
    # the opponents who actually field her do need to use it or she is strictly worse than she reads.
    ability_cost: float = 0.0
    ability_uses: int = 0
    ability_cd: float = 0.0
    ability_invis: float = 0.0
    ability_back: float = 0.0
    # THE OTHER ABILITY SHAPE: the Mighty Miner's "Explosive Escape", which is a PLAYER action, not
    # the automatic reaction above. He mirrors to the opposite lane and leaves a fused bomb behind,
    # so it needs a displacement that is a reflection rather than a nudge, plus a blast the nudge
    # ability has no concept of. Non-zero `ability_bomb_dmg` is what marks a card as having it; see
    # Engine.champion_ability, which the env calls from a dedicated action-space slot.
    ability_bomb_dmg: float = 0.0
    ability_bomb_radius: float = 0.0
    ability_bomb_knock: float = 0.0
    ability_delay: float = 0.0
    # SELF-RECOIL, in tiles: the shooter shoves ITSELF backwards every time it fires. Not a
    # knockback -- nothing is being hit, and it applies to the firer regardless of any knockback
    # immunity. Three cards have it (Firecracker, Sparky, Super Archers); 0 = it does not recoil.
    recoil: float = 0.0
    # PER-CARD SPLASH RADIUS (2026-08-14): splash used to be a bool + one flat _SPLASH_R for every
    # card. 0 = fall back to _SPLASH_R.
    splash_r: float = 0.0
    # ZAP-PACK REFLECT (Electro Giant, 2026-08-14): a unit that DAMAGES this card from within
    # reflect_r tiles takes reflect_dmg back (+ reflect_stun seconds). Wiki: 3 tiles, ~120 @ L11,
    # 0.5 s stun per hit. Ranged attackers outside the radius are untouched -- which is exactly
    # the ranged-only counter-doctrine this makes learnable.
    reflect_dmg: float = 0.0
    reflect_r: float = 0.0
    reflect_stun: float = 0.0
    knockback: float = 0.0    # a rolling spell pushes ground troops this far in the roll direction
    # KNOCKBACK REACHES EVERY TROOP, not just the light ones. The Log's 19/9/2016 entry -- "allowed
    # The Log to push back ALL ground troops. This allowed The Log to reset the charge attacks of the
    # Prince and Dark Prince" -- names the two units the Bowler page lists as knockback-IMMUNE, so
    # vulnerability is per-SPELL, not purely a property of the target.
    knockback_all: bool = False
    # This BODY shrugs off the small-to-medium pushback (Fireball / Giant Snowball / Rocket / Bowler).
    # Sourced from the game files' `ignore_pushback` (21 units), which both CONFIRMED the curated
    # list and extended it: the wiki prose enumerates "heavy troops such as the Prince, Sparky, ...",
    # and reading that as exhaustive had left every giant-class tank knockable. The wiki settles it
    # in the Giant Snowball page's own words -- pushback applies "if small or medium sized", and a
    # Giant or Elixir Golem is only SLOWED.
    knockback_immune: bool = False
    # Shove weight, straight from the game files (Skeleton 1, Knight 6, Giant 18, Golem 20). None
    # for cards newer than the 2023 dump -- _push_mass falls back rather than treating them as
    # weightless. NOT derivable from collision_radius: six different units share a 0.5 radius and
    # have masses from 1 to 6.
    mass: Optional[float] = None
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
    # Knockback carried by the DEATH blast alone, when it differs from the card's ordinary one.
    # The Bomb Tower is the case: its shots do not shove, only the bomb it drops when it dies
    # does. 0 = no separate value, so the death blast reuses `knockback` (Golem, Giant Skeleton
    # and the rest, whose shove is the same either way).
    death_knockback: float = 0.0
    # LUMBERJACK: "Upon death, he drops a bottle of Rage" -- an area that boosts friendly move
    # AND attack speed. Curated from the balance log: radius 3 tiles + 4.5 s (Aug 2025), boost
    # +30% (Oct 2025, from 35%), 0.5 s deploy timer before it takes effect.
    rage_r: float = 0.0
    rage_dur: float = 0.0
    rage_boost: float = 0.0
    rage_delay: float = 0.0
    # PHOENIX: dies -> death blast + drops an EGG once. If the egg survives `egg_hatch` seconds
    # it hatches a REBORN phoenix at `egg_frac` of the original's hitpoints and damage (7/2/2023
    # balance); the reborn deals no death damage and drops no second egg.
    egg_hatch: float = 0.0
    egg_frac: float = 0.0
    # ---- T1 EVO MECHANICS (2026-08-14 verify sweep; per-mechanic sources in cards.yaml) ----
    recoil_dmg: float = 0.0      # EVO ROYAL GIANT: every shot also blasts AROUND HIMSELF --
    recoil_r: float = 0.0        # 2.5 tiles, GROUND only, 1-tile shove (air is immune)
    spawn_on_hit: str = ""       # EVO SKELETONS: unit key spawned on each landed swing...
    spawn_on_hit_cap: int = 0    # ...while fewer than this many (same spec.key) are alive on the team
    charge_after_shield: bool = False  # EVO RECRUITS: the charge only arms once the shield is GONE
    hit_rage_s: float = 0.0      # EVO BARBARIANS: self-rage refreshed by every swing (3 s)...
    hit_rage_boost: float = 0.0  # ...at +30% move/attack speed; does NOT stack with rage zones
    attack_nado_r: float = 0.0   # EVO VALKYRIE: every swing spins up a 0.5 s whirlwind that
    attack_nado_s: float = 0.0   # pulls ground AND air toward her (5.5 tiles) and deals its
    attack_nado_dmg: float = 0.0 # damage spread over the duration -- the tornado vortex, reused
    zap_pulses: int = 0          # EVO ZAP: total pulses (3), ~1 s apart, ring GROWING by
    zap_step: float = 0.0        # zap_step tiles each pulse (2.5 -> 3.0 -> 3.5)
    kill_heal: float = 0.0       # EVO PEKKA: flat heal per troop/building KILL (12.5% = 470)...
    overheal_frac: float = 1.0   # ...overhealing up to this x deploy hp (1.5; EVO BATS 2.0)
    mid_drop_frac: float = 0.0   # EVO SKEL BARREL: first barrel drops when hp falls to this frac
    hit_heal: float = 0.0        # EVO BATS: heal per landed swing (two 0.5s pulses folded into one)
    # ---- PHASE B EVO MECHANICS (2026-08-14 sweep 2) ----
    sniper_shots: int = 0        # EVO MUSKETEER: infinite-range rounds she spawns with (3). Fired
    sniper_mult: float = 0.0     # only when NOTHING is in her normal reach, at the closest enemy
                                 # unit IN FRONT of her, each dealing sniper_mult x her hit (1.8).
                                 # She can never snipe a crown tower.
    power_mult: float = 0.0      # EVO ARCHERS: POWER SHOT -- swings at gap >= power_min tiles
    power_min: float = 0.0       # (4.0) deal power_mult x damage (1.5); their reach is 6.
    spark_dps_big: float = 0.0   # EVO FC: shots leave LINGERING SPARK ZONES along their paths --
    spark_dps_small: float = 0.0 # the CARRIER trails LARGE sparks (192 dps), the shrapnel SMALL
    spark_dur: float = 0.0       # ones (60 dps); tick every 0.25 s + 15% move slow, zone lives
    spark_r: float = 0.0         # spark_dur (2.5 s). Values USER-VERIFIED at level 11.
    javelin_dmg: float = 0.0     # EVO E-BARBS: rage-tipped spear at the current target (troop OR
    javelin_cd: float = 0.0      # crown tower) every javelin_cd seconds, leaving a rage TRAIL
    decoy_mirror: str = ""       # EVO GOBLIN BARREL: also throw this spell at the MIRRORED tile
    # ---- PHASE B WAVE 3 (2026-08-14 sweep 3; per-mechanic sources in cards.yaml) ----
    uppercut_tiles: float = 0.0  # EVO MK: every swing launches the TARGET this far toward ITS OWN
                                 # nearest crown tower, ignoring weight (buildings excepted)
    smash_range: float = 0.0     # EVO EXECUTIONER: targets within this range also get SHOVED
    smash_knock: float = 0.0     # smash_knock tiles (resets charges via the shove's aggro_reset)
    net_cd: float = 0.0          # EVO HUNTER: net at the closest unit every net_cd seconds...
    net_root_s: float = 0.0      # ...rooting it (stun-equivalent: no move/attack, still hittable)
    net_range: float = 0.0
    shield_burst_dmg: float = 0.0  # EVO WIZARD: the Fire Shield EXPLODES when it breaks
    shield_burst_r: float = 0.0
    shield_burst_knock: float = 0.0
    spawn_death_heal: float = 0.0  # EVO WITCH: heals this much when ANY friendly skeleton/guard dies
    ramp_keep_s: float = 0.0     # EVO INFERNO D: keeps its damage stage this long after a KILL
    ramp4_s: float = 0.0         # ...and reaches a 4th stage after ramp4_s at ramp4_mult x stage 3
    ramp4_mult: float = 0.0
    aura_r: float = 0.0          # EVO BABY D: moving wind aura -- enemies slowed, allies sped up
    aura_slow: float = 0.0
    aura_boost: float = 0.0
    volley_slow_every: int = 0   # EVO PRINCESS: every Nth volley SLOWS (7 s) in a wider blast
    volley_slow_s: float = 0.0
    first_hit_immune_s: float = 0.0  # EVO MINION HORDE: first hit taken -> invincible this long
    poison_dps: float = 0.0      # EVO DART GOBLIN: darts poison; stronger the longer he lives
    poison_stages: tuple = ()    # ...3-stage dps (51/115/307 by time alive, wiki vardefines)
    poison_s: float = 0.0
    # SIEGE DEAD ZONE (2026-08-15, wiki): the Mortar "has a blind spot, preventing it from
    # attacking enemies inside it" -- published range "3.5-11.5". Units closer than min_range
    # can neither be acquired nor shelled; rushing the Mortar IS its counterplay.
    min_range: float = 0.0
    # TOP-N SPELLS (wiki, Lightning & Vines): "the three troops that are targeted are always
    # the three that have the highest hitpoints within its radius" -- never the swarm.
    top_n_targets: int = 0
    # LINGERING ZONES: Poison ("low damage dealt every second for 8 seconds", move -15%),
    # Void (3 count-tiered hits over 4 s), Graveyard (timed edge spawns). One system.
    zone_s: float = 0.0
    zone_tick_s: float = 0.0
    zone_move_slow: float = 0.0
    zone_tiers: tuple = ()        # Void: ((max_targets, dmg, crown_dmg), ...) per tick
    zone_spawn_n: int = 0         # Graveyard: "a single Skeleton ... every 0.5 seconds
    zone_spawn_start_s: float = 0.0   # for 9 seconds on the edge of the spell's radius",
    zone_spawn_gap_s: float = 0.0     # first at 2.2 s, 12 total (x12, wiki attr table)
    zone_spawn_edge: bool = False
    # RONIN (wiki): "can block the attack of opposing melee troops and deal double the
    # damage to them every 3.5 seconds" -- the blocked swing lands nothing.
    parry_cd_s: float = 0.0
    # SKELETON BARREL (wiki 2026-08-16): "the player must account for the 0.5 second animation
    # where NEITHER THE BARREL NOR THE SKELETONS are considered as entities; if the spell is
    # cast during this phase, it will not affect the Skeletons." The death blast + knockback
    # land at once; the bodies arrive after this delay. That gap IS the log-timing skill.
    death_spawn_delay_s: float = 0.0
    # GOBLIN BARREL: thrown from the caster's KING TOWER, so its flight time grows with the
    # distance thrown -- the same physics the rocket already uses.
    lobbed: bool = False
    # DELAYED DEATH BOMBS (wiki): Balloon / Giant Skeleton / Bomb Tower drop "a bomb which
    # explodes after 3 seconds"; the Giant Skeleton's deals DOUBLE against Crown Towers.
    death_delay_s: float = 0.0
    death_crown_mult: float = 1.0
    # GOBLIN DEMOLISHER (wiki attr row: 50% || Very Fast (120) || 10 sec || Melee 0.5 || 2.5):
    # below enrage_frac he lights the dynamite -- very fast, melee, building-targeting,
    # detonating on connect or when the fuse runs out.
    enrage_frac: float = 0.0
    enrage_fuse_s: float = 0.0
    enrage_speed: float = 0.0
    enrage_reach: float = 0.0
    deploy_volley: int = 0       # EVO CANNON: cannonball fan on deployment (9 in 2 rows)
    volley_dmg: float = 0.0      # 304 per ball; crown towers take volley_crown (89)
    volley_crown: float = 0.0
    deploy_spawn: str = ""       # EVO ROYAL GHOST (Souldiers) / EVO SKARMY (the General):
    deploy_spawn_n: int = 0      # companions placed once per CARD at deploy
    low_hp_frac: float = 0.0     # EVO GOBLIN GIANT: below this hp fraction...
    low_hp_spawn_s: float = 0.0  # ...passively spawns its spawner unit every this many seconds
    army_ghosts: bool = False    # EVO SKARMY: its skeletons GHOST on death while the General lives
    carry_roll: bool = False     # EVO SNOWBALL: the roll GATHERS troops and drops them at the end
    drill_relocate: bool = False # EVO DRILL: resurfaces around the tower as it takes damage
    ram_bounce: bool = False     # EVO BATTLE RAM: bounces off the building and re-charges
    air_drop: bool = False       # EVO ROYAL HOGS: deploy AIRBORNE; fall on attacking/getting hurt
    air_drop_dmg: float = 0.0
    always_ghost: bool = False   # LJ GHOST: never unfades -- untargetable for its whole life
    ghost_life_s: float = 0.0    # ...which is this long (removed silently, no death effects)
    # LITTLE PRINCE: attack speed RAMPS while he keeps shooting from the same spot -- every
    # `atk_ramp_per` attacks the cadence multiplier steps through `atk_ramp_mults`
    # (1.2s -> 0.8s -> 0.4s = 1x/1.5x/3x). ANY movement or displacement resets it.
    atk_ramp_per: int = 0
    atk_ramp_mults: tuple = ()
    # ELIXIR PAID TO THE OPPONENT WHEN THIS UNIT DIES -- the Elixir Golem line's defining drawback
    # (Golem 1, each Golemite 0.5, each Blob 0.5 => up to 4 elixir back if the whole chain is
    # cleared, which is why a 3-elixir tank is not free value). Without it the sim modelled only
    # the upside and would happily learn that Elixir Golem is a bargain.
    elixir_death: float = 0.0
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
    charge_splash_r: float = 0.0  # a charged strike can also WIDEN the blast (Dark Prince 1.25 -> 2.2)
    # EVO BOMBER: "the bomb will bounce twice, 2.5 tiles apart in a straight line, dealing the same
    # damage ... as the initial hit"; since 16/12/2024 "enemies hit by Evolved Bomber's attack would
    # only take damage once" -- the three blasts share one hit set.
    bounce_n: int = 0
    bounce_tiles: float = 0.0
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
    # WEAPON LOAD TIME: the wind-up between acquiring a target and the FIRST hit landing
    # (game-file `load_time`; Archer 0.4 s, Knight 0.7 s, Musketeer 1.0 s). Subsequent hits then
    # come every hit_speed. Units used to hit the instant they entered reach, which quietly made
    # every defensive placement land its damage up to a second early -- the exact margin a
    # defence is judged on. 0 = fire immediately.
    load_time: float = 0.0
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
    hides: bool = False       # HIDDEN TESLA: retracts underground whenever nothing is in range
    hits_hidden: bool = False # this spell reaches a retracted building anyway (Earthquake)
    invis_time: float = 0.0   # ROYAL GHOST: seconds of NOT fighting before he fades out again
    spread: float = 0.0       # SHOTGUN half-angle in DEGREES that the pellets scatter within
    curse_dur: float = 0.0    # Mother Witch curse duration on struck enemy troops (seconds)
    hook_min: float = 0.0     # Fisherman hook starts only at/above this edge gap (tiles)
    hook_max: float = 0.0     # Fisherman hook reaches up to this edge gap (tiles)
    hook_time: float = 0.0    # Fisherman hook wind-up/execution time (seconds)
    hook_speed: float = 0.0   # Fisherman hook projectile speed (tiles/s), informational for now
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
    proj_width: float = 0.0   # HALF the published Projectile Width, in tiles: how wide the piercing
                              # line actually is. The Executioner's axe is published at width 2, and
                              # "the axe itself has a 1 tile radius, so his effective reach is 8.5"
                              # (7.5 throw + 1) -- so half-width is the number that does the work.
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
    if is_evo:
        # The import writes each evolution as its OWN `<base>_evo` row whose top-level fields ARE
        # the evo's stats (hp/damage/cycles/...). This function only ever read the BASE row plus a
        # curated `evolution:` dict -- so every imported evo silently fielded BASE stats (Evo
        # Bomber 304 hp instead of 332, and so on for all 41). Merge the evo row over the base;
        # `evolution` itself is excluded so a curated mechanics dict (our Knight/Tesla) still
        # applies through the overlay below.
        ev_row = db.get(key) or {}
        if ev_row:
            c = {**c, **{k: v for k, v in ev_row.items()
                         if v is not None and k not in ("evolution", "base", "display", "rarity")}}
    flags = set(db.flags(base))
    if is_evo:
        flags |= set((db.get(key) or {}).get("flags") or ())   # evo-only flags (Evo Snowball ROLLS)
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
    # `or` would have been wrong here: a speed of 0.0 is falsy, so a card declared STATIONARY fell
    # straight through to the "medium" default and walked. That is not a hypothetical -- the Phoenix
    # Egg's own KB comment said "stationary and harmless" while it strolled 2.9 tiles across the lane.
    _sp = db.speed_tiles(base)
    speed = _sp if _sp is not None else _SPEED.get(c.get("speed"), _SPEED["medium"])   # TILES/s
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
    # CR level scaling: HP + damage only. NOT 1.1^(level-11) -- the game floors a level-1 base
    # against a hand-authored percentage table that drifts off the 10% rule (256% at L11, not
    # 259%; 409% at L16, not 418%). See levels.py for how the table was derived and verified.
    # Scaling each stat through `scale()` reproduces the game's own rounding exactly.
    hp = _lv.scale(hp, level); dmg = _lv.scale(dmg, level)
    dps = _lv.scale(dps, level); tower_dmg = _lv.scale(tower_dmg, level)
    p_dmg = _lv.scale(p_dmg, level)
    sc = _lv.ratio(level)                                     # for stats with no integer base
    sight = float(db.sight_range_tiles(base))                  # per-troop aggro radius, TILES (from the KB)
    # SIEGE WIND-UP (2026-08-15, wiki attr tables): X-Bow and Mortar publish a 3.5 s deploy
    # time where everything else takes 1 s -- that window is the whole counterplay to an
    # offensive siege placement, and the sim was giving defenders 2.5 s less than the game.
    deploy_time = 0.0 if kind == "spell" else float(c.get("deploy_time_s") or 1.0)
    hit_dmg = dps * hit                                        # DPS delivered as one discrete hit every `hit` seconds
    ct = db.crown_tower_damage(base)                           # troops with a reduced crown value (Miner) hit towers softer
    tower_hit_dmg = float(ct) * sc if ct is not None else hit_dmg
    radius = float(db.collision_radius_tiles(base))             # body radius, TILES (cr-api-data)
    proj = db.projectile(base) or {}
    spawn_spec, spawn_count = None, 0
    if base == "royal_delivery":                              # RD drops ONE shielded Royal Recruit where it lands
        spawn_spec = build_spec(db, "royal_recruits", level)  # single-recruit combat stats (the Royal Recruits card)
        spawn_count = 1
    # GENERIC SPELL TROOP DROP (curated `spawns_troop`). Goblin Barrel resolved as a bare 120
    # blast and spawned NOTHING -- the damage row is the GOBLIN's swing, and the barrel drops
    # 3 goblins with zero impact damage. Every logbait deck in the pool was toothless.
    st = c.get("spawns_troop") or {}
    if spawn_spec is None and c.get("spawn_unit"):
        spawn_spec = build_spec(db, str(c["spawn_unit"]), level)   # Graveyard -> a single Skeleton
    if spawn_spec is None and st.get("unit") and st["unit"] != base:
        try:
            spawn_spec = build_spec(db, st["unit"], level)
            spawn_count = int(st.get("count") or 1)
        except Exception:                                     # noqa: BLE001 - unknown key: no drop
            spawn_spec = None
    # TROOP PRODUCTION. `db.spawner()` merges the wiki timings with the curated unit identity. The
    # guard on `unit != base` stops a self-referential curation from recursing forever, and a
    # missing/unknown unit key degrades to "not a spawner" rather than raising during a match.
    spw = dict(db.spawner(base) or {})
    if c.get("spawns"):
        spw.update(c["spawns"])          # an EVO row / curation may override the whole spawner
    spawner_spec = None                  # (Evo Furnace 2.4s, Evo Battle Ram -> EVO barbarians,
                                         # Evo Goblin Giant + Evo Lumberjack gain one outright)
    if spw and spw.get("unit") and spw["unit"] != base:
        try:
            spawner_spec = build_spec(db, spw["unit"], level)
        except Exception:                                     # noqa: BLE001 - unknown key: not a spawner
            spawner_spec = None
    spec = CardSpec(
        key=key, base=base, kind=kind, elixir=elixir, hp=hp, dps=dps, reach=reach, speed=speed,
        count=count, flying=(c.get("movement") == "air" if c.get("movement") else db.is_flying(base)),
        attacks_air=db.attacks_air(base),
        # splash: the stats import OR the curated flag. Testing only db.has_splash silently
        # single-targeted witch (flag curated but unread) and every flag-only splash troop.
        splash=db.has_splash(base) or ("splash" in set(db.flags(base))),
        splash_r=float(c.get("splash_radius_tiles") or c.get("splash_radius") or 0.0),
        reflect_dmg=float(c.get("reflect_damage") or 0.0) * sc,
        reflect_r=float(c.get("reflect_radius_tiles") or 0.0),
        reflect_stun=float(c.get("reflect_stun_s") or 0.0),
        building_only=building_only, siege=siege,
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
        death_knockback=float(c.get("death_knockback_tiles") or 0.0),
        knockback_all=("knockback_all" in flags),
        # either the curated flag OR the game files' ignore_pushback (imported as a plain field)
        knockback_immune=("knockback_immune" in flags) or bool(c.get("knockback_immune")),
        mass=db.mass(base),
        load_time=float(c.get("load_time_s") or 0.0),
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
        rage_r=float((c.get("drops_rage") or {}).get("radius_tiles") or 0.0),
        rage_dur=float((c.get("drops_rage") or {}).get("duration_s") or 0.0),
        rage_boost=float((c.get("drops_rage") or {}).get("boost") or 0.0),
        rage_delay=float((c.get("drops_rage") or {}).get("delay_s") or 0.0),
        egg_hatch=float((c.get("egg") or {}).get("hatch_s") or 0.0),
        egg_frac=float((c.get("egg") or {}).get("reborn_frac") or 0.0),
        recoil_dmg=float(c.get("recoil_damage") or 0.0) * sc,
        recoil_r=float(c.get("recoil_radius_tiles") or 0.0),
        spawn_on_hit=str(c.get("spawn_on_hit") or ""),
        spawn_on_hit_cap=int(c.get("spawn_on_hit_cap") or 0),
        charge_after_shield=bool(c.get("charge_after_shield")),
        hit_rage_s=float(c.get("hit_rage_s") or 0.0),
        hit_rage_boost=float(c.get("hit_rage_boost") or 0.0),
        attack_nado_r=float(c.get("attack_nado_radius_tiles") or 0.0),
        attack_nado_s=float(c.get("attack_nado_duration_s") or 0.0),
        attack_nado_dmg=float(c.get("attack_nado_damage") or 0.0) * sc,
        zap_pulses=int(c.get("zap_pulses") or 0),
        zap_step=float(c.get("zap_radius_step_tiles") or 0.0),
        kill_heal=float(c.get("kill_heal") or 0.0) * sc,
        overheal_frac=float(c.get("overheal_frac") or 1.0),
        mid_drop_frac=float(c.get("mid_drop_frac") or 0.0),
        hit_heal=float(c.get("hit_heal") or 0.0) * sc,
        atk_ramp_per=int((c.get("attack_ramp") or {}).get("per_stage") or 0),
        atk_ramp_mults=tuple(float(m) for m in (c.get("attack_ramp") or {}).get("mults") or ()),
        sniper_shots=int(c.get("sniper_shots") or 0),
        sniper_mult=float(c.get("sniper_mult") or 0.0),
        power_mult=float(c.get("power_mult") or 0.0),
        power_min=float(c.get("power_min") or 0.0),
        spark_dps_big=float(c.get("spark_dps_large") or 0.0) * sc,
        spark_dps_small=float(c.get("spark_dps_small") or 0.0) * sc,
        spark_dur=float(c.get("spark_duration_s") or 0.0),
        spark_r=float(c.get("spark_radius_tiles") or 0.0),
        javelin_dmg=float(c.get("javelin_damage") or 0.0) * sc,
        javelin_cd=float(c.get("javelin_cd_s") or 0.0),
        decoy_mirror=str(c.get("decoy_mirror") or ""),
        uppercut_tiles=float(c.get("uppercut_tiles") or 0.0),
        smash_range=float(c.get("smash_range_tiles") or 0.0),
        smash_knock=float(c.get("smash_knockback_tiles") or 0.0),
        net_cd=float(c.get("net_cd_s") or 0.0),
        net_root_s=float(c.get("net_root_s") or 0.0),
        net_range=float(c.get("net_range_tiles") or 0.0),
        shield_burst_dmg=float(c.get("shield_burst_damage") or 0.0) * sc,
        shield_burst_r=float(c.get("shield_burst_radius_tiles") or 0.0),
        shield_burst_knock=float(c.get("shield_burst_knockback_tiles") or 0.0),
        spawn_death_heal=float(c.get("spawn_death_heal") or 0.0) * sc,
        ramp_keep_s=float(c.get("ramp_keep_s") or 0.0),
        ramp4_s=float(c.get("ramp_stage4_s") or 0.0),
        ramp4_mult=float(c.get("ramp_stage4_mult") or 0.0),
        aura_r=float(c.get("aura_radius_tiles") or 0.0),
        aura_slow=float(c.get("aura_slow_frac") or 0.0),
        aura_boost=float(c.get("aura_boost_frac") or 0.0),
        volley_slow_every=int(c.get("volley_slow_every") or 0),
        volley_slow_s=float(c.get("volley_slow_s") or 0.0),
        first_hit_immune_s=float(c.get("first_hit_immune_s") or 0.0),
        poison_dps=float(c.get("poison_dps") or 0.0) * sc,
        poison_stages=tuple(float(v) * sc for v in (c.get("poison_stages") or ())),
        poison_s=float(c.get("poison_s") or 0.0),
        min_range=float(c.get("min_range_tiles") or 0.0),
        top_n_targets=int(c.get("top_n_targets") or 0),
        zone_s=float(c.get("zone_s") or 0.0),
        zone_tick_s=float(c.get("zone_tick_s") or 0.0),
        zone_move_slow=float(c.get("zone_move_slow") or 0.0),
        zone_tiers=tuple((int(t[0]), float(t[1]) * sc, float(t[2]) * sc)
                         for t in (c.get("zone_tiers") or ())),
        zone_spawn_n=int(c.get("zone_spawn_n") or 0),
        zone_spawn_start_s=float(c.get("zone_spawn_start_s") or 0.0),
        zone_spawn_gap_s=float(c.get("zone_spawn_gap_s") or 0.0),
        zone_spawn_edge=bool(c.get("zone_spawn_edge")),
        parry_cd_s=float(c.get("parry_cd_s") or 0.0),
        death_spawn_delay_s=float(c.get("death_spawn_delay_s") or 0.0),
        lobbed=bool(c.get("lobbed")),
        death_delay_s=float(c.get("death_delay_s") or 0.0),
        death_crown_mult=float(c.get("death_crown_mult") or 1.0),
        enrage_frac=float(c.get("enrage_frac") or 0.0),
        enrage_fuse_s=float(c.get("enrage_fuse_s") or 0.0),
        enrage_speed=float(c.get("enrage_speed") or 0.0),
        enrage_reach=float(c.get("enrage_reach") or 0.0),
        deploy_volley=int(c.get("deploy_volley") or 0),
        volley_dmg=float(c.get("volley_damage") or 0.0) * sc,
        volley_crown=float(c.get("volley_crown_damage") or 0.0) * sc,
        deploy_spawn=str(c.get("deploy_spawn") or ""),
        deploy_spawn_n=int(c.get("deploy_spawn_n") or 0),
        low_hp_frac=float(c.get("low_hp_frac") or 0.0),
        low_hp_spawn_s=float(c.get("low_hp_interval_s") or 0.0),
        army_ghosts=bool(c.get("army_ghosts")),
        carry_roll=bool(c.get("carry_roll")),
        drill_relocate=bool(c.get("drill_relocate")),
        ram_bounce=bool(c.get("ram_bounce")),
        air_drop=bool(c.get("air_drop")),
        air_drop_dmg=float(c.get("air_drop_damage") or 0.0) * sc,
        always_ghost=bool(c.get("always_ghost")),
        ghost_life_s=float(c.get("ghost_life_s") or 0.0),
        elixir_death=float(c.get("elixir_on_death") or 0.0),   # NOT level-scaled: it is a flat refund
        # DEPLOY/SURFACE blast (Mega Knight landing 430 over 1.3 tiles, Goblin Drill surfacing 84).
        # Radius falls back to the card's splash radius, which is the circle the wiki describes.
        spawn_dmg=float(c.get("spawn_damage") or 0.0) * sc,
        spawn_radius=float(c.get("spawn_radius_tiles") or c.get("splash_radius")
                           or (_SPLASH_R if c.get("spawn_damage") else 0.0)),
        spawn_crown_dmg=float(c.get("spawn_crown_damage") or 0.0) * sc,
        combo_every=int(c.get("combo_every") or 0),
        # Bandit publishes dash_damage/dash_time_s, Mega Knight jump_damage/jump_time_s -- one
        # mechanic, so they fold into the same fields. Trigger ranges come from the lead paragraph
        # (Bandit 3.5-6, Mega Knight 3.5-5) and are curated because they are prose, not a table.
        leap_dmg=float(c.get("dash_damage") or c.get("jump_damage") or 0.0) * sc,
        leap_time=float(c.get("dash_time_s") or c.get("jump_time_s") or 0.0),
        leap_speed=float(c.get("leap_speed_tiles") or 0.0),
        leap_splash=float(c.get("leap_splash_tiles") or 0.0),
        leap_min=float(c.get("leap_min_tiles") or 0.0),
        leap_max=float(c.get("leap_max_tiles") or 0.0),
        leap_invuln=bool(c.get("leap_invulnerable")),
        leap_towers=bool(c.get("leap_towers")),
        ability_cost=float(c.get("ability_cost") or 0.0),
        ability_uses=int(c.get("ability_uses") or 0),
        ability_cd=float(c.get("ability_cooldown_s") or 0.0),
        ability_invis=float(c.get("ability_invis_s") or 0.0),
        ability_back=float(c.get("ability_back_tiles") or 0.0),
        # Bomb damage is a level-scaled stat like any other, so it goes through scale() rather than
        # the flat `sc` ratio -- that is what reproduces the game's own rounding off the level table.
        ability_bomb_dmg=_lv.scale(float(c.get("ability_bomb_damage") or 0.0), level),
        recoil=float(c.get("recoil_tiles") or 0.0),
        ability_bomb_radius=float(c.get("ability_bomb_radius") or 0.0),
        ability_bomb_knock=float(c.get("ability_bomb_knockback") or 0.0),
        ability_delay=float(c.get("ability_delay_s") or 0.0),
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
        charge_splash_r=float(c.get("charge_splash_radius_tiles") or 0.0),
        bounce_n=int(c.get("bounces") or 0),
        bounce_tiles=float(c.get("bounce_tiles") or 0.0),
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
        proj_width=float(proj.get("width") or 0.0),
        hides=("hides" in flags),
        hits_hidden=("hits_hidden" in flags),
        invis_time=float(c.get("invisibility_time_s") or 0.0),
        spread=float(c.get("spread_degrees") or 0.0),
        curse_dur=float(c.get("curse_duration_s") or 0.0),
        hook_min=float(c.get("hook_min_tiles") or 0.0),
        hook_max=float(c.get("hook_max_tiles") or 0.0),
        hook_time=float(c.get("hook_time_s") or 0.0),
        hook_speed=float(c.get("hook_speed_tiles") or 0.0),
        proj_pierce=bool(proj.get("pierce")))
    # MIXED SQUADS. Each component is the SAME card with its own body swapped in, so it inherits
    # everything the wiki publishes once for the whole card (elixir, splash, collision radius, the
    # crown-tower ratio) and overrides only what its own attributes row states. `damage` here is
    # PER HIT, exactly as in the parent path, so dps is derived rather than trusted.
    comps = c.get("components") or ()
    if kind != "spell" and len(comps) > 1:
        subs = []
        total = sum(max(1, int(cm.get("count") or 1)) for cm in comps)
        # Per-member BODY radius (cards.yaml `component_collision_tiles`, index-aligned with the
        # KB component rows). The card-level collision radius is really the BIGGEST member's --
        # sharing it gave the Rascal girls the boy's 0.75-tile body, twice their real size.
        comp_r = c.get("component_collision_tiles") or ()
        for ci, cm in enumerate(comps):
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
                radius=(float(comp_r[ci]) if ci < len(comp_r) and comp_r[ci] else spec.radius),
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
    loaded: bool = False         # weapon is raised: the load_time wind-up has already been paid
                                 # for the CURRENT engagement. Cleared on losing reach, so a unit
                                 # that gets kited or knocked back has to wind up again.
    deploy_left: float = 0.0     # deploy delay remaining (can't act while > 0)
    slow_left: float = 0.0       # SLOW status timer (halved move + attack speed)
    stun_left: float = 0.0       # STUN / FREEZE status timer (can't act while > 0)
    pulse_cd: float = 0.0        # Evo Tesla: time until its next area-shock pulse
    shield_left: float = 0.0     # SHIELD pool remaining -- absorbs damage before hp (init from spec.shield_hp)
    dmg_mult: float = 1.0        # per-unit damage multiplier (Royal Chef pancake buff; 1.0 = normal)
    hatch_left: float = 0.0      # Phoenix EGG: survives this long -> hatches (0 = not an egg)
    hatch_frac: float = 1.0      # ...at this fraction of the parent's hp/damage (0.8 since 7/2/2023)
    hatch_spec: object = None    # ...into this spec (the ORIGINAL phoenix's, so level carries over)
    from_egg: bool = False       # reborn phoenix: no death blast, no second egg
    rage_self_left: float = 0.0  # EVO BARBARIANS: seconds of self-rage left (refreshed per swing)
    mid_drop_done: bool = False  # EVO SKEL BARREL: the 75%-hp barrel has been spent
    ramp_shots: int = 0          # LITTLE PRINCE: attacks landed since he last moved/was displaced
    sniper_left: int = 0         # EVO MUSKETEER: infinite-range rounds remaining
    javelin_left: float = 0.0    # EVO E-BARBS: cooldown until the next spear
    net_left: float = 0.0        # EVO HUNTER: cooldown until the next net
    iframes_left: float = 0.0    # EVO MINION HORDE: first-hit invincibility remaining
    iframes_used: bool = False
    poison_left: float = 0.0     # EVO DART GOBLIN: DoT seconds remaining on THIS unit
    poison_take: float = 0.0     # ...at this dps
    parry_ready_t: float = 0.0   # RONIN: engine time when the next parry is available
    enraged: bool = False        # GOBLIN DEMOLISHER: dynamite lit (spec swapped, fuse burning)
    fuse_left: float = 0.0
    last_unit_hit_t: float = -999.0   # engine time this body last took damage from an enemy
                                      # UNIT (never tower fire) -- the trade ledger's combat
                                      # attribution for LONG-RANGE defenders (X-Bow at 11.5)
    lowspawn_cd: float = 0.0     # EVO GOBLIN GIANT: next passive low-hp spawn
    ramp_hold: float = 0.0       # EVO INFERNO D: stage kept alive this long after a kill
    relocate_next: float = 0.75  # EVO DRILL: next hp fraction that triggers a resurface
    parent: object = None        # spawner linkage (EVO SKARMY ghosts die with their General)
    attacking: bool = False      # engaged (target in reach) this step -> Evo Knight's damage reduction is OFF
    locked: bool = False         # has ENGAGED its target (got in reach) -- a locked unit does not switch
                                 # targets just because something wandered closer; only an aggro RESET frees it
    aggro_reset: bool = False    # set by a stun/freeze, a Log knockback, or being SHOVED out of reach of what
                                 # it was hitting -- consumed by _acquire, which then re-picks from scratch
    gen_count: int = 0           # elixir units this pump has already paid out (spec.gen_every > 0 only)
    blast_done: bool = False     # its DEPLOY/SURFACE blast has already fired (Mega Knight, Goblin Drill)
    hidden: bool = False         # HIDDEN TESLA: retracted underground -- untargetable and immune
    ghost: bool = False          # ROYAL GHOST: currently faded out -- untargetable, but NOT immune
    refade_left: float = 0.0     # seconds of not fighting still to run before he fades back out
    hit_no: int = 0              # attacks landed -- drives Monk's 3-strike combo
    leap_left: float = 0.0       # seconds of dash/jump WIND-UP still to run (stationary)
    leap_go: bool = False        # airborne: past the wind-up, travelling at leap_speed
    invis_left: float = 0.0      # seconds of ability invisibility left (untargetable + immune)
    ability_left: int = -1       # activations remaining (-1 = not initialised from the spec yet)
    ability_cd_left: float = 0.0  # seconds until the ability can be used again
    ability_hp_frac: float = 0.0  # HP fraction that triggers the next ability use -- ROLLED per unit
                                  # (and re-rolled lower after each use) so the trigger timing varies
    spawn_cd: float = 0.0        # time until this spawner's next production tick
    focus_time: float = 0.0      # seconds locked on the CURRENT target -- drives ramp-up damage
    slow_mult: float = 1.0       # movement/attack multiplier from whatever slowed this unit
    charge_dist: float = 0.0     # tiles walked without attacking -- arms the charge bonus
    hook_left: float = 0.0       # Fisherman: seconds remaining in an active hook-pull motion
    hook_windup_left: float = 0.0  # fixed pre-throw wind-up time
    hook_out_left: float = 0.0   # hook projectile travel time OUT to target
    hook_pull_left: float = 0.0  # return leg time while the pull movement happens
    hook_mode: str = ""          # "self" (pull self to building/tower) or "target" (pull enemy troop in)
    hook_kind: str = ""          # pending land-hit kind once the pull completes ("unit"/"tower")
    hook_ref: object = None      # body being pulled to/from during the active hook
    curse_left: float = 0.0      # active curse timer (seconds remaining)
    cursed_by: int = -1          # team that cursed this unit (-1 = none)
    curse_level: int = 11        # level to use for the spawned Mother Witch Hog
    fisherman_slowed: bool = False

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
    first_hit: float = 0.8        # delay before the first shot after ENGAGING (see `engaged`)
    reload_left: float = 0.0      # time until the next shot is ready
    acquired: bool = False        # currently locked onto a target (first-hit bookkeeping)
    engaged: bool = False         # had a target LAST tick -- the weapon is already up, so swapping
                                  # targets does not pay the wind-up again. Only an idle gap does.
    target: object = None         # sticky target lock; closer enemies do not steal aggro mid-fight
    aggro_reset: bool = False     # stun/freeze breaks the lock; the next shot re-acquires from scratch
    ammo: float = 0.0             # Dagger Duchess: daggers left in the loaded clip
    ammo_max: float = 0.0         # clip size (0 = not a Dagger Duchess)
    empty_hit_speed: float = 0.0  # slower cadence once the clip is empty
    ammo_regen_s: float = 0.0     # seconds to reload one dagger while idle
    cook_period: float = 0.0      # Royal Chef: seconds between pancakes (0 = not a Royal Chef)
    cook_left: float = 0.0        # time until the next pancake
    buff_mult: float = 1.0        # pancake buff (~+1 level) applied to HP + damage
    buff_min_frac: float = 0.33   # only feed a troop above this fraction of its max HP
    stun_left: float = 0.0        # STUN / FREEZE status timer (can't act while > 0)
    slow_left: float = 0.0        # SLOW status timer (halved attack speed)
    slow_mult: float = 1.0        # movement/attack multiplier from whatever slowed this tower
    fisherman_slowed: bool = False


@dataclass
class _Spell:
    team: int
    x: float
    y: float
    spec: CardSpec
    t: float                      # time remaining until it lands
    r_override: float = 0.0       # EVO ZAP echo: this pulse's radius (0 = the spec's own)
    echoes: int = 0               # EVO ZAP: growing-ring pulses still to fire after this one


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
class _Zone:
    """A lingering AREA effect pinned to the ground: Poison's 8 s damage-over-time field,
    Void's count-tiered pulses, Graveyard's timed skeleton ring. Ticks in advance()."""

    def __init__(self, team: int, x: float, y: float, spec: CardSpec, left: float):
        self.team, self.x, self.y, self.spec, self.left = team, x, y, spec, left
        self.tick_in = spec.zone_tick_s if spec.zone_tick_s > 0.0 else (left + 1.0)
        self.age = 0.0
        self.spawned = 0


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
    width: float = 0.0         # half-width of a piercing line, TILES (0 -> the 0.5 default)
    dirx: float = 0.0          # FIXED heading for a piercing shot, normalised units per tile of
    diry: float = 0.0          # travel. Steering at `tx,ty` every tick made the shot turn round
                               # the instant it passed the aim point instead of flying on through.
    hit: set = field(default_factory=set)   # ids already damaged by a piercing shot
    stop_on_hit: bool = False  # a SHOTGUN PELLET: flies straight, but stops in the first body it hits
    ox: float = 0.0            # where it was fired from -- the BOOMERANG flies back to here
    oy: float = 0.0
    returning: bool = False    # on the return leg (Executioner's axe hits again on the way back)
    bounces_left: int = 0      # EVO BOMBER: area blasts still to chain past this impact (2.5t apart)
    # EVO FC: per-0.25s tick damage of the ONE lingering spark zone this shot leaves WHERE ITS
    # FLIGHT ENDS -- the carrier drops a large zone on the target it hit, each shrapnel bolt drops a
    # small one at the end of its run. It used to drop a zone every 1.25 tiles along the WHOLE path,
    # for the carrier and all five bolts, which at 11 tiles of shrapnel range carpeted most of a lane
    # in damage-over-time (user report: "covering too much space"). 0 = this shot leaves none.
    spark_end_dmg: float = 0.0


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


def _push_mass(spec) -> float:
    """How hard a body is to SHOVE -- the game's own `mass`, not a guess from its size.

    Body-blocking used to split every push 50/50, so a 0.5-radius 81 hp Skeleton moved a 0.75-radius
    3968 hp Giant exactly as far as the Giant moved it. MEASURED: six Skeletons cut a Giant to 34% of
    its unblocked pace and nine to 30% -- a swarm was stopping a tank dead, which is not a play that
    exists in the game.

    The fix for that was `radius ** 3`, on the stated grounds that CR's mass "is not published as a
    field, only named in prose". That was wrong: the game files publish `mass` for all 119
    characters, and the volume approximation missed badly in both directions. It put a Giant at 3.4x
    a Skeleton where the game says 18x, and -- worse -- it gave Knight, Musketeer, Archer, Skeleton,
    Goblin and Bat the SAME shoving weight, because they all share a 0.5 collision radius, when
    their real masses are 6, 5, 3, 1, 2 and 1. Size and heft are simply different fields.

    `spec.mass` is None for the handful of cards released after the dump froze; those keep the old
    volume estimate rather than defaulting to weightless.
    """
    m = getattr(spec, "mass", None)
    return float(m) if m else float(spec.radius) ** 3 * 48.0   # 48: volume->mass at the 0.5/6 anchor


_PULL_MASS_REF = 4.0     # mass that gets the FULL pull; heavier units scale down from here


def _pull_resist(spec) -> float:
    """How much of the Tornado's pull this body actually takes, from its MASS.

    The wiki states it plainly -- "the Tornado's pull strength is also affected by mass", and the
    Tornado guides that "a Hog Rider, Lumberjack, or Mini P.E.K.K.A are relatively light, so the
    Tornado will displace them further than a Valkyrie, Giant, or Golem", with Knight and Valkyrie
    "much more resilient".

    WHAT THIS REPLACES WAS DEAD CODE. The rule was `0.5 if radius >= _TANK_RADIUS else 1.0`, and
    _TANK_RADIUS is 0.9 while the LARGEST troop radius in the game is 0.75 (Giant / Golem /
    P.E.K.K.A). The branch could never fire, so every unit from a 1-mass Skeleton to a 20-mass
    Golem was hauled at the identical 11.2 tiles/s -- a Golem vortexed exactly as far as a
    Skeleton. It also repeated the collision-radius-as-heft mistake that `_push_mass` used to
    make: six units share a 0.5 radius with masses from 1 to 6.

    Inverse-linear in mass, which reproduces the ordering the guides describe: light swarm at the
    full pull, Knight/Valkyrie about two thirds, Giant/Golem/P.E.K.K.A about a fifth. The floor
    keeps a heavy unit from being perfectly immovable, since the Tornado does still shift them.

    SPEED RESISTANCE IS NOT ADDED HERE. "Any unit that is moving in the opposite direction ... will
    resist the pull" -- but units keep walking under their own power while the vortex is active, so
    that opposition is already in the simulation. Modelling it again would double-count it.
    """
    m = getattr(spec, "mass", None)
    if not m:
        return 0.5 if spec.radius >= 0.7 else 1.0    # pre-2023-dump cards: fall back on size
    return max(0.1, min(1.0, _PULL_MASS_REF / float(m)))


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
        self.splash_events: list = []   # (x, y, radius_tiles, t) of recent splash hits -- sim_view
        self.rage_zones: list = []      # (x, y, r_tiles, team, t_on, t_off, boost) -- Lumberjack's bottle
        self.spark_zones: list = []     # [x, y, r, team, t_end, tick_dmg, next_tick_t] -- Evo FC trails
                                        # flashes each as a brief AOE circle (~0.15 s), capped at 40
        # Tower Troops: per-troop HP + discrete-hit attack (CR wiki, L15). Your side plays my_tower_troop at
        # my_tower_level; the opponent rolls a troop (weighted) + a ladder level per match (see reset()).
        self.tower_ref_level = int(cfg.get("sim", "my_tower_level", default=15))
        # WEAPON LOAD TIME -- implemented, data imported for 83 cards, DEFAULT OFF. It is a real
        # mechanic (a Valkyrie's first swing lands 1.4 s after she engages, not instantly), and
        # switching it on is a one-line config change. It is off because turning it on surfaced a
        # PRE-EXISTING bug rather than a clean improvement: a unit sitting exactly at the edge of
        # its reach flickers in and out of engagement, and while it was firing on the tick it
        # arrived that flicker was invisible. Add a wind-up and the unit spends the gap unlocked,
        # drifts forward, re-acquires, and repeats -- a Musketeer holding station against a Bomb
        # Tower oscillated over ~0.5 tiles with no enemy touching her. The honest fix is reach
        # hysteresis (engage at `reach`, disengage only past `reach + margin`), which is a real
        # change to targeting and wants its own measured run rather than a late-night default.
        self.load_time_on = bool(cfg.get("sim", "load_time", default=False))
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
        self.river_width = float(board.get("river_width_tiles", 2.0))
        pt = list(board.get("princess_tile", [3.5, 6.5]))      # [x from the side wall, y from the back wall]
        kt = list(board.get("king_tile", [9.0, 3.0]))
        configure_board(self.tiles_x, self.tiles_y, self.bridge_tiles, self.bridge_width,
                        self.river_width)
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
        self.zones: List[_Zone] = []             # lingering areas: Poison / Void / Graveyard
        self._pending: list = []                 # (fire_t, team, spec, x, y) action-latency queue
        self._volleys: list = []                 # (land_t, team, x, y, spec): Evo Cannon barrage rings
        self._late_spawns: list = []             # (due_t, spec, team, x, y, n): barrel-limbo bodies
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
        """Build one Tower from a tower-troop profile (config/wiki stats at my_tower_level), scaling to
        the opponent's rolled level on the TOWER tables -- which are not the card table and not each
        other: a Princess Tower gains 8% per level, the King's Tower 7%, cards 10%. Damage is one
        shared progression across both towers. Using 1.1^(level-ref) here was the worst place to
        approximate, because tower HP is the denominator of every chip-damage reward."""
        prof = self.king_profile if king else self.tower_troops.get(troop, self.tower_troops.get("princess", {}))
        ref = self.tower_ref_level
        hp = _lv.tower_scale(float(prof.get("hp", 4424.0)), level, ref, king=king)
        sc = _lv.tower_scale(1.0, level, ref, king=king, damage=True)   # shared damage table
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

    def champion_ability(self, team: int) -> bool:
        """EXPLOSIVE ESCAPE -- the Mighty Miner's 1-elixir ability, as a PLAYER action.

        Unlike the automatic invisibility reaction (see the ability block in _tick_units), this is
        chosen: the env exposes it as its own action-space slot and calls straight through here.

        The wiki's sequence, and each part matters to how it is used: after a short delay he becomes
        intangible and moves to the HORIZONTALLY MIRRORED position -- same depth, opposite lane --
        leaving a bomb at the position he left, which detonates for area damage to ground AND air
        with knockback. So it is simultaneously an escape, a lane switch, and a swarm answer, which
        is why triggering it too early is the classic way to waste it: the bomb wants their counter
        already committed and standing on him.

        The bomb is resolved through the same fused-spell path the Balloon and Giant Skeleton death
        bombs use, so it inherits their delay, knockback and ground/air rules rather than
        re-implementing them. Returns False when there is no champion on the board, the ability is
        still cooling down, or the elixir is not there.
        """
        if self.done:
            return False
        champ = next((u for u in self.units
                      if u.team == team and u.hp > 0 and u.spec.ability_bomb_dmg > 0.0), None)
        if champ is None or champ.ability_cd_left > 0.0:
            return False
        s = champ.spec
        if self.elixir[team] < s.ability_cost:
            return False
        self.elixir[team] -= s.ability_cost
        champ.ability_cd_left = s.ability_cd
        ox, oy = champ.x, champ.y
        # THE BOMB, left where he was standing. Built off his own spec so it keeps his team and
        # level scaling, with every unrelated spell behaviour explicitly cleared -- the same
        # defensive `replace` the death-bomb path uses, because a stray `pulls`/`rolls`/`spawn_count`
        # inherited from the source card is exactly how a bomb quietly becomes a tornado.
        bomb = replace(s, kind="spell", spell_dmg=s.ability_bomb_dmg,
                       spell_radius=s.ability_bomb_radius or 2.0,
                       spell_tower_dmg=0.0,          # the escape bomb is not tower damage
                       knockback=s.ability_bomb_knock, ground_only=False,
                       pulls=False, rolls=False, zone_s=0.0, top_n_targets=0,
                       spawn_count=0, decoy_mirror=False, zap_pulses=0,
                       death_dmg=0.0, death_delay_s=0.0,
                       stuns=False, stun_dur=0.0, slows=False, slow_dur=0.0, freezes=False)
        self.spells.append(_Spell(team, ox, oy, bomb, max(0.0, s.ability_delay)))
        # ...and he is gone: mirrored across the arena's centre line, untargetable for the transit.
        champ.x = 1.0 - ox
        champ.invis_left = max(champ.invis_left, s.ability_delay)
        champ.target = None
        return True

    def deploy(self, team: int, spec: CardSpec, x: float, y: float,
               delay_s: float = 0.0) -> bool:
        if self.done or not self.can_afford(team, spec):
            return False
        # REAL-GAME TILE SNAP (2026-08-15): the game quantizes every placement -- troop or
        # spell reticle -- to the tile the tap lands in. The sim placed at the continuous
        # action-cell centre, a systematic half-tile disagreement with what the same action
        # does live. Same quantization here, BEFORE the field-shape rules (which move whole
        # tiles and so stay tile-aligned).
        x = (min(int(_TILES_X) - 1, max(0, int(x * _TILES_X))) + 0.5) / _TILES_X
        y = (min(int(_TILES_Y) - 1, max(0, int(y * _TILES_Y))) + 0.5) / _TILES_Y
        if spec.kind != "spell":
            # FIELD SHAPE (2026-08-14, user-verified): same board-truth as the mask
            # (actions.unplayable) -- the outermost SINGLE column beside the water is ledge
            # decor, the back rows exist only in the 1x6 strip behind each king, and the king
            # platforms are structures. Scripted opponents snap inward/forward here so the
            # sim never fields a unit where the live game could not.
            from ..actions import (KING_STRIP_X0, KING_STRIP_X1, KING_Y0, KING_Y1,
                                   LEDGE_X_FRAC, LEDGE_Y0, LEDGE_Y1)
            half_col, half_row = 0.5 / _TILES_X, 0.5 / _TILES_Y
            if LEDGE_Y0 <= y <= LEDGE_Y1:
                if x < LEDGE_X_FRAC:
                    x = LEDGE_X_FRAC + half_col
                elif x > 1.0 - LEDGE_X_FRAC:
                    x = 1.0 - LEDGE_X_FRAC - half_col
            if not (KING_STRIP_X0 < x < KING_STRIP_X1):
                y = min(max(y, KING_Y0 + half_row), 1.0 - KING_Y0 - half_row)   # back-row corners are decor
            elif KING_Y0 <= y <= KING_Y1:
                y = KING_Y1 + half_row                     # off the enemy king's platform, in front
            elif 1.0 - KING_Y1 <= y <= 1.0 - KING_Y0:
                y = 1.0 - KING_Y1 - half_row               # off YOUR king's platform, in front
        self.elixir[team] -= spec.elixir
        self.last_deploy[team] = (spec, x, y, self.t)
        if delay_s > 0.0:
            # ACTION LATENCY (2026-08-15): live, a decision becomes a tap becomes a game event
            # ~0.25 s later; the sim applied it instantly, so the sim policy never had to LEAD.
            # Elixir is committed at decision time (matches the live bar), the effect lands
            # when the tap would. Opponent scripts pass no delay -- their cadence already
            # models a player's decision rate, not our tap pipeline.
            self._pending.append((self.t + delay_s, team, spec, x, y))
            return True
        return self._finish_deploy(team, spec, x, y)

    def _finish_deploy(self, team: int, spec: CardSpec, x: float, y: float) -> bool:
        if spec.kind == "spell":
            delay = spec.spell_delay
            if spec.base == "rocket" or spec.lobbed:
                # FLIGHT TIME grows with distance from the launcher. The rocket is fired from
                # your side; the GOBLIN BARREL is thrown from the King's Tower (wiki), and its
                # shadow crossing the arena is what a defender reads to time the counter --
                # "deploy the Mega Knight right as the Goblin Barrel's SHADOW crosses the
                # river". A flat 0.4 s delay gave the defender no such window to read.
                oy = 1.0 if team == 0 else 0.0
                delay = 0.4 + _dist(x, y, 0.5, oy) / _TILES_Y   # (live-parity physics; ~1.4s at max range)
            self.spells.append(_Spell(team, x, y, spec, delay,
                                      echoes=max(0, spec.zap_pulses - 1)))
            if spec.decoy_mirror:
                # EVO GOBLIN BARREL: "a second Goblin Barrel is launched alongside the first one,
                # which lands on its mirroring tile in the other lane" -- with the decoy goblins.
                try:
                    dspec = build_spec(self.db, spec.decoy_mirror, spec.level)
                    self.spells.append(_Spell(team, 1.0 - x, y, dspec, delay))
                except Exception:                             # noqa: BLE001 - bad curation: main only
                    pass
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
        if spec.deploy_spawn and spec.deploy_spawn_n > 0:
            # Deploy COMPANIONS, once per CARD (Evo Royal Ghost's 2 Souldiers, Evo Skarmy's
            # General): placed just behind the drop point, whatever formation the card itself uses.
            try:
                cs = build_spec(self.db, spec.deploy_spawn, spec.level)
                fwdc = 1.0 if team == 0 else -1.0
                for i in range(spec.deploy_spawn_n):
                    ox = (i - (spec.deploy_spawn_n - 1) / 2.0) * (2.2 * cs.radius) / _TILES_X
                    cx2, cy2 = _clamp_xy(x + ox, y + fwdc * 1.0 / _TILES_Y, cs.radius)
                    self._place(cs, team, cx2, cy2)
            except Exception:                                 # noqa: BLE001 - bad curation: no companions
                pass
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

    def _structure_overlap(self, spec: CardSpec, x: float, y: float) -> bool:
        """Would a body of `spec` centred at (x, y) overlap an existing STRUCTURE?
        Structures are buildings (either team) and alive crown towers. Troops collide with
        them too -- nothing can be deployed inside a footprint."""
        for e in self.units:
            if e.hp <= 0 or e.spec.kind != "building":
                continue
            if e.hidden and spec.kind != "building":
                # SUBMERGED TESLA (2026-08-15, user): while retracted it is UNDERGROUND -- troops
                # deploy onto and walk straight over its tile. It still blocks another BUILDING
                # (the ground is occupied), and it blocks normally the moment it pops up.
                continue
            if _dist(x, y, e.x, e.y) < spec.radius + e.spec.radius:
                return True
        for side in (0, 1):
            for tw in self.towers[side]:
                if tw.alive and _dist(x, y, tw.x, tw.y) < spec.radius + tw.radius:
                    return True
        return False

    def _snap_structure(self, spec: CardSpec, x: float, y: float) -> "tuple[float, float]":
        """Real CR refuses to place anything inside an existing footprint: dragging onto an
        occupied spot SNAPS the placement to the nearest free tile. The sim had no such rule --
        unit-vs-unit separation explicitly skips building/building pairs (they are both
        anchored), so two Teslas dropped on one tile simply co-existed inside each other,
        doubling the DPS of a single footprint (user report, 2026-08-15).

        TROOPS are snapped too (2026-08-15, same report). A troop dropped on a building did
        eventually get shoved out by _separate -- but only AFTER its ~1 s deploy freeze, since
        that pass skips still-spawning bodies. In game it never overlaps at all: it spawns
        beside the structure. Spawner children (hut goblins, tombstone skeletons) do NOT come
        through here; they are meant to pop out at their spawner and walk off.

        Search outward a tile at a time from the requested spot, nearest first, and take the
        first free legal tile. Sideways beats forward/back at equal distance, matching the
        game's own bias. If nothing within `rings` is free the original point is returned --
        placement still happens (never silently swallow a paid card), just overlapped.
        """
        if not self._structure_overlap(spec, x, y):
            return x, y
        step_x, step_y = 1.0 / _TILES_X, 1.0 / _TILES_Y
        cands = []
        for ring in range(1, 6):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue                      # only the new ring's perimeter
                    nx_, ny_ = x + dx * step_x, y + dy * step_y
                    cands.append((ring, abs(dy), abs(dx), nx_, ny_))
            cands.sort()
            for _r, _ady, _adx, nx_, ny_ in cands:
                nx_, ny_ = _clamp_xy(nx_, ny_, spec.radius)
                if (y - _RIVER) * (ny_ - _RIVER) < 0:
                    continue                          # never snap a building across the river
                if not self._ground_pos_ok(nx_, ny_, spec.radius):
                    continue                          # stay on legal ground (no water/edges)
                if not self._structure_overlap(spec, nx_, ny_):
                    return nx_, ny_
            cands = []
        return x, y

    def _place(self, spec: CardSpec, team: int, cx: float, cy: float) -> None:
        """Put ONE body on the board, already positioned. Shared by the swarm and mixed-squad paths."""
        cx, cy = self._snap_structure(spec, cx, cy)   # nothing deploys inside a footprint
        u = Unit(spec, team, cx, cy, spec.hp)
        u.deploy_left = spec.deploy_time              # ~1s before it can act (you can't instant-block)
        u.pulse_cd = spec.pulse_interval              # Evo Tesla: first area-shock after one interval
        u.sniper_left = spec.sniper_shots             # Evo Musketeer spawns with her 3 rounds loaded
        if spec.ghost_life_s > 0.0:                   # LJ ghost: vanishes silently after its time
            u.hatch_left = spec.ghost_life_s          # (hatch with no hatch_spec = timed removal)
        if spec.deploy_volley > 0:
            # EVO CANNON "Deploy Barrage" (2026-08-15, RoyaleAPI/wiki): NOT projectiles -- nine
            # impact RINGS appear at placement (5 across the front, 4 flanking the sides) and
            # land together a beat later, each dealing area damage in a 2.5-tile radius with a
            # 1-tile knockback; a target inside overlapping rings is damaged ONCE. Landing
            # delay curated at 1.0 s [verify].
            self._volleys.append((self.t + 1.0, team, cx, cy, spec))
        # ROYAL GHOST: "upon deployment, he will spawn INVISIBLE" -- stealth is his resting state,
        # not something he earns, so he arrives already faded and the first thing anyone sees is him
        # swinging. It is also why he cannot kite: he re-fades and the chaser forgets him.
        u.ghost = spec.invis_time > 0.0
        u.refade_left = spec.invis_time
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
        # Three ways to be UNSEEN, and they are not the same thing:
        #   invis_left -- Boss Bandit's Getaway Grenade: gone entirely, and immune with it
        #   ghost      -- Royal Ghost's stealth: "will not be targeted by opposing units, but can
        #                 still be hit by area damage or spells", so ONLY the targeting is blocked
        #   hidden     -- a retracted Tesla: "its underground mechanic prevents spell responses"
        # "The Royal Ghost will ignore an opposing Royal Ghost, a Suspicious Bush, a hidden Tesla,
        # or an invisible Archer Queen and bypass them" -- one rule, all four cases.
        if u.spec.min_range > 0.0 and _gap(u.x, u.y, e) < u.spec.min_range:
            return False                       # SIEGE DEAD ZONE: too close to shell (Mortar)
        return e.hp > 0 and e.invis_left <= 0.0 and not e.hidden and not e.ghost \
            and (not e.spec.flying or u.spec.attacks_air or u.spec.flying)

    def _march_gap(self, u: Unit, ref) -> float:
        """Distance in tiles to an enemy building/tower the way this unit actually TRAVELS:
        through its own lane's bridge whenever the river is in between.

        Plain euclidean had a genuine pathology the moment a princess tower died: from a deep
        back spawn in the towerless lane the OTHER princess is straight-line nearer than the
        King (~25 vs ~26.5 tiles), so a Lava Hound / Giant placed there marched diagonally
        across the whole map -- where the real game sends it up its lane to the King. Selection
        routes through the SAME bridge the movement code picks (nearest deck to u.x), so what a
        unit targets and where it walks can never disagree. AIR flies straight once committed,
        but its TARGET choice follows the same lane rule -- a back-lane Balloon/Lava Hound in an
        empty lane heads for the King, not the far princess."""
        if (u.y - _RIVER) * (ref.y - _RIVER) >= 0.0:
            return _gap(u.x, u.y, ref)                   # same side of the river: straight line
        bx = min(_BRIDGES, key=lambda b: abs(u.x - b))
        leg1 = math.hypot((bx - u.x) * _TILES_X, (_RIVER - u.y) * _TILES_Y)
        leg2 = math.hypot((ref.x - bx) * _TILES_X, (ref.y - _RIVER) * _TILES_Y)
        return max(0.0, leg1 + leg2 - _body_radius(ref))

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
                    g = self._march_gap(u, e)                 # lane-aware: see _march_gap
                    if g < best_gap:
                        best, best_gap, best_kind = e, g, "unit"
            for tw in towers:                                 # crown towers are buildings too
                g = self._march_gap(u, tw)
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
            if u.spec.hook_max > 0.0:
                reach = max(reach, u.spec.hook_max)           # Evo Goblin Cage: it can HOOK past its arms
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
            tw = min(towers, key=lambda t: self._march_gap(u, t))   # lane-aware, same as wincons
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
                tx, ty = lane_x, river_bank(u.y)             # off the deck -> walk to the BANK on its own
                                                             # side (the water has thickness; aiming at
                                                             # the centreline walked it INTO the river)
            else:
                tx, ty = u.x, ty                             # on the deck -> straight across
        tx, ty = self._steer_around_towers(u, tx, ty)        # towers are solid -> walk around them
        tx, ty = self._steer_around_allies(u, tx, ty)        # ...and STOPPED allies get walked around
        # step in TILES, then convert back per axis (one normalised unit != one tile on both axes)
        dxt, dyt = (tx - u.x) * _TILES_X, (ty - u.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d < 1e-6:
            return
        spd = u.spec.speed
        if (u.spec.charge_dmg > 0.0 and u.spec.charge_range > 0.0
                and u.charge_dist >= u.spec.charge_range
                and not (u.spec.charge_after_shield and u.shield_left > 0.0)):
            # CHARGE GALLOP (wiki, Prince): "With his increased speed and damage while
            # charging" -- an ARMED charge runs at double pace until the hit spends it.
            spd *= 2.0
        step = min(spd * spd_mult * dt, d)
        u.charge_dist += step                                # tiles covered without swinging -> arms a charge
        if step > 1e-9 and u.ramp_shots:
            u.ramp_shots = 0                                 # Little Prince: MOVING resets the ramp
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
                if ((a.hidden and b.spec.kind != "building")
                        or (b.hidden and a.spec.kind != "building")):
                    continue                          # a retracted Tesla is underground: walk over it
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
                a_anch = a.spec.kind == "building"
                b_anch = b.spec.kind == "building"
                if a.team == b.team and not (a_anch or b_anch):
                    # ALLY PUSH RULES (2026-08-15, user-verified). A STOPPED attacker is a
                    # WALL to similar-or-lighter allies -- the walker behind gets stuck
                    # instead of bulldozing the whole mass into whatever it is shooting.
                    # Only a clearly heavier body still displaces it (a Golem really does
                    # shove your Musketeer aside).
                    a_stop = a.attacking or a.locked
                    b_stop = b.attacking or b.locked
                    if a_stop and not b_stop and _push_mass(b.spec) <= _push_mass(a.spec) * 1.4:
                        a_anch = True
                    elif b_stop and not a_stop and _push_mass(a.spec) <= _push_mass(b.spec) * 1.4:
                        b_anch = True
                if a_anch and b_anch:
                    continue
                am = 0.0 if a_anch else _push_mass(a.spec)
                bm = 0.0 if b_anch else _push_mass(b.spec)
                if (a.team == b.team and am > 0.0 and bm > 0.0
                        and not (a.attacking or a.locked or b.attacking or b.locked)):
                    # Both WALKING: "the large disparity in speed makes up for the small
                    # disparity in mass" (wiki mass notes) -- a fast heavy pusher (Hog) shoves
                    # a slow mini-tank (Ice Golem) up the lane, while an equally-fast but tiny
                    # Goblin barely moves it. Speed surplus scales ALLY pushing power only; an
                    # enemy wall holding up a tank stays pure volume.
                    am *= 1.0 + max(0.0, a.spec.speed - b.spec.speed)
                    bm *= 1.0 + max(0.0, b.spec.speed - a.spec.speed)
                s = am + bm
                if s <= 0:
                    continue
                px, py = ux * overlap / _TILES_X, uy * overlap / _TILES_Y  # back to normalised, per axis
                # Each body yields in inverse proportion to its OWN mass, so the heavier one barely
                # moves: a Skeleton takes 77% of the separation against a Giant instead of 50%.
                # Buildings are fully anchored once placed: the entire separation is applied to the
                # non-building body, never to the building.
                if a_anch:
                    b.x, b.y = _clamp_xy(b.x - px, b.y - py, b.spec.radius)
                elif b_anch:
                    a.x, a.y = _clamp_xy(a.x + px, a.y + py, a.spec.radius)
                else:
                    a.x, a.y = _clamp_xy(a.x + px * (bm / s), a.y + py * (bm / s), a.spec.radius)
                    b.x, b.y = _clamp_xy(b.x - px * (am / s), b.y - py * (am / s), b.spec.radius)
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
        if self._pending:                                    # action-latency queue (see deploy)
            due = [p for p in self._pending if p[0] <= self.t]
            if due:
                self._pending = [p for p in self._pending if p[0] > self.t]
                for _, tm_, sp_, px_, py_ in due:
                    self._finish_deploy(tm_, sp_, px_, py_)
        if self._late_spawns:
            # SKELETON BARREL LIMBO: the bodies were promised when the barrel broke and only
            # arrive now. Nothing exists in between -- which is exactly why a spell cast during
            # the animation hits nothing, and why the log has to be timed to LAND here.
            due = [q for q in self._late_spawns if q[0] <= self.t]
            if due:
                self._late_spawns = [q for q in self._late_spawns if q[0] > self.t]
                for _t, sp_, tm_, px_, py_, n_ in due:
                    for i in range(n_):
                        ang = 2.0 * math.pi * (i / max(1, n_))
                        rr = sp_.radius * 2.0 + 0.25
                        sx, sy = _clamp_xy(px_ + math.cos(ang) * rr / _TILES_X,
                                           py_ + math.sin(ang) * rr / _TILES_Y, sp_.radius)
                        nu = Unit(sp_, tm_, sx, sy, sp_.hp)
                        nu.deploy_left = sp_.deploy_time
                        self.units.append(nu)
        if self._volleys:
            landing = [v for v in self._volleys if v[0] <= self.t]
            if landing:
                self._volleys = [v for v in self._volleys if v[0] > self.t]
                for _, tm_, vx_, vy_, sp_ in landing:
                    self._resolve_barrage(tm_, vx_, vy_, sp_)
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
            if u.spec.lifetime and u.deploy_left <= 0.0 and u.spec.kind == "building":
                # BUILDINGS ONLY (2026-08-15): the Goblin Demolisher's wiki "life 10" is his
                # lit-dynamite FUSE, not a lifetime -- his HP must not bleed from deploy.
                u.hp -= (u.spec.hp / u.spec.lifetime) * dt
        self._tick_spawners(dt)
        self._tick_zones(dt)
        self._tick_hatch(dt)
        if self.rage_zones:                                  # drop zones whose effect has ended
            self.rage_zones = [z for z in self.rage_zones if z[5] > self.t]
        self._auras = [(u.x, u.y, u.team, u.spec.aura_r, u.spec.aura_slow, u.spec.aura_boost)
                       for u in self.units
                       if u.spec.aura_r > 0.0 and u.hp > 0 and u.deploy_left <= 0.0]
        if self.spark_zones:                                 # Evo FC lingering sparks: DoT + move slow
            for z in list(self.spark_zones):
                if self.t >= z[4]:
                    self.spark_zones.remove(z)
                    continue
                if self.t >= z[6]:
                    z[6] = self.t + 0.25                     # "deal damage every 0.25 seconds"
                    for e in self.units:
                        if e.team != z[3] and e.hp > 0 \
                                and _dist(e.x, e.y, z[0], z[1]) <= z[2] + e.spec.radius:
                            self._hurt(e, z[5])
                            e.slow_left = max(e.slow_left, 0.3)   # 15% slow while standing in it
                            e.slow_mult = 0.85
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
            if u.rage_self_left > 0.0:
                u.rage_self_left = max(0.0, u.rage_self_left - dt)
            if u.iframes_left > 0.0:
                u.iframes_left = max(0.0, u.iframes_left - dt)
            if (u.spec.enrage_frac > 0.0 and not u.enraged and u.hp > 0.0
                    and u.hp <= u.spec.hp * u.spec.enrage_frac):
                # GOBLIN DEMOLISHER (wiki): "When his hitpoints are lowered below 50%, he
                # changes into a very fast, building-targeting troop that charges toward the
                # nearest building" -- one spec swap and every downstream system just works;
                # kamikaze makes the connect ITSELF the detonation (death blast + knockback).
                u.enraged = True
                u.fuse_left = u.spec.enrage_fuse_s
                u.spec = replace(u.spec, building_only=True, kamikaze=True,
                                 speed=(u.spec.enrage_speed or u.spec.speed * 2.0),
                                 reach=(u.spec.enrage_reach or u.spec.reach),
                                 proj_speed=0.0, splash=False)
                u.aggro_reset = True
                u.locked = False
                u.target = None
            if u.enraged and u.fuse_left > 0.0:
                u.fuse_left -= dt
                if u.fuse_left <= 0.0:
                    u.hp = -1.0                              # the fuse wins: detonate in place
            if u.poison_left > 0.0:                          # Evo Dart Goblin's poison ticks
                u.poison_left = max(0.0, u.poison_left - dt)
                u.hp -= u.poison_take * dt                   # DoT bypasses shields (spell-like)
            if u.ramp_hold > 0.0:
                u.ramp_hold = max(0.0, u.ramp_hold - dt)
                if u.ramp_hold <= 0.0 and not u.attacking:
                    u.focus_time = 0.0                       # the kept inferno stage finally expires
            if (u.spec.low_hp_spawn_s > 0.0 and u.spec.spawner_spec is not None
                    and u.deploy_left <= 0.0 and u.hp <= u.spec.hp * u.spec.low_hp_frac):
                u.lowspawn_cd -= dt                          # Evo Goblin Giant: passive goblins below 50%
                if u.lowspawn_cd <= 0.0:
                    u.lowspawn_cd = u.spec.low_hp_spawn_s
                    self._spawn_from(u, 1)
            if (u.spec.drill_relocate and u.deploy_left <= 0.0
                    and u.hp > 0 and u.hp <= u.spec.hp * u.relocate_next):
                # EVO GOBLIN DRILL: "submerges and reappears around the tower as it takes damage,
                # spawning Goblins each time" -- every quarter of its hp lost, it pops up on a new
                # side of the nearest enemy tower with a fresh goblin.
                u.relocate_next -= 0.25
                tws = [t for t in self._enemy_towers(u.team) if t.alive]
                if tws:
                    tw = min(tws, key=lambda t: _dist(u.x, u.y, t.x, t.y))
                    ang = self.rng.uniform(0.0, 6.283)
                    u.x, u.y = _clamp_xy(tw.x + math.cos(ang) * 2.0 / _TILES_X,
                                         tw.y + math.sin(ang) * 2.0 / _TILES_Y, u.spec.radius)
                    u.aggro_reset = True
                self._spawn_from(u, 1)
            if (u.spec.mid_drop_frac > 0.0 and not u.mid_drop_done and u.deploy_left <= 0.0
                    and u.hp <= u.spec.hp * u.spec.mid_drop_frac):
                # EVO SKELETON BARREL: "one dropped when it reaches 75% hitpoints" -- the first
                # barrel falls MID-FLIGHT with the same blast + skeleton payload as the death drop.
                u.mid_drop_done = True
                self._death_blast(u)
                self._spawn_from(u, u.spec.spawner_death)
            was_engaged = u.attacking
            u.attacking = False                             # default; set True only when engaged (target in reach)
            if not was_engaged:
                # Out of reach this tick -> the weapon is lowered again. This is what makes kiting
                # and knockback cost the attacker real time: it has to pay the wind-up afresh when
                # it re-engages, rather than resuming mid-swing.
                u.loaded = False
            if u.curse_left > 0.0:
                u.curse_left = max(0.0, u.curse_left - dt)
                if u.curse_left <= 0.0:
                    u.cursed_by = -1
            if u.deploy_left > 0:                            # still spawning -> can't act yet (~1s)
                u.deploy_left -= dt
                if u.deploy_left <= 0.0 and not u.blast_done:
                    u.blast_done = True
                    self._deploy_blast(u)                    # Mega Knight lands / Goblin Drill surfaces
                    if u.spec.pulse_dmg > 0.0:
                        self._pulse(u)                       # "After surfacing AND DEPLOYMENT"
                continue
            if u.stun_left > 0:                              # stunned / frozen -> can't act
                u.stun_left = max(0.0, u.stun_left - dt)
                continue
            if u.hook_left > 0.0:
                self._tick_hook(u, dt)
                continue
            if u.spec.pulse_interval > 0:                    # periodic area-shock (none ship with this today)
                u.pulse_cd -= dt
                if u.pulse_cd <= 0:
                    self._pulse(u)
                    u.pulse_cd = u.spec.pulse_interval
            spd = u.slow_mult if u.slow_left > 0 else 1.0
            if self.rage_zones or u.rage_self_left > 0.0:
                spd *= self._rage_mult(u)                   # rage: +30% move AND attack speed, no stacking
            if self._auras:
                for (ax, ay, at, ar, aslow, aboost) in self._auras:
                    d_a = _dist(u.x, u.y, ax, ay)
                    if d_a <= ar:                           # Evo Baby Dragon's gust: +30% friends, -30% foes
                        spd *= (1.0 + aboost) if u.team == at else (1.0 - aslow)
                        break
            if u.slow_left > 0:
                u.slow_left = max(0.0, u.slow_left - dt)
            # PLAYER-TRIGGERED ability cooldown + transit. The Boss Bandit block below ticks these
            # too, but only for cards with `ability_invis` -- so a champion whose ability is chosen
            # rather than automatic (the Mighty Miner) would fire once and never recharge, and would
            # stay permanently untargetable after his escape. Ticked here, before that branch, and
            # skipped for the automatic cards so their existing sequencing is untouched.
            if u.spec.ability_bomb_dmg > 0.0 and u.spec.ability_invis <= 0.0:
                u.ability_cd_left = max(0.0, u.ability_cd_left - dt)
                if u.invis_left > 0.0:
                    u.invis_left = max(0.0, u.invis_left - dt)
            # GETAWAY ABILITY (Boss Bandit). Fires automatically when she is genuinely in trouble --
            # she is invisible and untouchable for a second, then reappears `ability_back` tiles
            # further from the enemy, which is exactly the Rocket/spell dodge the card is played for.
            if u.spec.ability_invis > 0.0:
                if u.ability_left < 0:
                    u.ability_left = u.spec.ability_uses
                    # VARIED TRIGGER (2026-08-14). The threshold was a flat 0.6 -- every Boss
                    # Bandit vanished at exactly 60% HP, so a policy could learn the one timing
                    # that games a constant (the user's exact concern). Each unit now rolls its
                    # own trigger, and each USE re-rolls a meaningfully lower one, spreading the
                    # two grenades across her HP bar and across matches.
                    u.ability_hp_frac = self.rng.uniform(0.35, 0.80)
                u.ability_cd_left = max(0.0, u.ability_cd_left - dt)
                if u.invis_left > 0.0:
                    u.invis_left -= dt
                    if u.invis_left <= 0.0:                 # reappear BEHIND where she vanished
                        back = -1.0 if u.team == 1 else 1.0  # away from the enemy side
                        u.x, u.y = _clamp_xy(u.x, u.y + back * u.spec.ability_back / _TILES_Y,
                                             u.spec.radius)
                        u.ability_cd_left = u.spec.ability_cd
                        u.aggro_reset = True
                    continue                                 # invisible: no walking, no attacking
                if u.ability_left > 0 and u.ability_cd_left <= 0.0 \
                        and u.hp < u.spec.hp * u.ability_hp_frac \
                        and self.elixir[u.team] >= u.spec.ability_cost:
                    self.elixir[u.team] -= u.spec.ability_cost
                    u.ability_left -= 1
                    u.invis_left = u.spec.ability_invis
                    u.ability_hp_frac = self.rng.uniform(0.15, max(0.16, u.ability_hp_frac * 0.75))
                    # The only thing that drops a wind-up, and it is HER OWN doing, not the
                    # defender's -- she vanishes and reappears further back, so there is nothing
                    # left standing there to finish the dash.
                    u.leap_left = 0.0
                    continue
            prev_target = u.target
            kind, ref = self._acquire(u)
            # HIDDEN TESLA. "When there are no enemies within range, it retracts underground, making
            # itself immune to all damage except for the Earthquake and the Freeze." So the retract
            # is driven by exactly the same targeting test it uses to shoot -- nothing in range means
            # nothing to come up for. While under it is untargetable (`_valid_foe`), which is what
            # makes it survive the spell that would otherwise trade up on it, and what lets it eat a
            # Hog's whole run: he cannot lock it until it surfaces in his face.
            if u.spec.hides:
                if ref is None:
                    u.hidden = True
                    continue
                if u.hidden:
                    u.hidden = False
                    # EVO TESLA: a pulse on EVERY surfacing, not on a timer -- "the Tesla will close
                    # and open again", which is how you get two pulses out of one building.
                    if u.spec.pulse_dmg > 0.0:
                        self._pulse(u)
            # RAMP-UP bookkeeping: the damage stages climb only while this unit stays on ONE target,
            # and drop straight back to stage 1 the instant the target changes -- which is why a stun,
            # a knockback or simply feeding a fresh body resets an Inferno.
            if u.target is not prev_target:
                if (u.spec.ramp_keep_s > 0.0 and prev_target is not None
                        and isinstance(prev_target, Unit) and prev_target.hp <= 0):
                    # EVO INFERNO DRAGON: "once [it] defeats a troop ... it remains on that damage
                    # state" for ramp_keep_s unless it is stunned or goes that long without a hit.
                    u.ramp_hold = u.spec.ramp_keep_s
                else:
                    u.focus_time = 0.0
            if ref is None:
                continue
            if kind is None:
                continue
            if u.spec.javelin_dmg > 0.0:                     # Evo E-Barbs: spear the target, then charge on
                u.javelin_left = max(0.0, u.javelin_left - dt)
                if u.javelin_left <= 0.0:
                    self._throw_javelin(u, ref)
                    u.javelin_left = u.spec.javelin_cd
            if u.spec.net_cd > 0.0 and u.deploy_left <= 0.0:
                # EVO HUNTER: "throws a net at the closest unit every 5 seconds, freezing the troop
                # in place and rendering it unable to move or attack for 3 seconds" -- a root: the
                # stun machinery is exactly that (still hittable), and it resets charges and ramps.
                u.net_left = max(0.0, u.net_left - dt)
                if u.net_left <= 0.0:
                    best, bg = None, u.spec.net_range
                    for e in self.units:
                        if e.team == u.team or e.hp <= 0 or not self._valid_foe(u, e):
                            continue
                        g = _gap(u.x, u.y, e)
                        if g <= bg:
                            best, bg = e, g
                    if best is not None:
                        best.stun_left = max(best.stun_left, u.spec.net_root_s)
                        best.aggro_reset = True
                        u.net_left = u.spec.net_cd
                        self.splash_events.append((best.x, best.y, 0.8, self.t))
                        del self.splash_events[:-40]
            rx, ry = (ref.x, ref.y)
            reach = u.spec.reach + u.reach_extra
            # LEAP (Bandit dash / Mega Knight jump), in TWO phases:
            #   WIND-UP  -- "he will STOP MOVING and begin charging"; stationary and COMMITTED. The
            #               balance log calls this the CHARGE, not the flight.
            #   TRAVEL   -- airborne at the leap row's own published Speed (Mega Knight 250 = 4.17
            #               tiles/s, Bandit 500 = 8.33), so a longer leap takes longer to land.
            # Splitting them matters: the wind-up is the window a defender gets, and the travel is
            # what closes a gap that walking never would.
            if u.leap_left > 0.0:
                # THE CHARGE CANNOT BE CANCELLED. Once he stops and starts winding up he is going to
                # leap; there is no body you can drop that makes him abort and walk in instead.
                #
                # What DOES keep moving is the AIM. `_acquire` re-picks every tick while he is
                # unlocked, so the leap lands on whatever is CLOSEST when the charge ENDS -- and the
                # band is not re-tested, so a body dropped INSIDE the minimum still gets jumped on.
                # Feeding a cheap body to a winding-up Mega Knight therefore does not save the unit
                # behind it by denying the jump; it only changes WHO the jump lands on.
                u.leap_left -= dt
                if u.leap_left <= 0.0:
                    u.leap_go = True
                    u.locked = True             # aim settled HERE -- the flight does not re-pick
                continue
            if u.leap_go:
                dxt, dyt = (ref.x - u.x) * _TILES_X, (ref.y - u.y) * _TILES_Y
                d = math.hypot(dxt, dyt)
                stop = max(0.0, d - (_body_radius(ref) + u.spec.radius))
                step = (u.spec.leap_speed or u.spec.speed) * dt
                if step >= stop or stop <= 1e-6 or d <= 1e-6:
                    u.leap_go = False
                    self._land_leap(u, ref)
                else:
                    u.x, u.y = _clamp_xy(u.x + (dxt / d) * step / _TILES_X,
                                         u.y + (dyt / d) * step / _TILES_Y, u.spec.radius)
                continue
            gap = _gap(u.x, u.y, ref)
            if u.spec.hook_max > 0.0 and gap > u.spec.reach and gap <= u.spec.hook_max:
                # Fisherman commits to the hook prep inside hook range instead of taking extra
                # walk steps first, so wind-up starts from a stable distance band.
                u.attacking = True
                u.locked = True
                u.focus_time += dt
                if u.cooldown <= 0.0 and u.hook_left <= 0.0:
                    self._hook_attack(u, kind, ref)
                    hook_cd = u.spec.hook_time if u.spec.hook_time > 0.0 else u.spec.hit_speed
                    u.cooldown = hook_cd / spd
                continue
            if self._hook_ok(u, ref, gap):
                u.attacking = True
                u.locked = True
                u.focus_time += dt
                if u.cooldown <= 0.0:
                    self._hook_attack(u, kind, ref)
                    hook_cd = u.spec.hook_time if u.spec.hook_time > 0.0 else u.spec.hit_speed
                    u.cooldown = hook_cd / spd
                continue
            if self._leap_ok(u, ref):
                # "he will STOP MOVING and begin charging" -- the wind-up is why a Mega Knight
                # answered at 4 tiles still reaches you, and why baiting the dash out of a Bandit
                # with a cheap body works.
                u.leap_left = u.spec.leap_time
                continue
            # NO SLOP AGAINST A CROWN TOWER. The tolerance exists so a body closing the last
            # fraction of a tile on a MOVING target does not stall a tick short; a crown tower is
            # stationary and 3 tiles wide, so there is nothing to absorb. Granting it anyway handed
            # every attacker a free 0.6 tiles that the tower does not get back, and 0.6 is exactly
            # the margin that decides whether a card can chip a tower from outside its return fire.
            # MEASURED with the slop: Magic Archer (7.0 reach) opened fire at 7.55 while the tower
            # could only answer out to 8.0 of its own -- he took ZERO damage and landed 25 hits.
            # Dart Goblin (6.5) sieged untouched too. Neither can do that in game.
            slop = 0.0 if isinstance(ref, Tower) else _REACH_SLOP
            if isinstance(ref, Tower) and not u.spec.flying:
                # TOUCHING IS IN RANGE (2026-08-15). `reach` is published attacker-CENTRE to
                # target-EDGE, but _separate_towers holds a ground body at exactly its own
                # radius from the tower's edge -- so a unit whose reach is SHORTER than its
                # body can never satisfy the test and parks against the tower forever.
                # MEASURED: Battle Ram (reach 0.50, radius 0.75) stalled at gap 0.75 and never
                # struck the crown tower at all -- it only broke into Barbarians when the tower
                # eventually killed it (user report). Giant Skeleton (0.80 vs 1.00) had the same
                # hole. It never mattered against building UNITS because those get _REACH_SLOP.
                # A body pressed against the tower is in contact; let it swing.
                reach = max(reach, u.spec.radius + 0.02)
            if gap <= reach + slop:
                u.attacking = True                          # engaged (in reach) -> Evo Knight's damage reduction is OFF
                u.locked = True                             # ...and committed: only an aggro reset breaks it now
                u.focus_time += dt                          # ...and the beam charges while it is actually firing
                if self.load_time_on and not u.loaded and u.spec.load_time > 0.0:
                    # WEAPON WIND-UP, paid once per engagement. A Musketeer that has just walked
                    # into range does not fire on the same tick she arrives; she takes her
                    # load_time first. Charged here rather than at deploy because it is the
                    # TARGET that starts the clock -- a unit that walks the lane unopposed and
                    # then meets a defender still pays it.
                    u.loaded = True
                    u.cooldown = max(u.cooldown, u.spec.load_time / spd)
                if u.cooldown <= 0:                          # one discrete hit, then wait hit_speed (slow -> longer)
                    self._attack(u, kind, ref)
                    u.charge_dist = 0.0                      # the charge is SPENT (and stopping cancels a run-up)
                    rm = 1.0
                    if u.spec.atk_ramp_per and u.spec.atk_ramp_mults:
                        # LITTLE PRINCE: cadence steps up every `atk_ramp_per` attacks landed
                        # from the same spot (1.2s -> 0.8s -> 0.4s); movement resets the count.
                        rm = u.spec.atk_ramp_mults[min(u.ramp_shots // u.spec.atk_ramp_per,
                                                       len(u.spec.atk_ramp_mults) - 1)]
                        u.ramp_shots += 1
                    u.cooldown = u.spec.hit_speed / spd / rm
                    if u.spec.ram_bounce:
                        # EVO BATTLE RAM'S SUPER CHARGE: it "charges and bounces multiple times
                        # against buildings and towers until its HP is depleted" -- the landing
                        # throws it back 4 tiles and the run-up starts again. Death (by damage)
                        # still breaks it into its riders via the normal spawner_death path.
                        fwd = 1.0 if u.team == 0 else -1.0
                        u.x, u.y = _clamp_xy(u.x, u.y + fwd * 4.0 / _TILES_Y, u.spec.radius)
                        u.charge_dist = 0.0
                        u.locked = False
                    elif u.spec.kamikaze:
                        u.hp = 0.0
            elif u.spec.sniper_shots > 0 and self._try_snipe(u):
                pass                                         # Evo Musketeer STANDS to take the shot
            elif u.spec.kind != "building":                  # buildings are stationary
                self._move_toward(u, rx, ry, dt, spd)
        # ROYAL GHOST'S STEALTH. "Upon deployment, he will spawn invisible, and will only turn
        # visible once he attacks... When he is not fighting any unit for 1.8 seconds, he will
        # become invisible again." `u.attacking` is already exactly "has a target in reach", so
        # FIGHTING is read straight off the combat loop rather than tracked separately -- which is
        # why he re-fades the moment the last body in front of him dies.
        for u in self.units:
            if u.spec.invis_time <= 0.0 or u.hp <= 0:
                continue
            if u.attacking and not u.spec.always_ghost:
                u.ghost, u.refade_left = False, u.spec.invis_time
            elif not u.ghost:
                u.refade_left -= dt
                if u.refade_left <= 0.0:
                    u.ghost = True
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
                if u.spec.elixir_death > 0.0:
                    # ...and, for the Elixir Golem line, the elixir too (capped like every other gain)
                    foe = 1 - u.team
                    self.elixir[foe] = min(10.0, self.elixir[foe] + u.spec.elixir_death)
                if u.spec.spawn_death_heal <= 0.0 and u.spec.base in _SKELETON_BASES:
                    # EVO WITCH'S HEALING BONES: "whenever a Skeleton or Guard dies, she heals
                    # 109 HP", overhealing to +30%. Any friendly bone counts, not only her own.
                    for w in self.units:
                        if (w.team == u.team and w.hp > 0 and w.spec.spawn_death_heal > 0.0):
                            w.hp = min(w.spec.hp * w.spec.overheal_frac,
                                       w.hp + w.spec.spawn_death_heal)
                if (u.spec.key == "skeleton_army_evo" and u.spec.kind == "troop"
                        and not u.from_egg and u.invis_left <= 0.0):
                    # EVO SKARMY: a skeleton dying while the shielded GENERAL lives becomes a
                    # GHOST -- "invisible and indestructible" but still swinging -- and every
                    # ghost vanishes the moment the General is destroyed.
                    gen = next((g for g in self.units
                                if g.team == u.team and g.hp > 0
                                and g.spec.base == "skarmy_general"), None)
                    if gen is not None:
                        nu = Unit(u.spec, u.team, u.x, u.y, 1.0)
                        nu.invis_left = 9999.0               # untargetable AND unhittable
                        nu.parent = gen
                        nu.from_egg = True                   # ghosts die quietly, no re-ghosting
                        self.units.append(nu)
                if u.spec.base == "skarmy_general":
                    for g in self.units:
                        if g.parent is u and g.invis_left > 9000.0:
                            g.hp = 0.0                       # the ghosts go down with their General
                self._spawn_cursed_hog(u)
                if not u.from_egg:                           # a REBORN phoenix dies quietly
                    self._death_blast(u)                     # Balloon / Giant Skeleton / Bomb Tower
                if u.spec.death_spawn_delay_s > 0.0 and u.spec.spawner_spec is not None:
                    self._late_spawns.append((self.t + u.spec.death_spawn_delay_s,
                                              u.spec.spawner_spec, u.team, u.x, u.y,
                                              int(u.spec.spawner_death)))   # barrel limbo
                else:
                    self._spawn_from(u, u.spec.spawner_death)  # death burst (Tombstone's 4, Drill's 2)
                if u.spec.mid_drop_frac > 0.0 and not u.mid_drop_done:
                    # EVO SKEL BARREL: "if this hitpoints trigger isn't activated before reaching a
                    # building, the 2 barrels will drop at once" -- second blast + second 7 skels.
                    self._death_blast(u)
                    self._spawn_from(u, u.spec.spawner_death)
                if u.spec.rage_r > 0.0:                      # Lumberjack: the bottle breaks where he fell
                    self.rage_zones.append((u.x, u.y, u.spec.rage_r, u.team,
                                            self.t + u.spec.rage_delay,
                                            self.t + u.spec.rage_delay + u.spec.rage_dur,
                                            u.spec.rage_boost))
                if u.spec.egg_hatch > 0.0 and not u.from_egg:   # Phoenix: drop the egg ONCE
                    egg = build_spec(self.db, "phoenix_egg", u.spec.level)
                    ne = Unit(egg, u.team, u.x, u.y, egg.hp)
                    ne.hatch_left = u.spec.egg_hatch
                    ne.hatch_frac = u.spec.egg_frac or 1.0
                    ne.hatch_spec = u.spec
                    self.units.append(ne)                    # appended mid-cull, same as _spawn_from
                continue
            alive.append(u)
        self.units = alive
        self._check_end()

    def _leap_ok(self, u: "Unit", ref) -> bool:
        """May `u` START a charge at `ref`?

        This gates BEGINNING a wind-up and nothing else. It is deliberately NOT re-checked while he
        charges: the wind-up is uncancellable, and what he lands on is simply whatever is closest
        when the charge ends -- inside the minimum range or not. The band only ever decides whether
        a leap is STARTED, never whether it is seen through.
        """
        if u.spec.leap_dmg <= 0.0 or u.spec.leap_max <= 0.0:
            return False
        if isinstance(ref, Tower):
            if not u.spec.leap_towers or not ref.alive:
                return False
        elif isinstance(ref, Unit):
            if ref.spec.flying or ref.hp <= 0:
                return False
        else:
            return False
        return u.spec.leap_min <= _gap(u.x, u.y, ref) <= u.spec.leap_max

    @staticmethod
    def _hook_ok(u: "Unit", ref, gap: float) -> bool:
        """Whether this unit may use a Fisherman-style hook pull right now."""
        s = u.spec
        if s.hook_max <= 0.0:
            return False
        if not (s.hook_min <= gap <= s.hook_max):
            return False
        if isinstance(ref, Tower):
            return ref.alive
        if isinstance(ref, Unit):
            return ref.hp > 0 and not ref.spec.flying
        return False

    def _hook_attack(self, u: "Unit", kind: str, ref) -> None:
        """Fisherman hook: start a timed pull phase, then deal the hit when it completes."""
        s = u.spec
        gap = _gap(u.x, u.y, ref)
        pull_dist = max(0.0, gap - s.reach)
        speed = max(0.1, s.hook_speed or 12.0)
        # Fixed WIND-UP, then distance-scaled travel: OUT to the target, RETURN while pulling.
        u.hook_windup_left = max(0.0, s.hook_time)
        u.hook_out_left = gap / speed
        u.hook_pull_left = pull_dist / speed
        u.hook_left = u.hook_windup_left + u.hook_out_left + u.hook_pull_left
        u.hook_ref = ref
        u.hook_kind = kind
        if kind == "tower" or (isinstance(ref, Unit) and ref.spec.kind == "building"):
            # Buildings/towers pull Fisherman IN over time.
            u.hook_mode = "self"
            return
        # Troops are yanked TOWARD Fisherman over time.
        u.hook_mode = "target"

    def _tick_hook(self, u: "Unit", dt: float) -> None:
        """Advance one active Fisherman hook-pull phase, landing damage at completion."""
        ref = u.hook_ref
        if ref is None or u.hook_mode not in ("self", "target"):
            u.hook_left = 0.0
            u.hook_mode = u.hook_kind = ""
            u.hook_ref = None
            return
        if isinstance(ref, Tower):
            if not ref.alive:
                u.hook_left = u.hook_windup_left = u.hook_out_left = u.hook_pull_left = 0.0
                u.hook_mode = u.hook_kind = ""
                u.hook_ref = None
                return
        elif isinstance(ref, Unit):
            if ref.hp <= 0:
                u.hook_left = u.hook_windup_left = u.hook_out_left = u.hook_pull_left = 0.0
                u.hook_mode = u.hook_kind = ""
                u.hook_ref = None
                return
        else:
            u.hook_left = u.hook_windup_left = u.hook_out_left = u.hook_pull_left = 0.0
            u.hook_mode = u.hook_kind = ""
            u.hook_ref = None
            return

        if u.hook_windup_left > 0.0:
            step = min(dt, u.hook_windup_left)
            u.hook_windup_left -= step
            u.hook_left = max(0.0, u.hook_left - step)
            return
        if u.hook_out_left > 0.0:
            step = min(dt, u.hook_out_left)
            u.hook_out_left -= step
            u.hook_left = max(0.0, u.hook_left - step)
            return

        mover, anchor = (u, ref) if u.hook_mode == "self" else (ref, u)
        dxt, dyt = (mover.x - anchor.x) * _TILES_X, (mover.y - anchor.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        goal = max(0.0, u.spec.reach + _body_radius(anchor) + _body_radius(mover))
        left_dist = max(0.0, d - goal)
        if left_dist > 1e-6 and d > 1e-6 and u.hook_pull_left > 0.0:
            # Return leg: cover the remaining pull distance across the remaining return time.
            step = left_dist if u.hook_pull_left <= dt else left_dist * (dt / u.hook_pull_left)
            mover.x, mover.y = _clamp_xy(mover.x - (dxt / d) * step / _TILES_X,
                                         mover.y - (dyt / d) * step / _TILES_Y,
                                         _body_radius(mover))
        step_t = min(dt, u.hook_pull_left)
        u.hook_pull_left = max(0.0, u.hook_pull_left - step_t)
        u.hook_left = max(0.0, u.hook_left - step_t)
        if u.hook_left > 1e-6:
            return

        # Ensure final contact is in-range, then land the actual hit.
        self._snap_to_reach(mover, anchor, u.spec.reach)
        if u.hook_mode == "target" and isinstance(ref, Unit):
            ref.aggro_reset = True
        mult = self._ramp_mult(u)
        dmg = u.spec.hit_dmg * u.dmg_mult * mult
        tower_dmg = u.spec.tower_hit_dmg * u.dmg_mult * mult
        if u.hook_kind == "tower":
            self._land_hit(u.team, "tower", ref, u.spec, dmg, tower_dmg, attacker=u)
        elif isinstance(ref, Unit) and ref.hp > 0:
            self._land_hit(u.team, "unit", ref, u.spec, dmg, tower_dmg, attacker=u)
        u.charge_dist = 0.0
        u.hook_windup_left = u.hook_out_left = u.hook_pull_left = 0.0
        u.hook_mode = u.hook_kind = ""
        u.hook_ref = None

    @staticmethod
    def _snap_to_reach(mover, anchor, reach: float) -> None:
        """Place `mover` so its edge-gap to `anchor` is at most `reach` tiles."""
        dxt, dyt = (mover.x - anchor.x) * _TILES_X, (mover.y - anchor.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        goal = max(0.0, reach + _body_radius(anchor) + _body_radius(mover))
        if d <= goal + 1e-6:
            return
        move = d - goal
        if d <= 1e-6:
            return
        mover.x, mover.y = _clamp_xy(mover.x - (dxt / d) * move / _TILES_X,
                                     mover.y - (dyt / d) * move / _TILES_Y, _body_radius(mover))

    def _land_leap(self, u: "Unit", ref) -> None:
        """A dash/jump arrives: close the gap, then deliver the published double-damage hit.

        Mega Knight's landing also knocks back (his `knockback` flag) and splashes, which is what
        makes jumping onto a support group so punishing; Bandit's is single-target.
        """
        s = u.spec
        dxt, dyt = (ref.x - u.x) * _TILES_X, (ref.y - u.y) * _TILES_Y
        d = math.hypot(dxt, dyt)
        if d > 1e-6:                                          # land at its target's EDGE, not on top
            stop = max(0.0, d - (_body_radius(ref) + s.radius))
            u.x, u.y = _clamp_xy(u.x + (dxt / d) * stop / _TILES_X,
                                 u.y + (dyt / d) * stop / _TILES_Y, s.radius)
        u.charge_dist = 0.0
        u.cooldown = s.hit_speed                              # the leap IS the attack -- then normal cadence
        dmg = s.leap_dmg * u.dmg_mult
        if isinstance(ref, Tower):
            self._damage_tower(ref, dmg, u.team)
        elif ref.hp > 0:
            self._hurt(ref, dmg)
            self._apply_status(u.team, s, ref)
            self._knock(ref, s, u.x, u.y)
        if s.leap_splash > 0.0 or s.splash:                   # Mega Knight lands ON a group
            # GATE FIXED 2026-08-14: this used to test only the generic `splash` flag, which is
            # FALSE for Mega Knight (his jump splash is its own leap_splash field) -- so the
            # landing splash had NEVER fired for the one card it was written for; every MK jump
            # was silently single-target. The leap's own radius is the authority here.
            # The slam splashes around the LANDING POINT for BOTH landing kinds (2026-08-14).
            # It used to run only for unit landings -- a tower-landing returned early, so a jump
            # onto a tower splashed nothing, and NO landing could touch a second tower. That
            # erased the real game's MK KING ACTIVATION (bait his jump beside a sleeping king;
            # the 2.2-tile slam wakes it) -- verified by test before this fix. Tower damage is
            # routed through _damage_tower so activation-on-damage fires like any other hit.
            rad = s.leap_splash or _SPLASH_R                  # the JUMP has its own, wider radius
            for e in self.units:
                if e.team != u.team and e is not ref and e.hp > 0 \
                        and _dist(e.x, e.y, ref.x, ref.y) <= rad:
                    self._hurt(e, dmg)
                    self._apply_status(u.team, s, e)
                    self._knock(e, s, u.x, u.y)
            for tw in self.towers[1 - u.team]:
                if tw.alive and tw is not ref \
                        and _dist(tw.x, tw.y, ref.x, ref.y) <= rad + _body_radius(tw):
                    self._damage_tower(tw, dmg, u.team)

    def _deploy_blast(self, u: "Unit") -> None:
        """Area damage the instant a body finishes appearing -- Mega Knight LANDING, Goblin Drill
        SURFACING. Both are published as `spawn_damage`, both knock back, and both are most of the
        reason the card is scary on arrival rather than merely after it starts walking."""
        s = u.spec
        if s.spawn_dmg <= 0.0 or s.spawn_radius <= 0.0:
            return
        for e in self.units:
            if e.team == u.team or e.hp <= 0:
                continue
            if _dist(u.x, u.y, e.x, e.y) <= s.spawn_radius + e.spec.radius:
                self._hurt(e, s.spawn_dmg)
                self._apply_status(u.team, s, e)             # E-Wiz spawn STUN / Ice Wizard nova SLOW
                self._knock(e, s, u.x, u.y)                  # radial, out of the landing circle
        if s.spawn_crown_dmg > 0.0:                          # Goblin Drill publishes a reduced crown value
            for tw in self._enemy_towers(u.team):
                if tw.alive and _gap(u.x, u.y, tw) <= s.spawn_radius:
                    self._damage_tower(tw, s.spawn_crown_dmg, u.team)

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
        # The blast may shove harder than -- or, for the Bomb Tower, INSTEAD of -- the card's shots.
        blast_knock = s.death_knockback or s.knockback
        if s.death_delay_s > 0.0:
            # FUSED BOMB (wiki): Balloon / Giant Skeleton / Bomb Tower "drop a bomb which
            # explodes after 3 seconds". Walking out of it is the counterplay, so the delay
            # is the mechanic. Resolved through the generic spell path, which also applies
            # the knockback these bombs carry.
            bomb = replace(s, spell_dmg=s.death_dmg, spell_radius=s.death_radius,
                           spell_tower_dmg=s.death_dmg * s.death_crown_mult,
                           pulls=False, rolls=False, zone_s=0.0, top_n_targets=0,
                           spawn_count=0, decoy_mirror=False, zap_pulses=0,
                           knockback=blast_knock, death_delay_s=0.0)
            self.spells.append(_Spell(u.team, u.x, u.y, bomb, s.death_delay_s))
            return
        for e in self.units:
            if e.team == u.team or e.hp <= 0:
                continue
            if s.ground_only and e.spec.flying:
                continue
            if _dist(u.x, u.y, e.x, e.y) <= s.death_radius + e.spec.radius:
                self._hurt(e, s.death_dmg)
                # DEATH BLASTS SHOVE TOO -- Golem, Giant Skeleton, Phoenix, Skeleton Barrel and
                # Goblin Demolisher all state it in their lead paragraph. Radial from the corpse.
                self._knock(e, replace(s, knockback=blast_knock), u.x, u.y)
        for tw in self._enemy_towers(u.team):
            if tw.alive and _gap(u.x, u.y, tw) <= s.death_radius:
                self._damage_tower(tw, s.death_dmg * s.death_crown_mult, u.team)

    def _tick_hatch(self, dt: float) -> None:
        """Phoenix EGG countdown. An egg that SURVIVES its 3.8 s hatches into a reborn phoenix at
        80% of the original's hitpoints and damage (7/2/2023 balance); the reborn drops no egg and
        deals no death damage. A killed egg just dies -- no bird. Hatching REMOVES the egg outside
        the death path, so it triggers none of the on-death machinery."""
        for u in list(self.units):
            if u.hatch_left <= 0.0 or u.hp <= 0:
                continue
            u.hatch_left -= dt
            if u.hatch_left > 0.0:
                continue
            self.units.remove(u)
            sp = u.hatch_spec
            if sp is None:
                continue
            nb = Unit(sp, u.team, u.x, u.y, sp.hp * u.hatch_frac)
            nb.dmg_mult = u.hatch_frac
            nb.from_egg = True
            nb.deploy_left = sp.deploy_time
            nb.pulse_cd = sp.pulse_interval
            self.units.append(nb)

    def _rage_mult(self, u: "Unit") -> float:
        """1 + boost when the unit is raged -- by a friendly Rage zone OR its own Evo-Barbarian
        self-rage. Rage does not stack ("does not stack with another Rage spell, the Lumberjack's
        dropped Rage, or the Rage effect of the Evolved Barbarians"): the strongest source wins."""
        best = u.spec.hit_rage_boost if u.rage_self_left > 0.0 else 0.0
        for (zx, zy, zr, zt, t0, t1, boost) in self.rage_zones:
            if zt == u.team and t0 <= self.t < t1 \
                    and _dist(u.x, u.y, zx, zy) <= zr + u.spec.radius:
                best = max(best, boost)
        return 1.0 + best

    def _try_snipe(self, u: "Unit") -> bool:
        """EVO MUSKETEER's Sniper Ammo: 3 infinite-range rounds, spent ONLY when nothing is in her
        normal reach, at the closest enemy unit IN FRONT of her (troops and building-units; "she
        cannot snipe Crown Towers"), each dealing sniper_mult x her hit (1.8). Returns True if a
        round was fired this tick -- she stands still to take the shot."""
        if u.sniper_left <= 0 or u.cooldown > 0.0:
            return False
        fwd = -1.0 if u.team == 0 else 1.0                   # team 0 attacks toward y = 0
        best, best_gap = None, float("inf")
        for e in self.units:
            if e.team == u.team or e.hp <= 0 or not self._valid_foe(u, e):
                continue
            if (e.y - u.y) * fwd < 0.0:                      # behind her: not a sniper target
                continue
            g = _gap(u.x, u.y, e)
            if g < best_gap:
                best, best_gap = e, g
        if best is None:
            return False
        self._launch(f"{u.spec.base}_snipe", u.team, u.x, u.y, best, u.spec,
                     u.spec.hit_dmg * u.dmg_mult * u.spec.sniper_mult, 0.0)
        u.sniper_left -= 1
        u.cooldown = u.spec.hit_speed
        return True

    def _throw_javelin(self, u: "Unit", ref) -> None:
        """EVO ELITE BARBARIANS: "each ... throws a Rage-tipped javelin at an enemy troop or Crown
        Tower, then charges as normal" -- a spear every javelin_cd seconds that also lays a RAGE
        TRAIL along its flight, buffing any friendly that walks it (the announcement's "any of
        your troops that steps into them will be enhanced")."""
        jspec = replace(u.spec, proj_speed=10.0, proj_radius=0.0,   # the SPEAR flies; the barb is
                        splash=False, multi_kind="", multi_hits=1)  # melee, so his spec has no shot
        self._launch(f"{u.spec.base}_javelin", u.team, u.x, u.y, ref, jspec,
                     u.spec.javelin_dmg * u.dmg_mult, u.spec.javelin_dmg * u.dmg_mult)
        for f in (0.3, 0.6, 0.9):                            # trail segments toward the target
            zx = u.x + (ref.x - u.x) * f
            zy = u.y + (ref.y - u.y) * f
            self.rage_zones.append((zx, zy, 1.2, u.team, self.t, self.t + 3.0, 0.30))

    def _shield_burst(self, u: "Unit") -> None:
        """EVO WIZARD: "when the Fire Shield is destroyed, it triggers an explosion" -- area
        damage in shield_burst_r around him, shoving enemies shield_burst_knock tiles (normal
        knockback immunity rules; air is a valid victim, he is a wizard)."""
        ks = replace(u.spec, knockback=u.spec.shield_burst_knock)
        for e in self.units:
            if e.team == u.team or e.hp <= 0:
                continue
            if _dist(u.x, u.y, e.x, e.y) <= u.spec.shield_burst_r + e.spec.radius:
                self._hurt(e, u.spec.shield_burst_dmg)
                if self._can_knock(e, ks):
                    self._knock(e, ks, u.x, u.y)
        self.splash_events.append((u.x, u.y, u.spec.shield_burst_r, self.t))
        del self.splash_events[:-40]

    def _air_drop(self, u: "Unit") -> None:
        """EVO ROYAL HOGS: "deploy as flying troops ... upon attacking or getting hurt, the hogs
        will fall to the ground, dealing low area damage on impact." The spec swap is the
        transition -- ground-targeters can touch them from here on."""
        u.spec = replace(u.spec, flying=False, air_drop=False)
        if u.spec.air_drop_dmg > 0.0:
            for e in self.units:
                if e.team != u.team and e.hp > 0 and not e.spec.flying \
                        and _dist(u.x, u.y, e.x, e.y) <= 1.5 + e.spec.radius:
                    self._hurt(e, u.spec.air_drop_dmg)
            self.splash_events.append((u.x, u.y, 1.5, self.t))
            del self.splash_events[:-40]

    def _recoil_blast(self, u: "Unit") -> None:
        """EVO ROYAL GIANT: "every time [he] attacks, it deals damage in a 2.5 tile radius around
        it and knocks back enemy ground troops by 1 tile" -- a defensive blast around HIMSELF on
        each shot. Air is immune to both the damage and the shove; heavies shrug the shove off
        via the normal knockback-immunity list. This is what makes swarm-on-top a losing answer."""
        ks = replace(u.spec, knockback=1.0)                  # the shove exists ONLY in this blast --
        for e in self.units:                                 # his cannonball itself never pushes
            if e.team == u.team or e.hp <= 0 or e.spec.flying:
                continue
            if _dist(u.x, u.y, e.x, e.y) <= u.spec.recoil_r + e.spec.radius:
                self._hurt(e, u.spec.recoil_dmg)
                if self._can_knock(e, ks):
                    self._knock(e, ks, u.x, u.y)
        self.splash_events.append((u.x, u.y, u.spec.recoil_r, self.t))
        del self.splash_events[:-40]

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
            nu.ghost = sp.invis_time > 0.0               # LJ ghost / Souldiers spawn faded
            nu.refade_left = sp.invis_time
            if sp.ghost_life_s > 0.0:
                nu.hatch_left = sp.ghost_life_s          # timed silent removal (no death effects)
            self.units.append(nu)

    def _spawn_cursed_hog(self, u: "Unit") -> None:
        """Mother Witch curse: a cursed enemy TROOP turns into a hog for the curser's team on death."""
        if u.curse_left <= 0.0 or u.cursed_by not in (0, 1) or u.spec.kind != "troop":
            return
        if u.spec.base == "mother_witch_hog":
            return
        try:
            sp = build_spec(self.db, "mother_witch_hog", max(1, int(u.curse_level)))
        except Exception:
            return
        nu = Unit(spec=sp, team=u.cursed_by, x=u.x, y=u.y, hp=sp.hp)
        nu.deploy_left = min(sp.deploy_time, 0.2)
        self.units.append(nu)

    def _hurt(self, u: "Unit", dmg: float, hits_hidden: bool = False) -> None:
        """Apply damage to a UNIT. Two defensive mechanics can reduce it first:
        - DAMAGE REDUCTION while NOT attacking (Evo Knight -- 60% less from ALL sources whenever it isn't
          engaged; it drops the moment it deals a hit, tracked by `u.attacking`). NOT a numerical HP pool.
        - a SHIELD pool (Royal Recruits / Guards ...) that absorbs the WHOLE hit; like real Clash Royale the
          OVERFLOW that breaks the shield is DISCARDED, not carried to hp (a big hit only STRIPS the shield).
        A unit with neither behaves exactly as `u.hp -= dmg`."""
        # DASH INVULNERABILITY: "She is immune to damage during her dash." This is most of what makes
        # the Bandit worth 3 elixir -- she trades through a Crown Tower volley, and chipping her out
        # of the wind-up is not an option the defender has.
        # "She is immune to damage during her dash" -- the WHOLE dash, charge and flight alike.
        if (u.leap_left > 0.0 or u.leap_go) and u.spec.leap_invuln:
            return
        if u.invis_left > 0.0:               # invisible = untouchable, not merely unseen
            return
        # RETRACTED TESLA: "immune to all damage except for the Earthquake". The exception is a
        # PROPERTY OF THE SPELL, not of the Tesla -- Earthquake was given this specifically
        # (3/3/2020, "allowed the Earthquake to affect the Tesla even if it is hidden"), so it is
        # carried on the spell's own `hits_hidden` flag rather than special-cased by card name.
        if u.hidden and not hits_hidden:
            return
        if u.spec.first_hit_immune_s > 0.0 and u.iframes_left > 0.0:
            return                                           # Evo Minion Horde: mid-immunity window
        if u.spec.air_drop and u.spec.flying:
            self._air_drop(u)                                # Evo Royal Hogs FALL when first hurt
        if u.spec.damage_reduction > 0.0 and not u.attacking:
            dmg *= (1.0 - u.spec.damage_reduction)           # Evo Knight: 60% less while moving/approaching
        if u.shield_left > 0.0:
            u.shield_left = max(0.0, u.shield_left - dmg)
            if u.shield_left <= 0.0 and u.spec.shield_burst_dmg > 0.0:
                self._shield_burst(u)                        # Evo Wizard's Fire Shield EXPLODES
            if u.spec.first_hit_immune_s > 0.0 and not u.iframes_used:
                u.iframes_used = True
                u.iframes_left = u.spec.first_hit_immune_s
            return
        u.hp -= dmg
        if u.spec.first_hit_immune_s > 0.0 and not u.iframes_used and u.hp > 0:
            # EVO MINION HORDE'S HORDE IMMUNITY: "the first strike against each member makes it
            # briefly invincible" -- it TAKES that first hit, then cannot be hurt for 3 seconds.
            u.iframes_used = True
            u.iframes_left = u.spec.first_hit_immune_s

    def _attack(self, u: Unit, kind: str, ref) -> None:
        if u.spec.min_range > 0.0 and _gap(u.x, u.y, ref) < u.spec.min_range:
            # SIEGE DEAD ZONE: the target slipped under the barrel -- drop the lock so the
            # next acquisition picks something it CAN shell (or idles, exactly like the game).
            u.locked = False
            u.target = None
            return
        # T1 EVO on-swing effects: fire once per ATTACK (the swing), independent of what it lands on
        if u.spec.recoil_dmg > 0.0:                          # Evo Royal Giant's recoil blast
            self._recoil_blast(u)
        if u.spec.attack_nado_s > 0.0:                       # Evo Valkyrie's whirlwind
            nspec = replace(u.spec, pull_radius=u.spec.attack_nado_r,
                            pull_duration=u.spec.attack_nado_s, spell_dmg=u.spec.attack_nado_dmg)
            self.vortices.append(_Vortex(u.team, u.x, u.y, nspec, u.spec.attack_nado_s))
        if u.spec.hit_rage_s > 0.0:                          # Evo Barbarians rage themselves
            u.rage_self_left = u.spec.hit_rage_s
        if u.spec.hit_heal > 0.0:                            # Evo Bats drink on every swing
            u.hp = min(u.spec.hp * u.spec.overheal_frac, u.hp + u.spec.hit_heal)
        if u.spec.air_drop and u.spec.flying:                # Evo Royal Hogs fall when they attack
            self._air_drop(u)
        if u.spec.spawn_on_hit and u.spec.spawn_on_hit_cap > 0:
            # EVO SKELETONS: "every time they attack, an additional Evolved Skeleton will spawn,
            # for a maximum total of 8" -- the cap counts LIVING bodies of the same evo on this team.
            alive = sum(1 for e in self.units
                        if e.team == u.team and e.hp > 0 and e.spec.key == u.spec.key)
            if alive < u.spec.spawn_on_hit_cap:
                sp = u.spec if u.spec.spawn_on_hit == u.spec.key \
                    else build_spec(self.db, u.spec.spawn_on_hit, u.spec.level)
                fwd = -1.0 if u.team == 0 else 1.0
                nx, ny = _clamp_xy(u.x, u.y - fwd * (2.0 * u.spec.radius + 0.1) / _TILES_Y, sp.radius)
                nu = Unit(sp, u.team, nx, ny, sp.hp)
                nu.deploy_left = 0.2                         # pops out mid-fight, near-instant
                self.units.append(nu)
        mult = self._ramp_mult(u)
        dmg = u.spec.hit_dmg * u.dmg_mult * mult             # one discrete hit (DPS x hit_speed; x Royal Chef buff)
        tower_dmg = u.spec.tower_hit_dmg * u.dmg_mult * mult
        if u.spec.power_mult > 0.0 and _gap(u.x, u.y, ref) >= u.spec.power_min:
            dmg *= u.spec.power_mult                         # Evo Archers' POWER SHOT: 4+ tiles out -> 1.5x
            tower_dmg *= u.spec.power_mult
        # CHARGE: a completed run-up REPLACES this hit's damage (Prince 783 vs a ~200 base hit). It
        # is a flat published value, not a multiplier, so it overrides rather than scales -- and it
        # applies to towers too, which is what makes an unblocked Prince so punishing.
        charged_splash = 0.0
        if u.spec.charge_dmg > 0.0 and u.spec.charge_range > 0.0 \
                and u.charge_dist >= u.spec.charge_range \
                and not (u.spec.charge_after_shield and u.shield_left > 0.0):
            # EVO RECRUITS: "AFTER their shield is destroyed, they gain the ability to charge"
            dmg = u.spec.charge_dmg * u.dmg_mult
            tower_dmg = dmg
            charged_splash = u.spec.charge_splash_r          # Dark Prince's charged swing blasts wider
        if u.spec.proj_speed > 0.0:                          # the shot has to TRAVEL -- it lands later
            if u.spec.multi_kind == "shotgun" and u.spec.multi_hits > 1:
                self._shotgun(u, ref, dmg)
                return
            fspec = u.spec
            if u.spec.volley_slow_every > 0 and u.hit_no % u.spec.volley_slow_every == 0:
                # EVO PRINCESS: this volley SLOWS (7 s) in a widened blast; the next two are normal
                fspec = replace(u.spec, slows=True, slow_dur=u.spec.volley_slow_s, proj_radius=3.0)
            if u.spec.poison_dps > 0.0:
                # EVO DART GOBLIN: "poison becomes stronger the longer [he] remains alive" --
                # wiki vardefines publish THREE stage dps values (51/115/307); the stage
                # thresholds are not published, curated at 15 s steps [verify].
                dps = u.spec.poison_dps
                if u.spec.poison_stages:
                    dps = u.spec.poison_stages[min(len(u.spec.poison_stages) - 1, int(u.age // 15.0))]
                fspec = replace(fspec, poison_dps=dps)
            self._launch(f"{u.spec.base}_projectile", u.team, u.x, u.y, ref, fspec, dmg, tower_dmg)
            self._recoil(u, ref)
            return
        # SPLIT (Electro Wizard): "If 2 or more targets are within his range, his attack will SPLIT
        # and attack the closest 2 units." His published damage is the TOTAL for the attack, not per
        # bolt -- 115 / 1.8 s hit speed == his published dps of 64, so counting it once per target
        # was dealing DOUBLE. One target takes the whole hit; two share it. A CROWN TOWER is a valid
        # half ("the Electro Wizard could split the strike onto the Tower and deal unnecessary chip
        # damage"), which is why you keep the defending troop a tile clear of your own tower.
        # NB this is NOT the Electro Dragon's `chain`, which "arcs and strikes up to 2 OTHER targets"
        # -- there each body takes the full hit, and that model stays as it is.
        if u.spec.multi_kind == "split" and u.spec.multi_hits > 1:
            reach = u.spec.reach + u.reach_extra + _REACH_SLOP
            extra = [(_gap(u.x, u.y, e), e, "unit") for e in self.units
                     if e.team != u.team and e.hp > 0 and e is not ref
                     and self._valid_foe(u, e) and _gap(u.x, u.y, e) <= reach]
            # AT MOST ONE CROWN TOWER among the halves. Towers cluster: MEASURED, 100 of the 18x32
            # cells have two or more enemy towers inside a 5-tile reach (the whole area behind the
            # bridge, and all three towers dead centre), so counting each tower separately made an
            # Electro Wizard whose ONLY target is a crown tower deal half damage to it -- the other
            # bolt quietly went into the King, which also woke him up. He splits between a troop and
            # a tower, never between two towers.
            if not any(k == "tower" for _, _, k in extra) and not isinstance(ref, Tower):
                towers = [(_gap(u.x, u.y, tw), tw, "tower") for tw in self._enemy_towers(u.team)
                          if tw is not ref and _gap(u.x, u.y, tw) <= reach]
                if towers:
                    extra.append(min(towers, key=lambda t: t[0]))
            extra.sort(key=lambda t: t[0])
            picks = [(ref, kind)] + [(e, k) for _, e, k in extra[:u.spec.multi_hits - 1]]
            share = 1.0 / len(picks)
            for tgt, k in picks:
                self._land_hit(u.team, k, tgt, u.spec, dmg * share, tower_dmg * share, attacker=u)
            return
        self._land_hit(u.team, kind, ref, u.spec, dmg, tower_dmg, attacker=u,
                       splash_r=charged_splash)
        if (u.spec.uppercut_tiles > 0.0 and isinstance(ref, Unit) and ref.hp > 0
                and ref.spec.kind != "building"):
            # EVO MEGA KNIGHT'S MEGA UPPERCUT: "launching the targeted troop back 4 tiles towards
            # the nearest enemy Crown Tower ... isn't dependent on troop weight" -- the defender is
            # punched back toward ITS OWN side, re-entering his jump band, so he bullies it home.
            tws = [t for t in self.towers[ref.team] if t.alive]
            if tws:
                tw = min(tws, key=lambda t: _dist(ref.x, ref.y, t.x, t.y))
                dxt, dyt = (tw.x - ref.x) * _TILES_X, (tw.y - ref.y) * _TILES_Y
                d = math.hypot(dxt, dyt)
                if d > 1e-6:
                    ref.x, ref.y = _clamp_xy(
                        ref.x + (dxt / d) * u.spec.uppercut_tiles / _TILES_X,
                        ref.y + (dyt / d) * u.spec.uppercut_tiles / _TILES_Y, ref.spec.radius)
                    ref.aggro_reset = True
        if (u.spec.smash_knock > 0.0 and isinstance(ref, Unit) and ref.hp > 0
                and _gap(u.x, u.y, ref) <= u.spec.smash_range):
            # EVO EXECUTIONER'S AXE SMASH: close targets are also shoved 2 tiles (the shove's
            # aggro_reset is what "can reset Ram Rider and Prince's charge attacks").
            self._knock(ref, replace(u.spec, knockback=u.spec.smash_knock, knockback_all=False),
                        u.x, u.y)
        # MONK'S 3-STRIKE COMBO: "the first 2 attacks deal normal damage, while the 3rd strike deals
        # extra damage and knockback, EVEN IF THE TARGETED TROOP IS NORMALLY IMMUNE TO KNOCKBACK"
        # (hence knockback_all on the card). Only the shove is modelled -- the wiki does not publish
        # the 3rd hit's damage, and inventing a multiplier would be worse than leaving it flat.
        u.hit_no += 1
        if u.spec.combo_every > 0 and u.hit_no % u.spec.combo_every == 0 and isinstance(ref, Unit):
            self._knock(ref, u.spec, u.x, u.y)
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
        mult = float(st[idx]) / float(st[0])
        if u.spec.ramp4_s > 0.0 and u.focus_time >= u.spec.ramp4_s:
            mult *= u.spec.ramp4_mult                        # Evo Inferno D's 4th stage: 2x stage 3
        return mult

    def _land_hit(self, team: int, kind: str, ref, spec: CardSpec, dmg: float,
                  tower_dmg: float, attacker: "Unit | None" = None,
                  splash_r: float = 0.0) -> None:
        """Deal one hit that has ARRIVED (either instantly, or as a projectile reaching its target).
        ``attacker`` (the swinging unit, when melee/direct) enables the Zap-Pack reflect: damaging a
        reflect card from inside its radius zaps the attacker back."""
        if kind == "tower":
            # crown towers take the REDUCED per-hit value when the card has one (Miner) -- real CR's
            # crown-tower damage reduction; most troops have no reduced value so this equals hit_dmg
            self._damage_tower(ref, tower_dmg, team)
            self._apply_status(team, spec, ref)
            return
        if (attacker is not None and getattr(ref, "spec", None) is not None
                and ref.spec.parry_cd_s > 0.0 and ref.hp > 0 and ref.stun_left <= 0.0
                and self.t >= ref.parry_ready_t and attacker.spec.reach <= 2.0):
            # RONIN PARRY (wiki): "can block the attack of opposing melee troops and deal
            # double the damage to them every 3.5 seconds". The blocked swing lands NOTHING;
            # the counter is 2x Ronin's own hit. Ranged/spell damage is not parryable.
            ref.parry_ready_t = self.t + ref.spec.parry_cd_s
            self._hurt(attacker, 2.0 * ref.spec.hit_dmg * ref.dmg_mult)
            return
        self._hurt(ref, dmg)
        self._apply_status(team, spec, ref)
        if spec.kind != "tower" and getattr(ref, "spec", None) is not None:
            ref.last_unit_hit_t = self.t          # combat stamp: a UNIT (not a tower) hit it
        if (attacker is not None and attacker.hp > 0 and attacker.spec.kill_heal > 0.0
                and getattr(ref, "spec", None) is not None and ref.hp <= 0):
            # EVO PEKKA: "each kill heals the same amount ... always 12.5% of the core HP" (the
            # post-rework flat butterfly, 470 at level 11), overhealing up to 150% of deploy hp.
            attacker.hp = min(attacker.spec.hp * attacker.spec.overheal_frac,
                              attacker.hp + attacker.spec.kill_heal)
        if (attacker is not None and getattr(ref, "spec", None) is not None
                and ref.spec.reflect_dmg > 0.0 and attacker.hp > 0
                and ref.stun_left <= 0.0                       # the Zap Pack is off while frozen/stunned
                and _dist(attacker.x, attacker.y, ref.x, ref.y) <= ref.spec.reflect_r):
            self._hurt(attacker, ref.spec.reflect_dmg)
            if ref.spec.reflect_stun > 0.0:
                attacker.stun_left = max(attacker.stun_left, ref.spec.reflect_stun)
        if spec.splash:
            rad = splash_r or spec.splash_r or _SPLASH_R      # charged override, per-card, flat fallback
            self.splash_events.append((ref.x, ref.y, rad, self.t))
            del self.splash_events[:-40]
            for e in self.units:
                if e.team != team and e is not ref and _dist(e.x, e.y, ref.x, ref.y) <= rad:
                    self._hurt(e, dmg)
                    self._apply_status(team, spec, e)
                    if spec.kind != "tower":
                        e.last_unit_hit_t = self.t
            for tw in self._enemy_towers(team):
                if tw is not ref and _dist(tw.x, tw.y, ref.x, ref.y) <= rad:
                    self._damage_tower(tw, tower_dmg, team)
                    self._apply_status(team, spec, tw)

    def _launch(self, label: str, team: int, x: float, y: float, ref, spec: CardSpec,
                dmg: float, tower_dmg: float) -> None:
        radius = spec.proj_radius
        rng = spec.proj_range or (spec.reach + _REACH_SLOP)
        pierce = spec.proj_pierce and spec.multi_kind not in ("spark", "shotgun")
        dx, dy = 0.0, 0.0
        if pierce:
            # A piercing shot is fired ALONG A HEADING and keeps that heading for the whole leg.
            # Re-aiming at `tx,ty` each tick made it turn round the moment it passed the target, so
            # it hovered there instead of flying on -- which is most of the Executioner's reach
            # (7.5-tile throw vs his own 4.5-tile range) and all of Magic Archer's.
            d = _dist(x, y, ref.x, ref.y)
            if d > 1e-9:
                dx, dy = (ref.x - x) / d, (ref.y - y) / d
        self.projectiles.append(Projectile(
            label=label, team=team, x=x, y=y, tx=ref.x, ty=ref.y, target=ref, spec=spec,
            dmg=dmg, tower_dmg=tower_dmg, radius=radius, speed=spec.proj_speed,
            left=max(rng, _dist(x, y, ref.x, ref.y)),
            ground_only=not spec.attacks_air,
            # SPARK and SHOTGUN shots must not pierce: a piercing shot is deleted at max range and
            # never reaches _impact, so their extra hits would never fire. Both burst ON the target.
            pierce=pierce, width=spec.proj_width, dirx=dx, diry=dy, ox=x, oy=y,
            bounces_left=spec.bounce_n,
            spark_end_dmg=spec.spark_dps_big * 0.25))   # Evo FC: ONE large zone on the impact point

    def _shotgun(self, u: Unit, ref, dmg: float) -> None:
        """Fire the WHOLE shotgun: `multi_hits` separate pellets scattered across a cone.

        "The Hunter launches an attack that shoots 10 SHOTGUN PELLETS that travel in RANDOM
        directions with a wide spread, giving him higher damage the closer he is to the target and
        lower damage at long range." The falloff is not a rule -- it is what a diverging cone does
        to a target of fixed size, so it is left to EMERGE rather than be computed. That also buys
        three published behaviours for free:
          * "each bullet is an individual hit", so a SHIELD eats one pellet and the rest dig in;
          * pellets that miss keep flying to the projectile range (6.5) well past his own reach (4),
            and hit whatever else is in the cone;
          * against a Graveyard "the spawning order of his bullets is also random, possibly making
            him miss more of his bullet shots" -- inconsistency by construction.
        A pellet stops in the first body it touches: it scatters, it does not pierce.

        The cone half-angle is the ONE number here the wiki does not publish (its only mention is
        "slightly decreased his bullet spread", 24/1/2018, with no value). It is curated in
        cards.yaml, chosen so that point-blank ALL ten connect -- which is what the published DPS of
        84 x 10 / 2.2 assumes -- and so the count at his maximum range matches what the old
        hardcoded falloff produced, so this fixes the mechanic without quietly rebalancing the card.
        """
        s = u.spec
        d = _dist(u.x, u.y, ref.x, ref.y)
        if d <= 1e-9:
            return
        base = math.atan2((ref.y - u.y) * _TILES_Y, (ref.x - u.x) * _TILES_X)
        half = math.radians(s.spread)
        rng = s.proj_range or (s.reach + _REACH_SLOP)
        for i in range(s.multi_hits):
            ang = base + self.rng.uniform(-half, half)
            self.projectiles.append(Projectile(
                label=f"{s.base}_pellet", team=u.team, x=u.x, y=u.y,
                tx=u.x + math.cos(ang) * rng / _TILES_X,
                ty=u.y + math.sin(ang) * rng / _TILES_Y,
                target=None, spec=s, dmg=dmg, tower_dmg=dmg, radius=0.0, speed=s.proj_speed,
                left=rng, ground_only=not s.attacks_air, pierce=True, width=_PELLET_R,
                dirx=math.cos(ang) / _TILES_X, diry=math.sin(ang) / _TILES_Y,
                stop_on_hit=True, ox=u.x, oy=u.y))

    def _pierce_pass(self, p: Projectile) -> None:
        """One tick of a piercing shot's damage: everything it is currently overlapping, once each.

        Crown towers are hit too. They were not before, and the omission was total rather than
        partial: a piercing shot is removed at max range and never reaches ``_impact``, which is the
        only place towers were ever checked -- so an Executioner, Bowler or Magic Archer left alone
        against a tower did literally nothing to it. The wiki assumes the opposite ("Left alone, the
        Executioner will deal the same damage to all tower troops, throwing his axe 3 times against
        all of them").
        """
        reach = p.width or max(p.radius, 0.5)
        for e in self.units:
            if e.team == p.team or e.hp <= 0 or id(e) in p.hit or e.hidden:
                continue
            if p.ground_only and e.spec.flying:
                continue
            if _dist(p.x, p.y, e.x, e.y) <= reach + e.spec.radius:
                p.hit.add(id(e))
                self._hurt(e, p.dmg)
                self._apply_status(p.team, p.spec, e)
                # A PIERCING SHOT SHOVES ALONG ITS OWN LINE. The Bowler's boulder "inflicts
                # knockback, while piercing through enemies" -- separating a tank from the
                # support behind it is the card's entire job, and it was landing damage with
                # no push at all because knockback only ever ran on the SPELL paths.
                self._knock(e, p.spec, p.x, p.y, p.dirx * _TILES_X, p.diry * _TILES_Y)
                if p.stop_on_hit:
                    p.left = 0.0          # a PELLET buries itself in the first body it reaches
                    return
        for tw in self._enemy_towers(p.team):
            if id(tw) in p.hit:
                continue
            # A pellet is tiny and clips the tower's crown/turret body, not the full 3x3 base used
            # for melee stand-off and pathing. Keeping the full footprint here made Hunter land
            # 8-9 pellets on a tower at range where live behavior is closer to 3-4.
            tower_r = _PELLET_TOWER_R if p.stop_on_hit else tw.radius
            if _dist(p.x, p.y, tw.x, tw.y) <= reach + tower_r:
                p.hit.add(id(tw))
                self._damage_tower(tw, p.tower_dmg, p.team)
                self._apply_status(p.team, p.spec, tw)
                if p.stop_on_hit:
                    p.left = 0.0
                    return

    def _tick_projectiles(self, dt: float) -> None:
        for p in list(self.projectiles):
            if p.target is not None and not p.pierce and p.radius <= 0.0:
                alive = (p.target.hp > 0) if isinstance(p.target, Unit) else p.target.alive
                if not alive:
                    self.projectiles.remove(p)      # single-target shot whose target died mid-flight fizzles
                    continue
                p.tx, p.ty = p.target.x, p.target.y  # tracking shot follows it
            step = p.speed * dt
            if p.pierce:
                p.x += p.dirx * step                 # straight on along the launch heading
                p.y += p.diry * step
                p.x, p.y = _clamp_xy(p.x, p.y, 0.0)
                p.left -= step
                self._pierce_pass(p)
                if p.left <= 0.0:
                    # BOOMERANG: the axe does not stop at max range, it turns around and hits
                    # everything again on the way back -- "striking all enemies on the way out AND
                    # back", which is HALF this card's published damage (168 x2 per throw).
                    # Clearing `hit` is what lets it re-damage the same bodies. It flies back to
                    # where it was THROWN, not to the thrower: "if he is defeated while his axe is
                    # not in his hand, the axe will still fly back to where he was defeated".
                    if (p.spec.multi_kind == "boomerang" and not p.returning
                            and p.spec.multi_hits >= 2):
                        back = _dist(p.x, p.y, p.ox, p.oy)
                        p.returning = True
                        p.label = f"{p.spec.base}_axe_return"
                        p.target = None
                        p.tx, p.ty = p.ox, p.oy
                        p.dirx = (p.ox - p.x) / back if back > 1e-9 else 0.0
                        p.diry = (p.oy - p.y) / back if back > 1e-9 else 0.0
                        p.left = back
                        p.hit.clear()
                        continue
                    self._drop_spark_zone(p)   # Evo FC shrapnel: one SMALL zone at the end of its run
                    self.projectiles.remove(p)
                continue
            dxt, dyt = (p.tx - p.x) * _TILES_X, (p.ty - p.y) * _TILES_Y
            d = math.hypot(dxt, dyt)
            if d > 1e-9:
                move = min(step, d)
                p.x += (dxt / d) * move / _TILES_X
                p.y += (dyt / d) * move / _TILES_Y
            p.left -= step
            if d <= step or p.left <= 0.0:            # ARRIVED
                self._drop_spark_zone(p)   # Evo FC carrier: one LARGE zone on the impact point
                self._impact(p)
                self.projectiles.remove(p)

    def _drop_spark_zone(self, p: Projectile) -> None:
        """EVO FIRECRACKER: leave this shot's lingering spark zone where its flight ENDED.

        The card's damage-over-time is deliberately only in two places -- one large circle on the
        primary projectile's impact point, and one small circle at the very end of each of the five
        shrapnel bolts' flight. Dropping them along the flight path instead (the old model, every
        1.25 tiles) painted most of a lane with DoT and made her a zoning card she is not.
        """
        if p.spark_end_dmg <= 0.0:
            return
        self.spark_zones.append([p.x, p.y, p.spec.spark_r or 0.75, p.team,
                                 self.t + p.spec.spark_dur, p.spark_end_dmg, self.t])
        del self.spark_zones[:-60]

    def _impact(self, p: Projectile) -> None:
        spark = p.spec.multi_kind == "spark" and p.label.endswith("_projectile")
        if spark:
            # The rocket is only the CARRIER. Firecracker's published damage is PER SHRAPNEL --
            # "each shard deals 64, totaling 320 if all shards hit the same target" -- so the
            # burst is the entire payload and the rocket itself hurts nothing. The original
            # target still takes up to all 5 bolts: they spawn on its centre and pierce out
            # through its hitbox.
            self._spark_burst(p)
            return
        if p.radius > 0.0:                            # AREA shot: explodes where it landed, hit or miss
            chain = p.bounces_left > 0 or bool(p.hit)  # a BOUNCE chain damages each enemy once per attack
            for e in self.units:
                if e.team == p.team or e.hp <= 0:
                    continue
                if p.ground_only and e.spec.flying:
                    continue
                if _dist(p.x, p.y, e.x, e.y) <= p.radius + e.spec.radius:
                    if chain:
                        if id(e) in p.hit:
                            continue
                        p.hit.add(id(e))
                    self._hurt(e, p.dmg)
                    self._apply_status(p.team, p.spec, e)
                    self._knock(e, p.spec, p.x, p.y)      # area shot: radial from where it landed
            for tw in self._enemy_towers(p.team):
                if _gap(p.x, p.y, tw) <= p.radius:
                    if chain:
                        if id(tw) in p.hit:
                            continue
                        p.hit.add(id(tw))
                    self._damage_tower(tw, p.tower_dmg, p.team)
                    self._apply_status(p.team, p.spec, tw)
            if p.bounces_left > 0:
                # EVO BOMBER: the bomb BOUNCES on past the blast, 2.5 tiles along its flight
                # heading, and explodes again with the same damage and area -- twice. From the
                # bridge that is what lets it reach the crown tower. The continuation shares this
                # projectile's `hit` set (once-per-attack rule, 16/12/2024).
                hx, hy = (p.x - p.ox) * _TILES_X, (p.y - p.oy) * _TILES_Y
                d = math.hypot(hx, hy)
                if d < 1e-9:
                    hx, hy = 0.0, (1.0 if p.team == 1 else -1.0)
                else:
                    hx, hy = hx / d, hy / d
                step = p.spec.bounce_tiles or 2.5
                nx, ny = _clamp_xy(p.x + hx * step / _TILES_X, p.y + hy * step / _TILES_Y, 0.0)
                nb = Projectile(
                    label=f"{p.spec.base}_bounce", team=p.team, x=p.x, y=p.y, tx=nx, ty=ny,
                    target=None, spec=p.spec, dmg=p.dmg, tower_dmg=p.tower_dmg, radius=p.radius,
                    speed=p.speed, left=step * 1.5, ground_only=p.ground_only,
                    ox=p.x, oy=p.y, bounces_left=p.bounces_left - 1)
                nb.hit = p.hit
                self.projectiles.append(nb)
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
            # The bolt hops BODY-TO-BODY, each hop picking the nearest new enemy in chain range
            # from the CURRENT node. This enforces unique targets (Electro Spirit's cap is 9) and
            # reproduces the published "up to N" behaviour instead of spraying from only the first
            # target.
            if not isinstance(ref, Unit):
                return
            seen = {id(ref)}
            cur = ref
            for _ in range(n - 1):
                near = [e for e in self.units
                        if e.team != team and e.hp > 0 and id(e) not in seen
                        and _dist(cur.x, cur.y, e.x, e.y) <= _CHAIN_TILES
                        and not (not s.attacks_air and e.spec.flying)]
                if not near:
                    break
                e = min(near, key=lambda x: _dist(cur.x, cur.y, x.x, x.y))
                self._hurt(e, dmg)
                self._apply_status(team, s, e)
                self.projectiles.append(Projectile(
                    label=f"{s.base}_chain", team=team, x=cur.x, y=cur.y, tx=e.x, ty=e.y,
                    target=e, spec=s, dmg=0.0, tower_dmg=0.0, radius=0.0,
                    speed=max(s.proj_speed, 20.0), left=_dist(cur.x, cur.y, e.x, e.y),
                    ground_only=not s.attacks_air))
                seen.add(id(e))
                cur = e
        elif s.multi_kind == "shotgun":
            return          # fired as real pellets in _shotgun, not as extra hits on one target

    def _spark_burst(self, p: Projectile) -> None:
        """Firecracker: the rocket hits its target, THEN splits into shrapnel.

        Wiki + guide mechanics ("once it hits its target, splits into 5 ADDITIONAL shrapnel,
        which continue to travel, while piercing through enemies"; spread "between the leftmost
        and rightmost small projectiles is 70 degrees ... between any two adjacent small
        projectiles is 17.5 degrees"):
          * the bolts spray FORWARD from the landing point in a 70-degree cone centred on the
            rocket's flight heading -- not a radial ring;
          * each bolt PIERCES, damaging everything along its corridor (published projectile
            radius 0.4 tiles) -- her damage stat is PER BOLT, the carrier deals nothing;
          * total projectile range is 11 tiles from the FIRING position ("she can even damage
            the Princess towers when at the bridge, not unlike a Magic Archer"), so the bolts
            fly whatever is LEFT of that budget past the impact point.
        The old model sprayed 5 bolts in a full circle with no heading vector, and a piercing
        projectile moves along dirx/diry -- unset, so they sat motionless on the impact point.
        """
        s = p.spec
        n = s.multi_hits
        if s.multi_kind != "spark" or n < 2:
            return
        flown = _dist(p.ox, p.oy, p.x, p.y)
        left = max(1.0, (s.proj_range or (flown + _SPARK_TILES)) - flown)
        hx, hy = (p.x - p.ox) * _TILES_X, (p.y - p.oy) * _TILES_Y
        d = math.hypot(hx, hy)
        if d < 1e-9:                                   # point-blank burst: spray toward the enemy side
            hx, hy = 0.0, (1.0 if p.team == 1 else -1.0)
        else:
            hx, hy = hx / d, hy / d
        base = math.atan2(hy, hx)
        for i in range(n):
            ang = base + math.radians(-35.0 + 70.0 * i / (n - 1))
            cx, cy = math.cos(ang), math.sin(ang)
            self.projectiles.append(Projectile(
                label=f"{s.base}_spark", team=p.team, x=p.x, y=p.y,
                tx=p.x + cx * left / _TILES_X, ty=p.y + cy * left / _TILES_Y, target=None,
                spec=s, dmg=p.dmg, tower_dmg=p.tower_dmg, radius=0.0,
                speed=max(s.proj_speed, 8.0), left=left,
                ground_only=not s.attacks_air, pierce=True,
                width=s.proj_radius or 0.4,
                dirx=cx / _TILES_X, diry=cy / _TILES_Y, ox=p.x, oy=p.y,
                spark_end_dmg=s.spark_dps_small * 0.25))  # ONE small zone at the END of each bolt

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

    def _recoil(self, u: Unit, ref) -> None:
        """The shooter shoves ITSELF backwards on firing -- Firecracker's 1 tile.

        Wiki, Firecracker: "After attacking, she will recoil backwards 1 tile." (7/7/2020 dropped it
        from 1.5 to 1.) It cuts both ways, and both directions matter to how she is played: it walks
        her out of reach of the melee troop she is shooting -- and out of a spell aimed where she was
        standing -- but "her repeated recoil may cause her to switch to the other lane", which is
        the reason she is placed BEHIND the engagement rather than beside it.

        Straight away from the target, since that is what "backwards" means for a unit that always
        faces what it shoots. Not routed through _knock: nothing hit her, so knockback immunity and
        the charge/ramp resets a real shove carries must not apply -- a recoiling Sparky keeps her
        charge, and a knockback-immune recoiler would otherwise stop recoiling entirely.
        """
        r = u.spec.recoil
        if r <= 0.0 or ref is None:
            return
        dx, dy = (u.x - ref.x) * _TILES_X, (u.y - ref.y) * _TILES_Y
        d = math.hypot(dx, dy)
        if d <= 1e-6:                       # standing on top of it: recoil toward our own side
            dx, dy, d = 0.0, (1.0 if u.team == 0 else -1.0), 1.0
        u.x, u.y = _clamp_xy(u.x + (dx / d) * r / _TILES_X,
                             u.y + (dy / d) * r / _TILES_Y, u.spec.radius)

    def _knock(self, e: Unit, spec: CardSpec, fx: float, fy: float,
               dx: float = 0.0, dy: float = 0.0) -> None:
        """Push `e` back. `dx, dy` is an optional TRAVEL direction in tiles -- a rolling boulder shoves
        everything it passes along its own line, so a Bowler splits a push apart lengthwise. With no
        direction it falls back to RADIAL, away from the impact point (Fireball / Giant Snowball /
        Rocket, and every death blast).
        The shove also RESETS the attack animation ("troops vulnerable to knockback will have their
        attack animations reset"), which is why a Snowball answers a charge or an Inferno's ramp --
        modelled here by the same aggro_reset the Log already set."""
        if not self._can_knock(e, spec):
            return
        d = math.hypot(dx, dy)
        if d <= 1e-9:                                    # no travel direction -> radial from impact
            dx, dy = (e.x - fx) * _TILES_X, (e.y - fy) * _TILES_Y
            d = math.hypot(dx, dy)
            if d <= 1e-6:                                # dead centre: no radial direction exists
                dx, dy, d = 0.0, 1.0, 1.0                # deterministic fallback
        e.x, e.y = _clamp_xy(e.x + (dx / d) * spec.knockback / _TILES_X,
                             e.y + (dy / d) * spec.knockback / _TILES_Y, e.spec.radius)
        e.aggro_reset = True
        e.ramp_shots = 0                                 # displacement resets the Little Prince ramp too
        e.charge_dist = 0.0                              # ...and DISARMS a charge (2026-08-15): a Log/
                                                         # Snowball hit drops a Prince/Ram back to walking
                                                         # pace; the run-up tiles must be earned again

    def _apply_status(self, team: int, spec: CardSpec, e) -> None:
        if spec.poison_dps > 0.0 and isinstance(e, Unit):
            # EVO DART GOBLIN: the dart leaves poison ticking on the victim (dps already grown
            # by the goblin's age at fire time -- see _attack's fspec).
            e.poison_left = max(e.poison_left, spec.poison_s)
            e.poison_take = spec.poison_dps
        """Apply a hitter's/spell's crowd-control to a struck unit or crown tower.

        Durations and slow strength are PER CARD where the wiki publishes them, falling back to the
        global config value. That difference is not cosmetic: a Freeze holds for 4s and an Ice Spirit
        for 1.1s, and a Ram Rider's snare (-70%) is more than twice a Giant Snowball's (-30%).
        """
        if isinstance(e, Unit):
            # A retracted Tesla is "vulnerable to Earthquake and Freeze" and nothing else -- so a Zap or
            # an Electro Wizard cannot stun it while it is under, but a Freeze still locks it down.
            if e.hidden and not spec.freezes and not spec.hits_hidden:
                return
        if spec.freezes:
            e.stun_left = max(getattr(e, "stun_left", 0.0), spec.freeze_dur or self.freeze_dur)
            if isinstance(e, Unit):
                e.aggro_reset = True          # RESET CARDS: a stun/freeze breaks the target lock -- that is the
                e.charge_dist = 0.0           # ...and disarms a charge, same as knockback
            elif hasattr(e, "aggro_reset"):
                e.aggro_reset = True
        elif spec.stuns:                  # whole point of an Ice/Electro Spirit or a Zap on a locked attacker
            e.stun_left = max(getattr(e, "stun_left", 0.0), spec.stun_dur or self.stun_dur)
            if isinstance(e, Unit):
                e.aggro_reset = True
                e.charge_dist = 0.0           # a Zap under a charging Prince resets the run-up too
            elif hasattr(e, "aggro_reset"):
                e.aggro_reset = True
        if spec.slows:
            if spec.base == "fisherman" and getattr(e, "fisherman_slowed", False):
                return
            if spec.base == "fisherman":
                setattr(e, "fisherman_slowed", True)
            e.slow_left = max(getattr(e, "slow_left", 0.0), spec.slow_dur or self.slow_dur)
            e.slow_mult = spec.slow_mult or self.slow_factor
        if spec.curse_dur > 0.0 and isinstance(e, Unit) and e.spec.kind == "troop":
            e.curse_left = max(e.curse_left, spec.curse_dur)
            e.cursed_by = team
            e.curse_level = spec.level

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
        if tw.stun_left > 0.0:
            tw.stun_left = max(0.0, tw.stun_left - dt)
            return
        if tw.slow_left > 0.0:
            tw.slow_left = max(0.0, tw.slow_left - dt)
        eff_dt = dt * (tw.slow_mult if tw.slow_left > 0.0 else 1.0)
        rng = self.king_range if tw.king else self.tower_range
        foes = [e for e in self.units if e.team != team and e.hp > 0 and e.deploy_left <= 0.0
                and e.invis_left <= 0.0 and not e.hidden and not e.ghost
                and _gap(tw.x, tw.y, e) <= rng]
        if tw.aggro_reset:
            tw.aggro_reset = False
            tw.acquired = False
            tw.target = None
        if not foes:
            tw.acquired = False
            tw.target = None
            tw.engaged = False                                   # weapon lowered -> the NEXT engage pays the wind-up
            if tw.ammo_max > 0.0:                                # reload the dagger clip while there's no target
                tw.ammo = min(tw.ammo_max, tw.ammo + dt / tw.ammo_regen_s)
            return
        locked = tw.target if tw.acquired else None
        valid_locked = (locked in foes)
        if not valid_locked:
            tw.target = None
            tw.acquired = False
        if not tw.acquired:
            tw.target = min(foes, key=lambda e: _gap(tw.x, tw.y, e))
            tw.acquired = True
            # LOAD TIME on ENGAGING -- not on every retarget. Keeping it for the first target is
            # what reproduces the reference interaction: an L11 Bomber walking into an L11 princess
            # tower lands EXACTLY ONE bomb before dying. Firing the instant a target appears kills
            # it ~0.8 s sooner and the bomb never lands, so the opening delay is load-bearing.
            #
            # But it was being charged again EVERY time the lock broke, and a lock breaks when the
            # target DIES. Against a swarm the princess one-shots -- Bats or Skeletons at the
            # bridge -- the tower paid the 0.8 s wind-up before every single body, so five Bats cost
            # it ~4 s of firing instead of ~0.8 s plus four normal shots, and the tower read as far
            # slower than the real one (user-reported 2026-08-16). In the game the wind-up is the
            # weapon coming up: once it is up it stays up while there is anything to shoot, and the
            # cadence between kills is the ordinary hit speed. `engaged` is that "weapon already up"
            # state, cleared only by an idle tick with no foes in range at all.
            if not tw.engaged:
                tw.reload_left = tw.first_hit
        tw.engaged = True
        tw.reload_left -= eff_dt
        if tw.reload_left > 0.0:
            return
        tgt = tw.target
        if tgt is None:
            return
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
        if s.spec.zone_s > 0.0:
            # LINGERING ZONE (Poison / Void / Graveyard): nothing lands at cast -- the field
            # does the work over its lifetime in _tick_zones.
            self.zones.append(_Zone(s.team, s.x, s.y, s.spec, s.spec.zone_s))
            return
        if s.spec.top_n_targets > 0:
            # LIGHTNING / VINES: hit only the N HIGHEST-HP targets in the radius (towers
            # rank by hp among them) -- a swarm under the bolt is untouched, which is the
            # entire counterplay economics of these spells.
            rad = s.r_override or s.spec.spell_radius
            pool = [(e.hp, "unit", e) for e in self.units
                    if e.team != s.team and e.hp > 0 and not e.hidden
                    and _dist(e.x, e.y, s.x, s.y) <= rad]
            pool += [(tw.hp, "tower", tw) for tw in self._enemy_towers(s.team)
                     if _dist(tw.x, tw.y, s.x, s.y) <= rad]
            for _hp, k, ref in sorted(pool, key=lambda p: -p[0])[:s.spec.top_n_targets]:
                if k == "unit":
                    self._hurt(ref, s.spec.spell_dmg, s.spec.hits_hidden)
                    self._apply_status(s.team, s.spec, ref)
                    self._knock(ref, s.spec, s.x, s.y)
                else:
                    self._damage_tower(ref, s.spec.spell_tower_dmg, s.team)
                    self._apply_status(s.team, s.spec, ref)
            return
        rad = s.r_override or s.spec.spell_radius
        for e in self.units:
            if s.spec.ground_only and e.spec.flying:
                continue                                     # a ground bomb can't reach flyers
            if e.team != s.team and _dist(e.x, e.y, s.x, s.y) <= rad:
                self._hurt(e, s.spec.spell_dmg, s.spec.hits_hidden)
                self._apply_status(s.team, s.spec, e)                 # Zap/Freeze stun; slow spells
                self._knock(e, s.spec, s.x, s.y)              # Fireball / Giant Snowball / Rocket pushback
        for tw in self._enemy_towers(s.team):
            if _dist(tw.x, tw.y, s.x, s.y) <= rad:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)
                self._apply_status(s.team, s.spec, tw)
        if s.echoes > 0:
            # EVO ZAP: "the ring grows and zaps every target inside 2 more times" -- pulses ~1 s
            # apart at radii 2.5 -> 3.0 -> 3.5, each a full zap (damage + stun + crown chip).
            self.spells.append(_Spell(s.team, s.x, s.y, s.spec, 1.0,
                                      r_override=rad + (s.spec.zap_step or 0.5),
                                      echoes=s.echoes - 1))
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
                pull = step * _pull_resist(e.spec)
                if pull >= d:
                    e.x, e.y = v.x, v.y                       # reached the centre (clumped)
                else:
                    e.x += (dxt / d) * pull / _TILES_X        # tiles -> normalised, per axis
                    e.y += (dyt / d) * pull / _TILES_Y
                # BEING DRAGGED OFF WHAT YOU WERE HITTING BREAKS THE LOCK. This is the mechanic that
                # makes KING ACTIVATION work: tornado a wincon off a princess tower and, once that
                # tower is out of its reach, it re-picks -- taking the king if the king is now the
                # nearest building. Without this a Hog hauled onto the king tower simply walked back
                # to the princess it was still committed to, and the whole pull-to-activate play
                # (and the defensive pull generally) did not exist. Same rule `_separate` already
                # applies when a body is SHOVED out of reach; the vortex was the path that missed it.
                if e.locked and e.target is not None \
                        and _gap(e.x, e.y, e.target) > e.spec.reach + e.reach_extra:
                    e.aggro_reset = True

    def _resolve_barrage(self, team: int, cx: float, cy: float, spec: CardSpec) -> None:
        """Evo Cannon's nine rings land: 5 in a row ~2.5 tiles ahead, 4 flanking the mount
        [verify layout]. Damage radius 2.5 per ring, each victim hit ONCE, shoved 1 tile from
        the nearest ring centre; crown towers take volley_crown once."""
        fwd = -1.0 if team == 0 else 1.0
        rings = [(cx + ox / _TILES_X, cy + fwd * 2.5 / _TILES_Y)
                 for ox in (-4.4, -2.2, 0.0, 2.2, 4.4)]
        rings += [(cx + ox / _TILES_X, cy + fwd * 0.5 / _TILES_Y)
                  for ox in (-3.3, -1.1, 1.1, 3.3)]
        R = 2.5
        kspec = replace(spec, knockback=1.0, knockback_all=False)
        for e in self.units:
            if e.team == team or e.hp <= 0 or e.spec.flying or e.hidden:
                continue
            hits = [rg for rg in rings if _dist(e.x, e.y, rg[0], rg[1]) <= R + e.spec.radius]
            if not hits:
                continue
            near = min(hits, key=lambda rg: _dist(e.x, e.y, rg[0], rg[1]))
            self._hurt(e, spec.volley_dmg)
            self._knock(e, kspec, near[0], near[1])
        for tw in self._enemy_towers(team):
            if tw.alive and any(_gap(rg[0], rg[1], tw) <= R for rg in rings):
                self._damage_tower(tw, spec.volley_crown or spec.volley_dmg, team)

    @staticmethod
    def _ground_pos_ok(x: float, y: float, r_tiles: float) -> bool:
        """Can a GROUND body legally stand here? Inside the side edges, and never in the
        water unless on a bridge deck -- vetoes ally-dodge points at the bridge choke."""
        if not (r_tiles / _TILES_X <= x <= 1.0 - r_tiles / _TILES_X):
            return False
        if abs(y - _RIVER) * _TILES_Y < 1.0 + r_tiles:
            return any(abs(x - bx) * _TILES_X <= _BRIDGE_HALF for bx in _BRIDGES)
        return True

    def _steer_around_allies(self, u: Unit, tx: float, ty: float):
        """A walker paths AROUND a STOPPED ally (attacking / locked / still deploying)
        instead of shoving it -- the user-reported bug was a melee unit bulldozing its own
        firing ranged support into the enemy. Marching same-direction pushes are untouched
        (that is a real mechanic; see _separate). The dodge point must be legal ground, so
        nobody sidesteps into the river at a bridge choke."""
        if u.spec.flying:
            return tx, ty
        ux, uy = (tx - u.x) * _TILES_X, (ty - u.y) * _TILES_Y
        d = math.hypot(ux, uy)
        if d <= 1e-6:
            return tx, ty
        ux, uy = ux / d, uy / d
        best = None
        for a in self.units:
            if (a is u or a.team != u.team or a.hp <= 0 or a.spec.flying
                    or not (a.attacking or a.locked or a.deploy_left > 0.0)):
                continue
            axt, ayt = (a.x - u.x) * _TILES_X, (a.y - u.y) * _TILES_Y
            along = axt * ux + ayt * uy                      # tiles ahead along the path
            if along <= 0.0 or along > 2.5:
                continue
            lat = -axt * uy + ayt * ux                       # signed lateral offset
            block = u.spec.radius + a.spec.radius + 0.1
            if abs(lat) >= block:
                continue
            if best is None or along < best[0]:
                best = (along, a, lat, block)
        if best is None:
            return tx, ty
        _along, a, lat, block = best
        side = 1.0 if lat > 0.0 else -1.0                    # round the shoulder it already leans to
        px, py = -uy * side, ux * side                       # lateral unit vector toward the ally
        m = block + 0.15
        nx_, ny_ = a.x - px * m / _TILES_X, a.y - py * m / _TILES_Y
        if not u.spec.river_jump and not self._ground_pos_ok(nx_, ny_, u.spec.radius):
            return tx, ty                                    # no legal dodge: stay put behind it
        return nx_, ny_

    def _tick_zones(self, dt: float) -> None:
        for z in self.zones:
            z.left -= dt
            z.age += dt
            sp = z.spec
            # timed SPAWNS (Graveyard): one Skeleton per gap on the radius edge, wiki-exact
            # ("a single Skeleton ... every 0.5 seconds ... on the edge of the spell's
            # radius", first at 2.2 s, 12 total).
            if sp.zone_spawn_n > 0 and sp.spawn_spec is not None:
                while (z.spawned < sp.zone_spawn_n
                       and z.age >= sp.zone_spawn_start_s + z.spawned * sp.zone_spawn_gap_s):
                    ang = self.rng.uniform(0.0, 6.283185)
                    rr = sp.spell_radius if sp.zone_spawn_edge else sp.spell_radius * self.rng.random()
                    ss = sp.spawn_spec
                    sx, sy = _clamp_xy(z.x + math.cos(ang) * rr / _TILES_X,
                                       z.y + math.sin(ang) * rr / _TILES_Y, ss.radius)
                    nu = Unit(ss, z.team, sx, sy, ss.hp)
                    nu.deploy_left = ss.deploy_time
                    self.units.append(nu)
                    z.spawned += 1
            if sp.zone_tick_s <= 0.0:
                continue
            z.tick_in -= dt
            if z.tick_in > 0.0:
                continue
            z.tick_in += sp.zone_tick_s
            foes = [e for e in self.units if e.team != z.team and e.hp > 0
                    and not e.hidden and _dist(e.x, e.y, z.x, z.y) <= sp.spell_radius]
            tws = [tw for tw in self._enemy_towers(z.team)
                   if _dist(tw.x, tw.y, z.x, z.y) <= sp.spell_radius]
            dmg, crown = sp.spell_dmg, sp.spell_tower_dmg
            if sp.zone_tiers:
                # VOID: "dealing more damage to them the fewer there are inside its radius"
                # -- count-tiered per-tick damage (1 / 2-3 / 4+ targets, wiki vardefines).
                n = len(foes) + len(tws)
                dmg, crown = sp.zone_tiers[-1][1], sp.zone_tiers[-1][2]
                for cap, d_, c_ in sp.zone_tiers:
                    if n <= cap:
                        dmg, crown = d_, c_
                        break
            for e in foes:
                self._hurt(e, dmg)
                if sp.zone_move_slow > 0.0 and (e.slow_left <= 0.0
                                                or e.slow_mult > 1.0 - sp.zone_move_slow):
                    # POISON: "decreases the movement speed of enemy troops by 15%" -- never
                    # overriding a STRONGER slow already on the unit (Ice Wizard's 35%).
                    e.slow_mult = 1.0 - sp.zone_move_slow
                    e.slow_left = max(e.slow_left, sp.zone_tick_s + 0.1)
            for tw in tws:
                self._damage_tower(tw, crown, z.team)
        self.zones = [z for z in self.zones if z.left > 0.0]

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
                    e.charge_dist = 0.0                        # ...and DISARMS a charge (2026-08-15): a
                                                               # logged Prince/Ram drops to walking pace and
                                                               # must re-earn the run-up tiles
        if s.spec.carry_roll:
            # EVO SNOWBALL'S SNOW BOWLING: "the affected troops get pulled into it and [it] rolls
            # for 4.5 tiles ... when it finishes its roll, the troops are freed" -- every ground
            # body the corridor touched is swept to the corridor's END and slowed 4 s. (While
            # carried they are untargetable in game; at our tick size the sweep is instant, so
            # the untargetable window is folded into the displacement.)
            endy = s.y + fdir * s.spec.roll_len / _TILES_Y
            k = 0
            for e in self.units:
                if e.team == s.team or e.spec.flying or e.hp <= 0 or e.spec.kind == "building":
                    continue
                dy = (e.y - s.y) * fdir * _TILES_Y
                if -_LOG_BACK_SLOP <= dy <= s.spec.roll_len and abs(e.x - s.x) * _TILES_X <= halfw:
                    e.x, e.y = _clamp_xy(s.x + ((k % 3) - 1) * 0.6 / _TILES_X,
                                         endy + (k // 3) * 0.5 / _TILES_Y, e.spec.radius)
                    e.slow_left = max(e.slow_left, s.spec.slow_dur or self.slow_dur)
                    e.slow_mult = s.spec.slow_mult or self.slow_factor
                    e.aggro_reset = True
                    e.charge_dist = 0.0                        # being bowled certainly resets a run-up
                    k += 1
        for tw in self._enemy_towers(s.team):
            dy = (tw.y - s.y) * fdir * _TILES_Y
            if -_LOG_BACK_SLOP <= dy <= s.spec.roll_len and abs(tw.x - s.x) * _TILES_X <= halfw:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)
                self._apply_status(s.team, s.spec, tw)

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
