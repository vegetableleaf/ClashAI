"""Headless Clash-Royale-ish match engine (no vision, no rendering by itself).

Medium-fidelity, STAT-DRIVEN from the card knowledge base (clashrl.cards.CardDB): elixir economy,
lane movement with bridge crossing, target acquisition with an AGGRO/SIGHT range + target commitment
(building-only + siege rules), a ~1s DEPLOY delay, DISCRETE hit-speed combat with splash, slow/stun/
freeze crowd-control, soft-collision body-blocking, princess/king towers (the king wakes on ANY
damage), and area/rolling spells. It is deliberately NOT a faithful CR clone -- exact pathfinding,
champions, evolutions, and card-specific quirks (charge / ramp-up) are still out of scope. The point
is enough fidelity that a policy trained here transfers as a PRIOR to the real game (then fine-tuned
live). See icebow/DECK_SWITCH.md (Stage: simulator) and log.txt.

Coordinates are NORMALISED [0,1] to match the rest of the pipeline: enemy side is the TOP (y<0.5),
your side the BOTTOM (y>0.5), the river at y=0.5, bridges at x in {0.25, 0.75}. team 0 = you
(bottom/blue), team 1 = opponent (top/red).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

# speed word -> normalized units/second (CR tiles/min over a ~32-tile-tall arena)
_SPEED = {"slow": 0.023, "medium": 0.031, "fast": 0.047, "very_fast": 0.063, None: 0.031}
# attack reach word -> normalized distance (melee ~0.3 tile, short ~2.5, long ~5.5)
_REACH = {"melee": 0.03, "short": 0.09, "long": 0.16, None: 0.03}
_RIVER = 0.5
_BRIDGES = (0.25, 0.75)
_SPLASH_R = 0.06
# The Log (rolling spell): a forward CORRIDOR from the cast point -- ground-only, with knockback.
_LOG_ROLL_LEN = 0.30      # how far forward it rolls (normalized)
_LOG_ROLL_HALFW = 0.07    # corridor half-width (~a lane)
_LOG_KNOCKBACK = 0.05     # pushes ground troops this far in the roll direction


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
    roll_len: float = 0.0     # forward length of the roll corridor (normalized)
    hit_speed: float = 1.0    # seconds between attacks (discrete hits)
    hit_dmg: float = 0.0      # damage per hit (= dps * hit_speed; preserves average DPS)
    deploy_time: float = 1.0  # seconds before a freshly-placed unit can act (spells = 0)
    radius: float = 0.02      # collision radius (soft body-block)
    slows: bool = False       # applies a SLOW on hit (Ice Wizard)
    stuns: bool = False       # applies a brief STUN (Zap / Tesla-evo pulse / Electro)
    freezes: bool = False     # applies a FREEZE -- a longer stun (Ice Spirit / Freeze)
    level: int = 11           # card level (HP + damage scaled by 1.1^(level-11))
    pulse_dmg: float = 0.0    # Evo Tesla area-shock: damage per pulse
    pulse_r: float = 0.0      # pulse radius (normalized)
    pulse_stun: float = 0.0   # STUN seconds applied by each pulse
    pulse_interval: float = 0.0  # seconds between pulses (0 = no pulse)


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
    reach = _REACH.get(db.attack_range(base), 0.03)
    speed = _SPEED.get(c.get("speed"), 0.031)
    count = int(c.get("count") or 1)
    building_only = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    siege = "siege" in flags
    spell_radius = 0.11 if base == "royal_delivery" else 0.09
    spell_delay = 3.0 if base == "royal_delivery" else 0.4
    rolls = kind == "spell" and "knockback" in flags          # The Log: a rolling forward corridor
    ground_only = kind == "spell" and c.get("attacks") == ["ground"]
    if rolls:
        spell_radius = _LOG_ROLL_HALFW                        # corridor HALF-WIDTH for a rolling spell
    lifetime = 40.0 if kind == "building" else None
    p_dmg = p_r = p_stun = p_int = 0.0
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
        p_r = float(evo.get("pulse_radius", 0.0)) * (_REACH["long"] / 5.5)   # tiles -> normalized
        p_stun = float(evo.get("pulse_stun", 0.0))
        p_int = float(evo.get("pulse_interval", 0.0))
    sc = 1.1 ** (int(level) - 11)                             # CR level scaling: HP + damage only
    hp *= sc; dmg *= sc; dps *= sc; tower_dmg *= sc; p_dmg *= sc
    deploy_time = 0.0 if kind == "spell" else 1.0             # troops/buildings take ~1s to appear; spells use spell_delay
    hit_dmg = dps * hit                                        # DPS delivered as one discrete hit every `hit` seconds
    radius = 0.03 if "tank" in flags else (0.014 if count >= 3 else 0.02)
    return CardSpec(
        key=key, base=base, kind=kind, elixir=elixir, hp=hp, dps=dps, reach=reach, speed=speed,
        count=count, flying=db.is_flying(base), attacks_air=db.attacks_air(base),
        splash=db.has_splash(base), building_only=building_only, siege=siege,
        kamikaze="kamikaze" in flags, lifetime=lifetime,
        spell_radius=spell_radius, spell_dmg=dmg,
        spell_tower_dmg=tower_dmg, spell_delay=spell_delay,
        rolls=rolls, ground_only=ground_only,
        knockback=(_LOG_KNOCKBACK if rolls else 0.0), roll_len=(_LOG_ROLL_LEN if rolls else 0.0),
        hit_speed=hit, hit_dmg=hit_dmg, deploy_time=deploy_time, radius=radius,
        slows=("slow" in flags), stuns=("stun" in flags), freezes=("freeze" in flags),
        level=int(level), pulse_dmg=p_dmg, pulse_r=p_r, pulse_stun=p_stun, pulse_interval=p_int)


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


@dataclass
class Tower:
    x: float
    y: float
    hp: float
    max_hp: float
    king: bool = False
    active: bool = True
    alive: bool = True


@dataclass
class _Spell:
    team: int
    x: float
    y: float
    spec: CardSpec
    t: float                      # time remaining until it lands


def _dist(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


class SimEngine:
    """One match. Advance with :meth:`advance(dt)`; deploy with :meth:`deploy`."""

    def __init__(self, cfg, db, rng):
        self.cfg = cfg
        self.db = db
        self.rng = rng
        self.princess_hp = float(cfg.get("sim", "princess_hp", default=2600.0))
        self.king_hp = float(cfg.get("sim", "king_hp", default=4800.0))
        self.tower_dps = float(cfg.get("sim", "tower_dps", default=90.0))
        self.tower_range = float(cfg.get("sim", "tower_range", default=0.20))
        self.king_range = float(cfg.get("sim", "king_range", default=0.20))
        self.regulation = float(cfg.get("sim", "regulation_s", default=180.0))
        self.overtime = float(cfg.get("sim", "overtime_s", default=60.0))
        self.siege_sight = float(cfg.get("sim", "siege_sight", default=0.42))  # X-Bow ~11.5 tiles
        self.sight_range = float(cfg.get("sim", "sight_range", default=0.12))  # troop aggro radius (notice enemy UNITS)
        self.slow_factor = float(cfg.get("sim", "slow_factor", default=0.5))   # SLOW -> this x move + attack speed
        self.slow_dur = float(cfg.get("sim", "slow_duration", default=2.0))
        self.stun_dur = float(cfg.get("sim", "stun_duration", default=0.5))
        self.freeze_dur = float(cfg.get("sim", "freeze_duration", default=1.0))
        self.collide = bool(cfg.get("sim", "collision", default=True))         # soft body-block separation
        my = cfg.get("env", "my_towers", default=[[0.245, 0.615], [0.745, 0.615], [0.48, 0.72]])
        en = cfg.get("env", "enemy_towers", default=[[0.25, 0.21], [0.72, 0.21], [0.48, 0.12]])
        self._anchors = {0: my, 1: en}
        self.reset()

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> None:
        self.t = 0.0
        self.done = False
        self.outcome: Optional[str] = None       # from team 0's view: win | loss | draw
        self.units: List[Unit] = []
        self.spells: List[_Spell] = []
        self.elixir = {0: 5.0, 1: 5.0}
        self.towers = {}
        for team in (0, 1):
            a = self._anchors[team]
            self.towers[team] = [
                Tower(a[0][0], a[0][1], self.princess_hp, self.princess_hp),
                Tower(a[1][0], a[1][1], self.princess_hp, self.princess_hp),
                Tower(a[2][0], a[2][1], self.king_hp, self.king_hp, king=True, active=False),
            ]
        self.chip = {0: 0.0, 1: 0.0}             # enemy-tower HP you removed this step (both views)
        self.kills = {0: 0, 1: 0}
        self.last_deploy = {0: None, 1: None}    # (spec, x, y, t) of each team's most recent deploy

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
            self.spells.append(_Spell(team, x, y, spec, spec.spell_delay))
            return True
        n = max(1, spec.count)
        for i in range(n):
            ox = x + (0.02 * ((i % 3) - 1)) if n > 1 else 0.0
            oy = y + (0.02 * ((i // 3) - 0.5)) if n > 1 else 0.0
            u = Unit(spec, team, min(max(x + ox, 0.03), 0.97), min(max(y + oy, 0.03), 0.97), spec.hp)
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
        sight = self.siege_sight if u.spec.siege else self.sight_range
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
            if abs(u.x - bx) > 0.02:
                tx, ty = bx, _RIVER
            else:
                tx, ty = bx, ty                              # aligned with the bridge -> cross straight
        d = _dist(u.x, u.y, tx, ty)
        if d < 1e-6:
            return
        step = min(u.spec.speed * spd_mult * dt, d)
        u.x += (tx - u.x) / d * step
        u.y += (ty - u.y) / d * step

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
                dx, dy = a.x - b.x, a.y - b.y
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
                a.x = min(max(a.x + ux * overlap * (am / s), 0.03), 0.97)
                a.y = min(max(a.y + uy * overlap * (am / s), 0.03), 0.97)
                b.x = min(max(b.x - ux * overlap * (bm / s), 0.03), 0.97)
                b.y = min(max(b.y - uy * overlap * (bm / s), 0.03), 0.97)

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
        # spells land
        landed = []
        for s in self.spells:
            s.t -= dt
            if s.t <= 0:
                self._resolve_spell(s)
                landed.append(s)
        for s in landed:
            self.spells.remove(s)
        # units act (deploy delay -> stun/freeze -> slow-aware move + discrete cooldown attacks)
        for u in list(self.units):
            if u.hp <= 0:
                continue
            u.age += dt
            u.cooldown = max(0.0, u.cooldown - dt)
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
            if _dist(u.x, u.y, rx, ry) <= reach + 0.02:
                if u.cooldown <= 0:                          # one discrete hit, then wait hit_speed (slow -> longer)
                    self._attack(u, kind, ref)
                    u.cooldown = u.spec.hit_speed / spd
                    if u.spec.kamikaze:
                        u.hp = 0.0
            elif u.spec.kind != "building":                  # buildings are stationary
                self._move_toward(u, rx, ry, dt, spd)
        if self.collide:
            self._separate()
        # towers fire
        for team in (0, 1):
            for tw in self.towers[team]:
                if tw.alive and (tw.active or not tw.king):
                    self._tower_fire(team, tw, dt)
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

    def _attack(self, u: Unit, kind: str, ref) -> None:
        dmg = u.spec.hit_dmg                                  # one discrete hit (DPS x hit_speed)
        if kind == "tower":
            self._damage_tower(ref, dmg, u.team)
            return
        ref.hp -= dmg
        self._apply_status(u.spec, ref)
        if u.spec.splash:
            for e in self.units:
                if e.team != u.team and e is not ref and _dist(e.x, e.y, ref.x, ref.y) <= _SPLASH_R:
                    e.hp -= dmg
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
                e.hp -= u.spec.pulse_dmg
                if u.spec.pulse_stun > 0:
                    e.stun_left = max(e.stun_left, u.spec.pulse_stun)

    def _tower_fire(self, team: int, tw: Tower, dt: float) -> None:
        rng = self.king_range if tw.king else self.tower_range
        foes = [e for e in self.units if e.team != team and e.hp > 0
                and _dist(tw.x, tw.y, e.x, e.y) <= rng]
        if not foes:
            return
        tgt = min(foes, key=lambda e: _dist(tw.x, tw.y, e.x, e.y))
        tgt.hp -= self.tower_dps * dt

    def _resolve_spell(self, s: _Spell) -> None:
        if s.spec.rolls:
            self._resolve_roll(s)
            return
        for e in self.units:
            if e.team != s.team and _dist(e.x, e.y, s.x, s.y) <= s.spec.spell_radius:
                e.hp -= s.spec.spell_dmg
                self._apply_status(s.spec, e)                 # Zap/Freeze stun; slow spells
        for tw in self._enemy_towers(s.team):
            if _dist(tw.x, tw.y, s.x, s.y) <= s.spec.spell_radius:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)

    def _resolve_roll(self, s: _Spell) -> None:
        """A ROLLING spell (The Log): a forward CORRIDOR from the cast point that damages + KNOCKS BACK
        ground troops in its path (no air). 'Forward' = toward the enemy (up for team 0, down for team 1),
        so a defensive Log shoves the enemy push back UP the arena, away from your tower (buying time). A
        Log whose corridor reaches an enemy tower chips it (poor crown damage) -- the bridge cycle-chip."""
        fdir = -1.0 if s.team == 0 else 1.0
        halfw = s.spec.spell_radius
        for e in self.units:
            if e.team == s.team or (s.spec.ground_only and e.spec.flying):
                continue
            dy = (e.y - s.y) * fdir                           # forward distance along the roll
            if -0.03 <= dy <= s.spec.roll_len and abs(e.x - s.x) <= halfw:
                e.hp -= s.spec.spell_dmg
                e.y += fdir * s.spec.knockback                # knock back in the roll direction
        for tw in self._enemy_towers(s.team):
            dy = (tw.y - s.y) * fdir
            if -0.03 <= dy <= s.spec.roll_len and abs(tw.x - s.x) <= halfw:
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
        my_hp = sum(t.hp for t in self.towers[0])
        op_hp = sum(t.hp for t in self.towers[1])
        if abs(my_hp - op_hp) < 1.0:
            return "draw"
        return "win" if op_hp < my_hp else "loss"

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
