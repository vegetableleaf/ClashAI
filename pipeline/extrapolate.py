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
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional
from collections import Counter

from pipeline.opp_elixir_count import MAX_ELIXIR, regen_between

BOARD_X, BOARD_Y = 18000.0, 32000.0

# predict_drops: Skeleton Barrel (base / evo card id; the balloon AND its skeletons carry it, told apart by max_hp)
SB_CARDS = {26000056: 532.0, 13000056: 665.0}        # card id -> balloon max_hp at level 11
BALLOON_MIN_HP = 300                                  # balloon 532..967; its skeletons 81..130
CHILD_HP11, N_CHILD = 81.0, 7                         # skeleton max_hp at level 11, count
# Live-measured (30 exact drops, 210 children, 2-tick frames; fix/age_profile.py): the 7 spawn near the drop point and
# jump out to a ring in ~3 ticks -- median radius by age 0 / 1 / 2 / >= 3 ticks since spawn, millitiles; body kind 14
# (deploying) until age 9, then 15. (The audit's hand-placed counterfactual used a 1.3-tile ring at every age.)
CHILD_RING, CHILD_DEPLOY_TICKS = (250.0, 630.0, 960.0, 1460.0), 9
DROP_DELAY, DROP_TTL = 12, 40                         # skeletons appear T + 12 (T = first absent tick); pending kept to T + 40


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


def _child_hp(balloon: Mapping[str, Any]) -> float:
    """Skeleton max_hp at the balloon's card level: CR scales +10% per level (balloon 532/586/642/705/773 -> skeleton
    81/89/98/108/119, live-measured; the evo balloon starts at 665 but drops the same 81-hp skeletons)."""
    base = SB_CARDS.get(int(balloon.get("card_id", -1)), SB_CARDS[26000056])
    level = round(math.log(float(balloon["max_hp"]) / base) / math.log(1.1))
    return float(round(CHILD_HP11 * 1.1 ** max(level, 0)))


class DropTracker:
    """Observed-only memory of enemy Skeleton Barrel balloons that left the board (see the module docstring).

    ``observe(obs, my_side)`` once per observation in ascending tick order (a smaller tick = a new match: reset);
    ``pending`` is what ``extrapolate(drops=...)`` reads. A pending drop ends when its real skeletons are observed
    (new Skeleton Barrel bodies below balloon hp within 4.5 tiles), when the same balloon reappears (a one-frame
    flicker, not a death), or after T + 40."""

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
            for k, e in last.items():
                if _is_balloon(e) and int(e["side"]) != int(my_side) and (k not in ents or _sig(ents[k]) != _sig(e)):
                    self.pending.append(dict(t0=tick, x=float(e["x"]), y=float(e["y"]), parent=dict(e)))
            fresh = [e for k, e in ents.items() if k not in last and _is_sb(e) and not _is_balloon(e)]
            self.pending = [d for d in self.pending if tick <= d["t0"] + DROP_TTL
                            and not (d["t0"] < tick and any(
                                int(f["side"]) == int(d["parent"]["side"]) and
                                math.hypot(f["x"] - d["x"], f["y"] - d["y"]) <= 4500 for f in fresh))
                            and not (d["t0"] < tick and _eid(d["parent"]) in ents
                                     and _sig(ents[_eid(d["parent"])]) == _sig(d["parent"]))]
        self._last, self._tick = ents, tick


def predicted_children(d: Mapping[str, Any], age: int) -> list[dict]:
    """The 7 skeleton bodies of one pending drop ``age`` ticks after they spawn: the parent's own entity dict (so the
    reader frame and the engine ``observe()`` dict both accept them) re-positioned on the ring with the children's
    hp, deploying kind while fresh, and a synthetic id."""
    p, hp = d["parent"], _child_hp(d["parent"])
    r, kind = CHILD_RING[min(max(age, 0), len(CHILD_RING) - 1)], 14 if age < CHILD_DEPLOY_TICKS else 15
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


def extrapolate(obs: Mapping[str, Any], prev: Optional[Mapping[str, Any]], h: int, my_side: int, *,
                public_objects=None, previous_objects=None, object_gap_ticks=0, drops=None) -> dict:
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
    ents = []
    for e in obs.get("entities") or ():
        e = dict(e)
        p = before.get(_eid(e)) if int(e.get("card_id", -1)) >= 0 else None
        if p is not None and p.get("side") == e.get("side") and p.get("card_id") == e.get("card_id"):
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
