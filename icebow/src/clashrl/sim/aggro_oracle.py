"""AGGRO ORACLE -- deterministic answers to "who will attack whom" questions, taken from the ENGINE itself.

Clash Royale targeting is deterministic (sticky lock, sight ranges, building-only targeters, resets from
stun / knockback / tornado shove -- `engine._acquire`), and the sim already implements it. The policy,
however, only ever SEES a memoryless nearest-target guess (`interactions.predict_targets`: 81% agreement
with the engine on LOCKED units, 16-25% on buildings -- HANDOFF §5br) and never QUERIES the rules. This
module is the query side: every answer comes from forking the live engine (one deepcopy, ~6.5 ms) and
advancing the fork, never from re-deriving the rules in a second place that could drift.

Questions it answers (the owner's list, HANDOFF §5br):
  * `target_of(u, horizon)`         -- which card or tower will `u` lock onto / be attacking in `horizon` s
  * `targeted_by(u, horizon)`       -- which cards and towers will be attacking `u`
  * `next_target_after_kill(u)`     -- once `u` kills its current target, what does it go for, and when
  * `after_spell(team, key, x, y)`  -- cast a Tornado / Log / Zap...: every unit's target BEFORE and AFTER
  * `draws(team, key, x, y)`        -- place card Z: what locks onto Z and what Z locks onto once deployed
  * `interpose_window(...)`         -- latest delay at which Z, placed between Y and an enemy, still
                                       steals the enemy's lock (and when the enemy first damages Y)
  * `duel(key_a, key_b)`            -- if two cards lock onto each other, who wins and with how much HP

Identity: fork objects are mapped back to the ORIGINAL engine's Unit / Tower objects (by position in
`eng.units` / `eng.towers` at fork time), so callers compare against the objects they already hold.
Units that only exist inside the fork (a card the query placed, a spawn) are reported as `Placed` /
the fork Unit itself. Nothing here mutates the caller's engine.

Cost: one fork per query plus `horizon / 0.1` engine ticks; `interpose_window` forks once per candidate
delay. Fine for drills, rewards, tests and offline analysis; a per-step obs feature would want the
cheaper lock-aware predictor instead (§5br.4 route 2).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .engine import Tower, Unit, build_spec

TICK = 0.1                 # engine advance step used by every query (matches the drills' cadence)
PLACED = "placed"          # kind tag for a unit the query itself placed


@dataclass(frozen=True)
class Target:
    """What something is going for: ``kind`` is 'unit' | 'tower' | 'placed' | None."""
    kind: Optional[str]
    ref: object = None                 # ORIGINAL engine Unit / Tower, or the fork Unit when 'placed'
    key: str = ""                      # card key ('princess' / 'king' for towers) -- for printing
    team: int = -1

    def is_(self, obj) -> bool:
        return self.ref is obj

    def __repr__(self) -> str:             # a Unit repr is its whole CardSpec -- keep prints readable
        return "Target(None)" if self.kind is None else f"Target({self.kind} {self.key} team{self.team})"


@dataclass(frozen=True)
class Draw:
    """Result of placing card Z: what Z locks onto and who locks onto Z, ``at`` seconds after the tap."""
    z_target: Target
    drawn: List[Target]                # units + towers whose target is Z
    at: float
    z_alive: bool


@dataclass(frozen=True)
class Duel:
    winner: Optional[str]              # key of the survivor (None = both alive at the time limit)
    hp_left: float                     # survivor's HP
    hp_left_frac: float
    t: float                           # seconds until the loser died (or the limit)


class AggroOracle:
    def __init__(self, eng):
        self.eng = eng

    # -- forking ------------------------------------------------------------------------------
    def _fork(self):
        f = copy.deepcopy(self.eng)
        back: Dict[int, object] = {id(fu): ou for fu, ou in zip(f.units, self.eng.units)}
        for team in (0, 1):
            for ft, ot in zip(f.towers[team], self.eng.towers[team]):
                back[id(ft)] = ot
        fwd = {id(ou): fu for fu, ou in zip(f.units, self.eng.units)}
        for team in (0, 1):
            for ft, ot in zip(f.towers[team], self.eng.towers[team]):
                fwd[id(ot)] = ft
        return f, back, fwd

    @staticmethod
    def _describe(obj, back, placed=None) -> Target:
        if obj is None:
            return Target(None)
        orig = back.get(id(obj))
        if isinstance(obj, Tower):
            return Target("tower", orig if orig is not None else obj,
                          "king" if obj.king else "princess", -1)
        if isinstance(obj, Unit):
            if orig is None:                       # exists only inside the fork
                return Target(PLACED if (placed is not None and obj is placed) else "unit", obj,
                              obj.spec.key, obj.team)
            return Target("unit", orig, obj.spec.key, obj.team)
        return Target(None)

    @staticmethod
    def _advance(f, seconds: float) -> None:
        n = int(round(max(0.0, seconds) / TICK))
        for _ in range(n):
            if f.done:
                break
            f.advance(TICK)

    def _place(self, f, team: int, key: str, x: float, y: float, level: int) -> Optional[Unit]:
        """Deploy inside the fork with the elixir constraint lifted (the question is 'what happens
        IF', not 'can I afford it'). Returns the placed unit (None for a spell), found as the newest
        unit of that team and base -- the engine snaps the tap to a tile, so position is not the key."""
        spec = build_spec(f.db, key, level)
        f.elixir[team] = max(f.elixir[team], float(spec.elixir))
        before = set(id(u) for u in f.units)
        if not f.deploy(team, spec, x, y):
            return None
        self._advance(f, 0.0)
        # deploys queue behind the action-latency line; drain it
        for _ in range(20):
            new = [u for u in f.units if id(u) not in before and u.team == team and u.spec.base == spec.base]
            if new or f.done:
                break
            f.advance(TICK)
        new = [u for u in f.units if id(u) not in before and u.team == team and u.spec.base == spec.base]
        return new[0] if new else None

    # -- queries ------------------------------------------------------------------------------
    def targets_at(self, horizon_s: float = 0.0):
        """Every original unit's and tower's target after ``horizon_s`` seconds of nobody playing anything:
        ``{id(original object): (original object, Target)}`` (Unit is a slots dataclass -> unhashable, hence
        the id keys). Dead-by-then units map to ``Target(None)``."""
        f, back, fwd = self._fork()
        self._advance(f, horizon_s)
        out = {}
        for ou in self.eng.units:
            fu = fwd.get(id(ou))
            out[id(ou)] = (ou, self._describe(getattr(fu, "target", None), back)
                           if (fu is not None and fu.hp > 0) else Target(None))
        for team in (0, 1):
            for ot in self.eng.towers[team]:
                ft = fwd[id(ot)]
                out[id(ot)] = (ot, self._describe(ft.target, back) if ft.alive else Target(None))
        return out

    def target_of(self, u, horizon_s: float = 0.0) -> Target:
        return self.targets_at(horizon_s).get(id(u), (u, Target(None)))[1]

    def targeted_by(self, u, horizon_s: float = 0.0) -> List[Target]:
        """Original units AND towers whose target is ``u`` after ``horizon_s``."""
        f, back, fwd = self._fork()
        self._advance(f, horizon_s)
        fu = fwd[id(u)]
        out = []
        for x in list(f.units) + f.towers[0] + f.towers[1]:
            if getattr(x, "target", None) is fu and (getattr(x, "hp", 1.0) > 0 or getattr(x, "alive", True)):
                out.append(self._describe(x, back))
        return out

    def next_target_after_kill(self, u, max_s: float = 30.0) -> Tuple[Optional[float], Target]:
        """Advance until ``u``'s CURRENT target dies (or leaves), then report what ``u`` goes for next.
        Returns ``(seconds until the switch, new Target)``; ``(None, current)`` if it never switches
        within ``max_s`` (target survived, or ``u`` died first -> Target(None))."""
        f, back, fwd = self._fork()
        fu = fwd[id(u)]
        cur = getattr(fu, "target", None)
        if cur is None:                              # nothing locked yet: let it pick first
            self._advance(f, TICK); cur = getattr(fu, "target", None)
        t = 0.0
        while t < max_s and not f.done:
            f.advance(TICK); t += TICK
            if fu.hp <= 0:
                return None, Target(None)
            nt = getattr(fu, "target", None)
            if nt is not cur and nt is not None:
                return round(t, 2), self._describe(nt, back)
        return None, self._describe(getattr(fu, "target", None), back)

    def after_spell(self, team: int, key: str, x: float, y: float, settle_s: float = 1.5,
                    level: int = 11):
        """Cast ``key`` (tornado / log / zap...) at (x, y) and report, per original unit and tower,
        ``(target BEFORE the cast, target AFTER settle_s)`` -- the retarget map, keyed like `targets_at`:
        ``{id(obj): (obj, before, after)}``."""
        before = self.targets_at(0.0)
        f, back, fwd = self._fork()
        self._place(f, team, key, x, y, level)
        self._advance(f, settle_s)
        out = {}
        for k, (obj, b) in before.items():
            fo = fwd.get(k)
            alive = fo is not None and (getattr(fo, "hp", 0.0) > 0 or getattr(fo, "alive", False))
            out[k] = (obj, b, self._describe(getattr(fo, "target", None), back) if alive else Target(None))
        return out

    def draws(self, team: int, key: str, x: float, y: float, horizon_s: float = 3.0,
              level: int = 11) -> Draw:
        """Place card Z at (x, y) now. After its deploy time plus ``horizon_s``: what Z is going for, and
        every original unit / tower that is going for Z."""
        f, back, fwd = self._fork()
        z = self._place(f, team, key, x, y, level)
        if z is None:
            return Draw(Target(None), [], 0.0, False)
        t = 0.0
        while getattr(z, "deploy_left", 0.0) > 0.0 and t < 10.0 and not f.done:
            f.advance(TICK); t += TICK
        self._advance(f, horizon_s); t += horizon_s
        drawn = [self._describe(o, back) for o in list(f.units) + f.towers[0] + f.towers[1]
                 if getattr(o, "target", None) is z and id(o) in back]
        return Draw(self._describe(getattr(z, "target", None), back, placed=z), drawn, round(t, 2), z.hp > 0)

    def first_damage_to(self, victim, by, max_s: float = 20.0) -> Optional[float]:
        """Seconds until ``by`` first damages ``victim`` with nobody playing anything (None = never).
        A Unit victim is read through `last_unit_hit_t` (buildings also LOSE hp to their lifetime, so an
        hp drop alone is not a hit); a Tower victim through its hp."""
        f, back, fwd = self._fork()
        fv, fb = fwd[id(victim)], fwd[id(by)]
        t0 = f.t; h0 = fv.hp; t = 0.0
        while t < max_s and not f.done:
            f.advance(TICK); t += TICK
            if getattr(fb, "target", None) is not fv:
                if getattr(fb, "hp", 1.0) <= 0:
                    return None
                continue
            if isinstance(fv, Unit):
                if fv.last_unit_hit_t >= t0:
                    return round(t, 2)
            elif fv.hp < h0 - 1e-6:
                return round(t, 2)
        return None

    def interpose_window(self, team: int, key: str, x: float, y: float, enemy, protect,
                         max_delay_s: float = 6.0, step_s: float = 0.2, settle_s: float = 0.5,
                         level: int = 11):
        """Place Z (``key`` at x, y) after a delay d and ask whether ``enemy`` is then locked onto Z
        rather than ``protect``. Returns ``(latest working delay or None, earliest failing delay or
        None, seconds until enemy first damages protect if nothing is played)``. Scans d = 0, step,
        2*step... up to max_delay_s -- one fork each."""
        hit_at = self.first_damage_to(protect, enemy)
        latest_ok, first_fail = None, None
        d = 0.0
        while d <= max_delay_s + 1e-9:
            f, back, fwd = self._fork()
            fe = fwd[id(enemy)]
            self._advance(f, d)
            z = self._place(f, team, key, x, y, level)
            ok = False
            if z is not None:
                t = 0.0
                while getattr(z, "deploy_left", 0.0) > 0.0 and t < 10.0 and not f.done:
                    f.advance(TICK); t += TICK
                self._advance(f, settle_s)
                ok = (fe.hp > 0 and getattr(fe, "target", None) is z)
            if ok:
                latest_ok = round(d, 2)
            elif first_fail is None and latest_ok is not None:
                first_fail = round(d, 2)
            d += step_s
        return latest_ok, first_fail, hit_at

    def duel(self, key_a: str, key_b: str, level: int = 11, max_s: float = 90.0,
             gap_tiles: float = 1.0) -> Duel:
        """A alone against B alone, towers silenced, starting ``gap_tiles`` apart in our half.
        Winner + HP left. Squads (a card with several bodies) are placed as one deploy."""
        f, back, fwd = self._fork()
        f.units.clear(); f.spells.clear(); f.projectiles.clear()
        for tw in f.towers[0] + f.towers[1]:
            tw.hit_dmg = 0.0
        ya = 0.62; yb = ya - gap_tiles / 32.0
        a = self._place(f, 0, key_a, 0.5, ya, level)
        b = self._place(f, 1, key_b, 0.5, yb, level)
        if a is None or b is None:
            return Duel(None, 0.0, 0.0, 0.0)
        side = lambda tm: [u for u in f.units if u.team == tm and u.hp > 0]
        t = 0.0
        while t < max_s and not f.done and side(0) and side(1):
            f.advance(TICK); t += TICK
        alive0, alive1 = side(0), side(1)
        if alive0 and not alive1:
            hp = sum(u.hp for u in alive0); mx = sum(u.spec.hp for u in alive0)
            return Duel(key_a, round(hp, 1), round(hp / max(1.0, mx), 3), round(t, 1))
        if alive1 and not alive0:
            hp = sum(u.hp for u in alive1); mx = sum(u.spec.hp for u in alive1)
            return Duel(key_b, round(hp, 1), round(hp / max(1.0, mx), 3), round(t, 1))
        return Duel(None, 0.0, 0.0, round(t, 1))
