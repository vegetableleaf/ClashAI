"""Dead reckoning of a RAW observation H ticks ahead (L68 T10): counter the live tap->land lag at decision time.

Training rows pair a pro placement with the board at the tick the card EXECUTED; live, our card executes ~26 ticks
after the frame we decided on. ``extrapolate`` guesses the board at landing from the last two observations, BEFORE
``obs_contract.from_engine``, so the screen (e1_eval cfg ``extrapolate_ticks``) and the live path share one function.

Accepted shapes (both are what ``from_engine`` / the live reader hand around):
  * the engine raw ``observe()`` dict (``pipeline/royale_env.RoyalePoolEnv.raw``, the real engine, and
    ``live_mem.to_observe``'s output): ``tick``, entity id ``entity_id``, my elixir ``players[].elixir_exact``;
  * the live reader frame: ``game_tick``, entity id ``address``, my elixir ``players[].elixir_raw`` (1e-4 elixir).

Advanced:
  * each entity seen in BOTH observations (same id, side and card_id -- the side/card check keeps a reused reader
    address from pairing two different bodies) moves pos + v * H, v = displacement / tick gap, clamped to the
    board 0..18000 x 0..32000 (engine units, 1,000 per tile);
  * the clock: ``tick`` / ``game_tick`` + H (so from_engine's t_sec / double-elixir / overtime phase follow);
  * MY elixir: + ``opp_elixir_count.regen_between(tick, tick + H)``, capped at 10;
  * opt-in v4 normalized public objects: catalog-speed projectile motion, remaining TTI and effect clocks.
    The advanced view is attached as ``extrapolated_public_objects``; source collections stay untouched for
    legacy consumers. V4 inference MUST pass this view to PublicObserver.features instead of cached objects.
NOT advanced / simulated: entities without a previous sighting (new or deploying bodies stay put), towers (crown
towers are never moved: ``episode.crown_towers`` is not touched and card_id < 0 entities stay put), HP, deaths,
spawns, targets and retargeting (a unit that stops to attack mid-window overshoots), hand / next card, and the
OPPONENT's elixir (left to the caller, which must not read the true value). Public objects are unchanged unless
the caller explicitly supplies the v4 snapshot; H=0 and legacy calls retain their previous output.

OPT-IN ``drops`` (``predict_drops``; L73 Skeleton Barrel audit; absent = byte-identical): the one spawn that IS simulated.
An enemy Skeleton Barrel balloon that VANISHES from the observed board (``DropTracker.observe``: present in the last
observation, absent now; killed or arrived) drops its 7 skeletons 12 ticks after the first absent observation (live
2-tick frames: 30 / 39 exactly 12; the engine's spec). ``extrapolate(..., drops=tracker.pending)`` adds those 7 bodies on
the measured spawn ring (CHILD_RING: tight at the drop point, ~1.46 tiles by 3 ticks) around the balloon's last observed position once T + 12 <= tick + h, shaped exactly like the real
children (the parent's card id / name -- the reader and the engine give a barrel's skeletons the BARREL's id, max_hp 81 at
level 11 scaled to the balloon's level), so fv4 and fv5 classify them as they classify the real ones. Only observed
disappearances count; no hidden state.

OPT-IN ``own_effects`` (W1, owner 2026-10-08; absent / None = byte-identical): MY OWN recent / pending plays move the
enemy bodies they reach. Dead reckoning alone mis-forecast 0.41 of moving enemy bodies by >= 1.5 tiles inside the zone of
my Log / Tornado / hero Ice Wizard ability of the last 2 s, against 0.11 with no recent play (owner_1008/q3_forecast.out):
the Log pushes the Hog back, but the next decision still saw it walking into the Tornado. ``own_effects`` = my accepted
plays as dicts ``card`` (any spelling ``card_key`` reads), ``x``, ``y`` (the tap, RAW engine units, as the entities),
``tick`` (the LANDING tick: SIM ``Match._land``'s, live the confirmation frame's) and optionally ``ability=True`` (a
confirmed hero-ability press; x / y unused). Only public inputs: my own plays and the observed bodies. Each ENEMY body a
play reaches is re-tracked tick by tick over (prev tick, tick + h]: its walk velocity is the observed displacement with the
effects' own displacement taken out, over the ticks it actually walked (a Log hit between the two observations no longer
reads as walking backwards), then the walk is replayed with the effects' displacement added. Bodies no effect reaches keep
the plain pos + v * H (so a far-away unit is byte-identical). Numbers (RoyaleSim ``data/derived/cards.json`` = the catalog,
``data/calibration.json`` = its measured laws, both under research/ext/Royale/RoyaleSim/data):
  * KNOCKBACK LADDER (calibration knockback.DISPLACEMENT_LAW = client16402): a push of length L replaces the walk for n+1
    ticks with steps 25n-25, ..., 25, 0, -25 (n smallest with 25n(n+1)/2 >= L, steps capped 250) from the tick after the
    hit; a push landing while a ladder runs is refused (knockback.STACKING first_wins_while_active).
  * The Log (cards.json Log): airborne MinDistance 3000 at speed 360 (no hitbox; SPELL_AS_DEPLOY_LAUNCH_MODEL
    airborne_from_behind_lands_on_tap), then rolls 10100 from the tap at 200 / tick along my forward y, hitting GROUND bodies
    within the 1950 half-width (+ the body's collision radius) and 600 along the axis (+ radius) once each, push 700 (all
    bodies: PushbackAll) radially from the roll centre (knockback.DIRECTION_ROLLING). Live-checked: the reader's Log
    projectile is 1.92 tiles behind the tap 2 ticks after the confirmation and rolls 0.2 tiles / tick from ~8 ticks after it.
  * Tornado (cards.json Tornado area_effect_object): radius 5500, life 1050 ms = 21 ticks, AttractPercentage 360: every
    tick each enemy body within radius (+ its radius) of the centre steps L = S * 360 / 100 toward it, S = its catalog
    speed, ADDED to its walk, air too, ignore-pushback bodies too (calibration status.ATTRACT_LAW base_speed; Knight 216);
    from the landing tick + 1 (status.ATTRACT_ONSET: the client pulls a tick late).
  * Fireball / Rocket and any other catalog projectile spell with PushbackMilli (Fireball 1000 r 2500, Rocket 1800 r 2000):
    flies from my king tower at its catalog speed, pushes bodies inside its radius radially from the impact point; bodies
    with IgnorePushback unaffected unless PushbackAll.
  * Hero Ice Wizard ability (Frosty Fella; NOT in the catalog -- RoyaleSim has no hero Ice Wizard, the wiki page is
    empty): hero_button.py's reading, snowman behind the hero's target, every enemy within 2.5 tiles of it frozen. The
    target = the enemy nearest my Ice Wizard within his 5.5-tile range. Timing LIVE-MEASURED (w1/freeze_profile.py, 84
    presses, bodies within 2.5 tiles of that target that were walking): share standing still 0.05-0.12 before the
    confirmation, 0.48 at +8..+11 ticks, 0.62-0.71 from +12 to +71, falling from +72 -> frozen ticks [T + 10, T + 70).
    Frozen = no walk (pulls and pushes still move it).
NOT modelled: the Ice Wizard troop's own slow (continuous; the observed velocity already carries it), damage / deaths,
retargeting after a push, river / building collisions, the opponent's spells.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Mapping, Optional
from collections import Counter

from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between

BOARD_X, BOARD_Y = 18000.0, 32000.0

# predict_drops: Skeleton Barrel (the balloon AND its skeletons carry the id, told apart by max_hp). Ids: reader / native
# base and evo card ids; the SIM (RoyaleSim) uses 56 for both forms (evo = status bit 8, or the level-11 evo hp 665).
SB_CARDS = {26000056: 532.0, 13000056: 665.0, 56: 532.0}        # card id -> balloon max_hp at level 11
EVO_CARD, EVO_HP11 = 13000056, 665.0
BALLOON_MIN_HP = 300                                  # balloon 532..967; its skeletons 81..130
CHILD_HP11, N_CHILD = 81.0, 7                         # skeleton max_hp at level 11, count
# Live-measured (30 exact drops, 210 children, 2-tick frames; fix/age_profile.py): the 7 spawn near the drop point and
# jump out to a ring in ~3 ticks -- median radius by age 0 / 1 / 2 / >= 3 ticks since spawn, millitiles; body kind 14
# (deploying) until age 9, then 15. (The audit's hand-placed counterfactual used a 1.3-tile ring at every age.)
CHILD_RING, CHILD_DEPLOY_TICKS = (250.0, 630.0, 960.0, 1460.0), 9
# skeletons appear T + 12 (T = first absent tick; first sighting up to T + 15 live). A drop whose skeletons are not on the board
# by T + 18 has none alive to show (killed at once / never spawned: SIM probe, 2 of 32), so the pending entry ends there.
DROP_DELAY, DROP_TTL = 12, 18
DROP_FIRST, CLAIM_RADIUS = DROP_DELAY - 2, 4500.0     # an old drop can claim children from T + 10 (12 +- 2); children within 4.5 tiles


def _tick_key(obs: Mapping[str, Any]) -> str:
    return "tick" if "tick" in obs else "game_tick"


def _eid(e: Mapping[str, Any]):
    return e.get("entity_id", e.get("address"))


def _is_sb(e: Mapping[str, Any]) -> bool:
    return int(e.get("card_id", -1)) in SB_CARDS or e.get("name") == "SkeletonBalloon"


def _is_balloon(e: Mapping[str, Any]) -> bool:
    return _is_sb(e) and float(e.get("max_hp") or 0) >= BALLOON_MIN_HP


def _sig(e: Mapping[str, Any]) -> tuple:
    return (_eid(e), e.get("side"), e.get("card_id"), e.get("max_hp"))


def _is_evo(e: Mapping[str, Any]) -> bool:
    if int(e.get("card_id", -1)) == EVO_CARD:
        return True
    flags = e.get("status_flags")
    if flags is not None and int(flags) >= 0:          # SIM: bit 8 = evolution, 16 = hero
        return bool(int(flags) & 8)
    return float(e.get("max_hp") or 0) == EVO_HP11


def _child_hp(balloon: Mapping[str, Any]) -> float:
    """Skeleton max_hp at the balloon's card level: CR scales +10% per level (balloon 532/586/642/705/773 -> skeleton
    81/89/98/108/119, live-measured; the evo balloon starts at 665 but drops the same 81-hp skeletons)."""
    base = EVO_HP11 if _is_evo(balloon) else SB_CARDS[26000056]
    level = round(math.log(float(balloon["max_hp"]) / base) / math.log(1.1))
    return float(round(CHILD_HP11 * 1.1 ** max(level, 0)))


class DropTracker:
    """Observed-only memory of enemy Skeleton Barrel balloons that left the board (see the module docstring).

    ``observe(obs, my_side)`` once per observation in ascending tick order (a smaller tick = a new match: reset);
    ``pending`` is what ``extrapolate(drops=...)`` reads. A pending drop ends when its own real skeletons are observed
    ("fresh" Skeleton Barrel bodies below balloon hp, matched one-to-one to the NEAREST drop within 4.5 tiles, at most 7
    per drop, an older drop only from T + 10 on), when the same balloon reappears (a one-frame flicker, not a death), or
    after T + 18. Children already on the board in the first observation without the balloon (a SIM decision gap of up
    to 30 ticks) satisfy the drop at once: it is never registered. (An EVO barrel drops twice -- 7 skeletons while its body
    lingers on arrival, 7 more 12-15 ticks after it vanishes, live 4 of 4 and SIM -- so older children near a vanishing
    balloon are not a reason to skip the drop.)"""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.pending: list[dict] = []
        self._last: Optional[dict] = None
        self._tick: Optional[int] = None

    def observe(self, obs: Mapping[str, Any], my_side: int) -> None:
        tick = int(obs[_tick_key(obs)])
        if self._tick is not None and tick < self._tick:
            self.reset()
        ents = {_eid(e): e for e in obs.get("entities") or () if _eid(e) is not None}
        last = self._last
        if last is not None:
            old = [d for d in self.pending if tick <= d["t0"] + DROP_TTL
                   and not (_eid(d["parent"]) in ents and _sig(ents[_eid(d["parent"])]) == _sig(d["parent"]))]
            new = [dict(t0=tick, x=float(e["x"]), y=float(e["y"]), parent=dict(e)) for k, e in last.items()
                   if _is_balloon(e) and int(e["side"]) != int(my_side) and (k not in ents or _sig(ents[k]) != _sig(e))]
            fresh = [e for k, e in ents.items() if _is_sb(e) and not _is_balloon(e) and (k not in last or _sig(last[k]) != _sig(e))]
            cands = [d for d in old if tick >= d["t0"] + DROP_FIRST] + new
            pairs = sorted((math.hypot(f["x"] - d["x"], f["y"] - d["y"]), fi, di) for fi, f in enumerate(fresh)
                           for di, d in enumerate(cands) if int(f["side"]) == int(d["parent"]["side"]))
            used, got = set(), Counter()
            for dist, fi, di in pairs:
                if dist <= CLAIM_RADIUS and fi not in used and got[di] < N_CHILD:
                    used.add(fi)
                    got[di] += 1
            done = {id(cands[di]) for di in got}
            self.pending = [d for d in old + new if id(d) not in done]
        self._last, self._tick = ents, tick


def predicted_children(d: Mapping[str, Any], age: int) -> list[dict]:
    """The 7 skeleton bodies of one pending drop ``age`` ticks after they spawn: the parent's own entity dict (so the
    reader frame and the engine ``observe()`` dict both accept them) re-positioned on the ring with the children's
    hp, deploying kind while fresh, and a synthetic id."""
    p, hp = d["parent"], _child_hp(d["parent"])
    r = CHILD_RING[min(max(age, 0), len(CHILD_RING) - 1)]
    kinds = (14, 15) if int(p.get("kind", 15)) >= 14 else (12, 0)      # reader kinds vs the SIM's (12 = deploying)
    kind = kinds[age >= CHILD_DEPLOY_TICKS]
    key = "entity_id" if "entity_id" in p else "address"
    out = []
    for k in range(N_CHILD):
        a = 2 * math.pi * k / N_CHILD
        c = dict(p, x=min(max(d["x"] + r * math.cos(a), 0.0), BOARD_X),
                 y=min(max(d["y"] + r * math.sin(a), 0.0), BOARD_Y), hp=hp, max_hp=hp, kind=kind)
        c[key] = f"predicted_drop_{d['t0']}_{k}"
        out.append(c)
    return out


def advance_public_objects(observed, previous, gap, h):
    """Project normalized public objects without updating observation history or inventing spawns.

    Ambiguous identity-free tracks cannot supply velocity. Known TTI uses the R6 catalog definition first;
    multi-stage shots retain their causal-motion estimate. Unknown targets/timing stay unknown.
    """
    from .projectile_observation import catalog_tti
    from .projectile_motion import ProjectileMotion
    rows = observed['projectiles']
    old_rows = (previous or {}).get('projectiles', [])
    counts = Counter(ProjectileMotion.key(r) for r in rows)
    old_counts = Counter(ProjectileMotion.key(r) for r in old_rows)
    old = {ProjectileMotion.key(r): r for r in old_rows}
    shots, areas = [], []
    landed = 0
    for key, side, x, y, tx, ty, ms in rows:
        if tx is not None and ty is not None:
            catalog_ms = catalog_tti(key, x, y, tx, ty)
            if catalog_ms is not None:
                ms = catalog_ms
        if ms is not None and tx is not None and ty is not None:
            if ms <= h * 50:
                x, y, ms = tx, ty, 0.0
                landed += 1
            else:
                fraction = h * 50 / ms
                x, y = x + (tx-x)*fraction, y + (ty-y)*fraction
                ms -= h * 50
        else:
            track = (key, side, tx, ty)
            if 0 < gap <= 20 and counts[track] == old_counts[track] == 1:
                p = old[track]
                dx, dy = (x-p[2])*h/gap, (y-p[3])*h/gap
                # Unknown-TTI motion uses only a unique earlier public observation.
                x, y = min(max(x+dx, 0.0), BOARD_X), min(max(y+dy, 0.0), BOARD_Y)
        shots.append((key, side, x, y, tx, ty, ms))
    expired = 0
    for key, side, x, y, ms in observed['effects']:
        if ms is not None:
            ms -= h * 50
            if ms <= 0:
                expired += 1
                continue
        areas.append((key, side, x, y, ms))
    return dict(projectiles=shots, effects=areas), dict(landed_in_lookahead=landed, expired_in_lookahead=expired)


# ---------------------------------------------------------------- OPT-IN own_effects (module docstring)
FREEZE_ONSET, FREEZE_END, FREEZE_R, IW_REACH = 10, 70, 2500.0, 5500.0   # live-measured window; hero_button.py radii
KING_Y = 3000.0                       # my king tower centre, my frame (obs_contract.KING_TILE), engine units
TICK_MS = 50                          # calibration.json time.TICK_MS
PRE_TICKS = 80                        # hits looked for before the observed window (a Log rolls ~59 ticks)
V_CAP = 1.5                           # a recovered walk faster than 1.5 x catalog speed (or the observed pace) = implausible


def ladder(length: float) -> list[int]:
    """Per-tick push steps of a knockback of ``length`` (calibration.json knockback.DISPLACEMENT_LAW = client16402):
    v0 = 25n, n smallest with 25n(n+1)/2 >= length; each tick speed -= 25, then step min(speed, 250), until -25."""
    n = 1
    while 25 * n * (n + 1) // 2 < length:
        n += 1
    return [min(v, 250) for v in range(25 * n - 25, -26, -25)]


@lru_cache(maxsize=1)
def catalog() -> dict:
    """card_key -> RoyaleSim cards.json row (base cards; evo / hero forms share their body numbers to first order)."""
    import json
    from .dataset_gen import card_key
    from .obs_contract import REPO
    data = json.loads((REPO / "research/ext/Royale/RoyaleSim/data/derived/cards.json").read_text(encoding="utf-8"))
    out = {}
    for c in data["cards"]:
        for n in (c["name"], c["display_name"]):
            out.setdefault(card_key(n), c)
    return out


def _row(e: Mapping[str, Any]) -> Optional[dict]:
    """The catalog row of an observed body: SIM bodies carry ``name``, reader bodies only ``card_id``."""
    from .dataset_gen import card_key
    name = e.get("name")
    if name is None:
        from .obs_contract import _catalog_names
        name = _catalog_names().get(int(e.get("card_id", -1)))
    return catalog().get(card_key(name)) if name else None


def own_effect_list(own_effects, ents, my_side: int, lo: int, hi: int) -> list[dict]:
    """My plays -> the effects acting on some tick in (lo, hi], with their geometry in raw engine units."""
    from .dataset_gen import card_key
    fwd = 1.0 if int(my_side) == 0 else -1.0
    kx, ky = 9000.0, KING_Y if fwd > 0 else BOARD_Y - KING_Y
    out = []
    for p in own_effects:
        key, t = card_key(str(p["card"])), int(p["tick"])
        if p.get("ability"):
            if key != "ice-wizard" or not (t + FREEZE_ONSET <= hi and t + FREEZE_END > lo + 1):
                continue
            mine = [e for e in ents if int(e["side"]) == int(my_side) and (_row(e) or {}).get("name") == "IceWizard"]
            foes = [e for e in ents if int(e["side"]) != int(my_side) and int(e.get("card_id", -1)) >= 0]
            near = [(math.hypot(f["x"] - w["x"], f["y"] - w["y"]), i) for w in mine for i, f in enumerate(foes)]
            near = [n for n in near if n[0] <= IW_REACH]
            if near:
                c = foes[min(near)[1]]
                out.append(dict(kind="freeze", t0=t + FREEZE_ONSET, t1=t + FREEZE_END, air=True, ground=True,
                                eids={_eid(f) for f in foes if math.hypot(f["x"] - c["x"], f["y"] - c["y"]) <= FREEZE_R}))
            continue
        c = catalog().get(key)
        if c is None or c.get("kind") != "spell":
            continue
        x, y = float(p["x"]), float(p["y"])
        pr, area = c.get("projectile") or {}, (c.get("spell") or {}).get("area_effect_object") or {}
        roll = pr.get("spawn_projectile") or {}
        if roll.get("projectile_range_milli") and roll.get("pushback_milli"):          # the Log
            t0 = t + pr["min_distance_milli"] / pr["speed"]
            if t0 <= hi and t0 + roll["projectile_range_milli"] / roll["speed"] > lo:
                out.append(dict(kind="roll", x=x, y=y, t0=t0, v=roll["speed"] * fwd, len=roll["projectile_range_milli"],
                                hw=roll["projectile_radius_milli"], ry=roll["projectile_radius_y_milli"],
                                push=roll["pushback_milli"], all=roll["pushback_all"], air=roll["aoe_to_air"],
                                ground=roll["aoe_to_ground"]))
        elif (area.get("buff") or {}).get("attract_percentage"):                         # Tornado
            t0, t1 = t + 1, t + 1 + area["life_duration_ms"] // TICK_MS
            if t0 <= hi and t1 > lo + 1:
                out.append(dict(kind="pull", x=x, y=y, t0=t0, t1=t1, r=area["radius_milli"],
                                pct=area["buff"]["attract_percentage"], air=area["hits_air"], ground=area["hits_ground"]))
        elif pr.get("pushback_milli") and pr.get("speed"):                               # Fireball, Rocket
            ti = t + math.ceil(math.hypot(x - kx, y - ky) / pr["speed"])
            if lo < ti <= hi:
                out.append(dict(kind="push", x=x, y=y, t=ti, r=pr["radius_milli"], push=pr["pushback_milli"],
                                all=pr["pushback_all"], air=pr["aoe_to_air"], ground=pr["aoe_to_ground"]))
    return out


def _unit(dx: float, dy: float, default: tuple) -> tuple:
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 0 else default


def retrack(e: Mapping[str, Any], p: Optional[Mapping[str, Any]], gap: int, tick: int, h: int, fx: list,
            my_side: int) -> Optional[tuple]:
    """(x, y) of enemy body ``e`` at tick + h under my effects ``fx``; None = no effect reaches it (or not an enemy
    troop): the caller keeps plain dead reckoning. ``p`` = its previous sighting ``gap`` ticks earlier, or None."""
    if not fx or int(e["side"]) == int(my_side) or int(e.get("card_id", -1)) < 0:
        return None
    row = _row(e) or {}
    if row.get("kind") in ("building", "spell"):
        return None
    r = float(row.get("collision_radius_milli") or 500)
    air = float(row.get("flying_height") or 0) > 0
    speed = row.get("speed")
    x0, y0 = float(e["x"]), float(e["y"])
    dx, dy = (x0 - float(p["x"]), y0 - float(p["y"])) if p is not None else (0.0, 0.0)
    if speed is None:                                          # unknown body: its observed pace
        speed = math.hypot(dx, dy) / gap if p is not None and gap > 0 else 0.0
    eid, fwd = _eid(e), (1.0 if int(my_side) == 0 else -1.0)
    ladders, hit, touched = [], set(), False

    def act(k, x, y):
        """Tick k on a body standing at (x, y) at the tick's start -> (walk multiplier, extra dx, extra dy)."""
        nonlocal touched
        m, ex, ey = 1.0, 0.0, 0.0
        for s0, steps, ux, uy in ladders:
            if s0 <= k < s0 + len(steps):
                m, ex, ey = 0.0, ex + ux * steps[k - s0], ey + uy * steps[k - s0]
        busy = any(s0 <= k < s0 + len(st) for s0, st, _, _ in ladders) or any(s0 > k for s0, _, _, _ in ladders)
        for i, f in enumerate(fx):
            if not (f["air"] if air else f["ground"]):
                continue
            kind = f["kind"]
            if kind == "freeze":
                if eid in f["eids"] and f["t0"] <= k < f["t1"]:
                    m = 0.0
            elif kind == "pull":
                d = math.hypot(f["x"] - x, f["y"] - y)
                if f["t0"] <= k < f["t1"] and 0 < d <= f["r"] + r:
                    step = int(speed * f["pct"] / 100)             # tdiv(S * AttractPercentage, 100)
                    ex, ey = ex + (f["x"] - x) / d * step, ey + (f["y"] - y) / d * step
            elif i not in hit and not busy:
                if kind == "roll":
                    a = (k - f["t0"]) * abs(f["v"])
                    cy = f["y"] + f["v"] * (k - f["t0"])
                    if not (0 <= a <= f["len"] and abs(x - f["x"]) <= f["hw"] + r and abs(y - cy) <= f["ry"] + r):
                        continue
                    u = _unit(x - f["x"], y - cy, (0.0, fwd))
                else:                                             # push: one impact tick
                    if k != f["t"] or (row.get("ignore_pushback") and not f["all"]) \
                            or math.hypot(x - f["x"], y - f["y"]) > f["r"] + r:
                        continue
                    u = _unit(x - f["x"], y - f["y"], (0.0, fwd))
                hit.add(i)
                ladders.append((k + 1, ladder(f["push"]), u[0], u[1]))
                busy = True
        touched = touched or m != 1.0 or ex != 0.0 or ey != 0.0
        return m, ex, ey

    tp = tick - gap if p is not None and gap > 0 else tick
    first = min(int(math.floor(f.get("t0", f.get("t", tp)))) for f in fx)
    for k in range(max(first, tp - PRE_TICKS), tp + 1):         # before the window: who was ALREADY hit (each body
        act(k, x0 + (k - tick) * dx / max(gap, 1), y0 + (k - tick) * dy / max(gap, 1))    # once; ladders run on)
    touched = False
    sm, sx, sy = 0.0, 0.0, 0.0                                    # the observed window: what the walk did
    if p is not None and gap > 0:
        for k in range(tp + 1, tick + 1):
            w = (k - 1 - tp) / gap
            m, ex, ey = act(k, float(p["x"]) + dx * w, float(p["y"]) + dy * w)
            sm, sx, sy = sm + m, sx + ex, sy + ey
    vx, vy = ((dx - sx) / sm, (dy - sy) / sm) if sm > 0 else (0.0, 0.0)
    if math.hypot(vx, vy) > max(V_CAP * float(speed), math.hypot(dx, dy) / gap if gap > 0 else 0.0):
        # the walk this needs is faster than the body can walk: the push the geometry put inside the window did not
        # happen there (it landed before the earlier sighting) -- keep the observed pace, drop the past ladders
        ladders[:] = [lad for lad in ladders if lad[0] > tick]
        vx, vy = (dx / gap, dy / gap) if gap > 0 else (0.0, 0.0)
    x, y = x0, y0
    for k in range(tick + 1, tick + int(h) + 1):
        m, ex, ey = act(k, x, y)
        x, y = x + vx * m + ex, y + vy * m + ey
    if not touched:
        return None
    return min(max(x, 0.0), BOARD_X), min(max(y, 0.0), BOARD_Y)


