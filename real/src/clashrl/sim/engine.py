"""Headless Clash-Royale-ish match engine (no vision, no rendering by itself).

Medium-fidelity, STAT-DRIVEN from the card knowledge base (clashrl.cards.CardDB): elixir economy,
lane movement with bridge crossing, nearest-target acquisition (incl. building-only + siege rules),
DPS combat with splash, princess/king towers, and area spells. It is deliberately NOT a faithful CR
clone -- exact pathfinding / aggro radii / pushback / champions / evolutions are out of scope. The
point is enough fidelity that a policy trained here transfers as a PRIOR to the real game (then
fine-tuned live). See real/DECK_SWITCH.md (Stage: simulator) and log.txt.

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


def build_spec(db, key: str) -> CardSpec:
    base = key[:-4] if key.endswith("_evo") else key
    c = db.get(base) or {}
    flags = set(db.flags(base))
    kind = c.get("kind", "troop")
    elixir = int(c.get("elixir") or db.elixir(base) or 4)
    hp = float(c.get("hitpoints") or 300)
    dmg = float(c.get("damage") or 0.0)
    hit = float(c.get("hit_speed") or 1.0)
    dps = float(c.get("dps") or (dmg / hit if hit else dmg))
    reach = _REACH.get(db.attack_range(base), 0.03)
    speed = _SPEED.get(c.get("speed"), 0.031)
    count = int(c.get("count") or 1)
    building_only = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    siege = "siege" in flags
    spell_radius = 0.11 if base == "royal_delivery" else 0.09
    spell_delay = 3.0 if base == "royal_delivery" else 0.4
    return CardSpec(
        key=key, base=base, kind=kind, elixir=elixir, hp=hp, dps=dps, reach=reach, speed=speed,
        count=count, flying=db.is_flying(base), attacks_air=db.attacks_air(base),
        splash=db.has_splash(base), building_only=building_only, siege=siege,
        kamikaze="kamikaze" in flags, lifetime=(40.0 if kind == "building" else None),
        spell_radius=spell_radius, spell_dmg=dmg,
        spell_tower_dmg=float(db.tower_damage(base) or dmg), spell_delay=spell_delay)


@dataclass
class Unit:
    spec: CardSpec
    team: int
    x: float
    y: float
    hp: float
    age: float = 0.0
    reach_extra: float = 0.0     # siege sees far (big engage range) even if it hits from reach


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
        if spec.kind == "spell":
            self.spells.append(_Spell(team, x, y, spec, spec.spell_delay))
            return True
        n = max(1, spec.count)
        for i in range(n):
            ox = x + (0.02 * ((i % 3) - 1)) if n > 1 else 0.0
            oy = y + (0.02 * ((i // 3) - 0.5)) if n > 1 else 0.0
            u = Unit(spec, team, min(max(x + ox, 0.03), 0.97), min(max(y + oy, 0.03), 0.97), spec.hp)
            if spec.siege:
                u.reach_extra = self.siege_sight - spec.reach
            self.units.append(u)
        return True

    # -- per-tick simulation ----------------------------------------------
    def _enemy_towers(self, team: int) -> List[Tower]:
        return [t for t in self.towers[1 - team] if t.alive]

    def _acquire(self, u: Unit):
        """Return the (kind, ref) this unit should head for: ('tower', Tower) or ('unit', Unit)."""
        foes = [e for e in self.units if e.team != u.team and e.hp > 0
                and (not e.spec.flying or u.spec.attacks_air or u.spec.flying)]
        towers = self._enemy_towers(u.team)
        if u.spec.building_only:                              # Miner / Hog: go for the tower
            if towers:
                tw = min(towers, key=lambda t: _dist(u.x, u.y, t.x, t.y))
                return ("tower", tw)
            return (None, None)
        if u.spec.siege:                                     # X-Bow: nearest foe in sight, else tower
            near = [e for e in foes if _dist(u.x, u.y, e.x, e.y) <= self.siege_sight]
            if near:
                return ("unit", min(near, key=lambda e: _dist(u.x, u.y, e.x, e.y)))
            if towers:
                return ("tower", min(towers, key=lambda t: _dist(u.x, u.y, t.x, t.y)))
            return (None, None)
        cands = [("unit", e, _dist(u.x, u.y, e.x, e.y)) for e in foes]
        cands += [("tower", t, _dist(u.x, u.y, t.x, t.y)) for t in towers]
        if not cands:
            return (None, None)
        k, ref, _ = min(cands, key=lambda c: c[2])
        return (k, ref)

    def _move_toward(self, u: Unit, tx: float, ty: float, dt: float) -> None:
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
        step = min(u.spec.speed * dt, d)
        u.x += (tx - u.x) / d * step
        u.y += (ty - u.y) / d * step

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
        # units act
        for u in list(self.units):
            if u.hp <= 0:
                continue
            u.age += dt
            kind, ref = self._acquire(u)
            if ref is None:
                continue
            rx, ry = (ref.x, ref.y)
            reach = u.spec.reach + u.reach_extra
            if _dist(u.x, u.y, rx, ry) <= reach + 0.02:
                self._attack(u, kind, ref, dt)
                if u.spec.kamikaze:
                    u.hp = 0.0
            else:
                if u.spec.kind != "building":                # buildings are stationary
                    self._move_toward(u, rx, ry, dt)
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

    def _attack(self, u: Unit, kind: str, ref, dt: float) -> None:
        dmg = u.spec.dps * dt
        if kind == "tower":
            self._damage_tower(ref, dmg, u.team)
        else:
            ref.hp -= dmg
            if u.spec.splash:
                for e in self.units:
                    if e.team != u.team and e is not ref and _dist(e.x, e.y, ref.x, ref.y) <= _SPLASH_R:
                        e.hp -= dmg

    def _tower_fire(self, team: int, tw: Tower, dt: float) -> None:
        rng = self.king_range if tw.king else self.tower_range
        foes = [e for e in self.units if e.team != team and e.hp > 0
                and _dist(tw.x, tw.y, e.x, e.y) <= rng]
        if not foes:
            return
        tgt = min(foes, key=lambda e: _dist(tw.x, tw.y, e.x, e.y))
        tgt.hp -= self.tower_dps * dt

    def _resolve_spell(self, s: _Spell) -> None:
        for e in self.units:
            if e.team != s.team and _dist(e.x, e.y, s.x, s.y) <= s.spec.spell_radius:
                e.hp -= s.spec.spell_dmg
        for tw in self._enemy_towers(s.team):
            if _dist(tw.x, tw.y, s.x, s.y) <= s.spec.spell_radius:
                self._damage_tower(tw, s.spec.spell_tower_dmg, s.team)

    def _damage_tower(self, tw: Tower, dmg: float, by_team: int) -> None:
        if not tw.alive:
            return
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