def extrapolate(obs: Mapping[str, Any], prev: Optional[Mapping[str, Any]], h: int, my_side: int, *,
                public_objects=None, previous_objects=None, object_gap_ticks=0, drops=None, own_effects=None) -> dict:
    """``obs`` advanced ``h`` ticks (a new dict; the inputs are not modified). ``prev`` = an earlier observation of
    the same match (None -> no motion, clock + my elixir still advance). See the module docstring."""
    h = int(h)
    tk = _tick_key(obs)
    tick = int(obs[tk])
    out = dict(obs)
    out[tk] = tick + h
    gap = tick - int(prev[_tick_key(prev)]) if prev is not None else 0
    before = {}
    if gap > 0:
        before = {_eid(e): e for e in prev.get("entities") or () if _eid(e) is not None}
    fx = (own_effect_list(own_effects, obs.get("entities") or (), my_side, tick - gap if gap > 0 else tick, tick + h)
          if own_effects and h else None)                # opt-in own_effects; None/[] -> the loop below is unchanged
    ents = []
    for e in obs.get("entities") or ():
        e = dict(e)
        p = before.get(_eid(e)) if int(e.get("card_id", -1)) >= 0 else None
        paired = p is not None and p.get("side") == e.get("side") and p.get("card_id") == e.get("card_id")
        moved = retrack(e, p if paired else None, gap, tick, h, fx, my_side) if fx else None
        if moved is not None:
            e["x"], e["y"] = moved
        elif paired:
            e["x"] = min(max(e["x"] + (e["x"] - p["x"]) * h / gap, 0.0), BOARD_X)
            e["y"] = min(max(e["y"] + (e["y"] - p["y"]) * h / gap, 0.0), BOARD_Y)
        ents.append(e)
    if drops:                                          # opt-in predict_drops: simulate the (invisible) 12-tick fall
        ents += [c for d in drops if d["t0"] + DROP_DELAY <= tick + h
                 for c in predicted_children(d, tick + h - d["t0"] - DROP_DELAY)]
    if "entities" in obs:
        out["entities"] = ents
    g = regen_between(tick, tick + h)
    players = []
    for p in obs.get("players") or ():
        p = dict(p)
        if int(p["side"]) == int(my_side):
            if "elixir_exact" in p:
                p["elixir_exact"] = min(MAX_ELIXIR, float(p["elixir_exact"]) + g)
            if "elixir_raw" in p:
                p["elixir_raw"] = min(MAX_ELIXIR * 1e4, float(p["elixir_raw"]) + g * 1e4)
        players.append(p)
    if "players" in obs:
        out["players"] = players
    if h and public_objects is not None:
        out['extrapolated_public_objects'], out['public_lookahead_counts'] = advance_public_objects(
            public_objects, previous_objects, object_gap_ticks, h)
    return out


# ---------------------------------------------------------------- --pipeline-plays: my PENDING plays on the board
EVEN_KEYS = {"tesla"}                 # 2x2 buildings snap to their tapped tile's lower-left corner (live_gen.EVEN_BUILDINGS)
LOG_AIR_TICKS = 9                     # the Log rolls from the tap from ~9 ticks after the act (RoyaleSim probe, L74)


def pending_board(pending, my_side: int, view_tick: int) -> tuple[list, list, list]:
    """My pending plays as RoyaleSim shows them ``view_tick - land`` ticks after they executed (L74
    probe_sim_objects.py; a play shows nothing on its own landing tick). ``pending``: dicts ``card`` (any spelling
    ``card_key`` reads), ``x``, ``y`` (the tap, RAW engine units), ``land`` (its execution tick). -> (bodies
    [(card key, x, y, id < 0 unique per play and body)], projectile rows (key, side, x, y, tx, ty, ms), effect rows
    (key, side, x, y, ms)) in raw units, the ``extrapolated_public_objects`` row shapes. Taps snap to the tile centre (2x2: the tile's lower-left corner).
      troop / building: ``count`` bodies at the tap (count 3: the triangle of radius summon_radius / cos 30 deg);
      projectile spell (Rocket, Fireball): from my king tower at its catalog speed, catalog time to impact;
      the Log: airborne from 3000 behind the tap to it, then rolling 200 / tick toward tap + 10100 (time unknown);
      area spell (Tornado): at the tap, remaining life_duration_ms - 50 / tick."""
    from .dataset_gen import card_key
    from .projectile_observation import catalog_tti
    fwd = 1.0 if int(my_side) == 0 else -1.0
    kx, ky = 9000.0, KING_Y if fwd > 0 else BOARD_Y - KING_Y
    bodies, shots, areas = [], [], []
    for p in pending:
        key, age = card_key(str(p["card"])), int(view_tick) - int(p["land"])
        c = catalog().get(key)
        if c is None or age < 1:
            continue
        corner = key in EVEN_KEYS
        x, y = (math.floor(float(v) / 1000) * 1000.0 + (0.0 if corner else 500.0) for v in (p["x"], p["y"]))
        if c.get("kind") in ("troop", "building"):
            n = max(1, int(c.get("count") or 1))
            r = float(c.get("summon_radius_milli") or 0) / math.cos(math.pi / (2 * n)) if n > 1 else 0.0
            for k in range(n):            # ponytail: the measured 3-body triangle; other counts use the same ring rule
                a = math.pi / 2 + 2 * math.pi * k / n
                bodies.append((key, x + r * math.cos(a), y + fwd * r * math.sin(a), -(int(p["land"]) * 8 + k + 1)))
            continue
        pr = c.get("projectile") or {}
        area = (c.get("spell") or {}).get("area_effect_object") or {}
        roll = pr.get("spawn_projectile") or {}
        if roll.get("projectile_range_milli"):                           # the Log
            if age < LOG_AIR_TICKS:
                shots.append((key, int(my_side), x, y - fwd * (pr["min_distance_milli"] - pr["speed"] * age), x, y, None))
            else:
                shots.append((key, int(my_side), x, y + fwd * roll["speed"] * (age - LOG_AIR_TICKS), x,
                              y + fwd * roll["projectile_range_milli"], None))
        elif pr.get("speed"):                                            # Rocket, Fireball: from my king tower
            d = math.hypot(x - kx, y - ky)
            f = min(1.0, pr["speed"] * age / d) if d else 1.0
            if f < 1.0:
                px, py = kx + (x - kx) * f, ky + (y - ky) * f
                shots.append((key, int(my_side), px, py, x, y, catalog_tti(key, px, py, x, y)))
        elif area.get("life_duration_ms"):                               # Tornado and other area spells
            ms = float(area["life_duration_ms"]) - 50.0 * age
            if ms > 0:
                areas.append((key, int(my_side), x, y, ms))
    return bodies, shots, areas
