"""L74 combo (owner 2026-10-17): an OPT-IN reward for OUR Rocket -- and the Tornado that set it up -- = the elixir value of the
enemy bodies the blast removes, net of the Rocket's cost, multiplied up when an enemy princess tower is caught in the same blast
as a real clump (scratchpad/gauntlet/L74/combo/RL_COMBO_REWARD.md). The owner's goal: the model learns the Rocket + Tornado combo by
itself, so the hard-coded rocket_tornado rule can go.

Two halves:
  SpellTracker (actor side, engine): royale_env._advance_to steps ONE tick at a time while one of the tracked side's Rockets is
    armed (royale_env act accepted it) or in flight, so the impact is read on exact ticks: the bodies inside the blast on the
    last tick the Rocket is seen, their hp one tick after it is gone (scenarios.impact's rule, L74/fastplays). Our Tornados are
    logged at every stop. -> ``events`` (plain dicts; e1_eval.SelfPlayMatch.result puts them under "spell").
  row_rewards (learner side, pure): events + the side's plays + its recorded row ticks -> one reward per traj row, on the rows
    that DECIDED the Rocket and its setup Tornado. rl_royale.collate adds it to r_step.
No tracker on the env (the default) = no extra engine step, no result key: byte-identical.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np

# rl_royale keys (``spell_value_reward: on`` + these; absent = the defaults). Elixir is the currency: w converts it to reward.
DEFAULTS = {"spell_value_w": 0.02,           # reward per elixir (win = +1): 6 elixir for nothing = -0.12
            "spell_value_dmg_w": 1.0,        # a body the blast damages but does not kill counts this x its hp share removed
            "spell_value_cost_w": 1.0,       # x the Rocket's cost, always charged (a princess hit floors the reward at 0)
            "spell_value_tower_bonus": 0.5,  # troop value x (1 + this) when a princess is in the blast with >= tower_min elixir
            "spell_value_tower_min": 7.0,    # ... of troops (elixir): above every lone card the eval rows caught (max 6.0)
            "spell_value_event_cap": 0.3,    # |one Rocket's reward| <= this
            "spell_value_match_cap": 0.5}    # |a match's summed spell reward| <= this (rl_royale's critic scale needs 1 + it)
# ``spell_value_lone: on`` (owner 10-18: "only rocket is used when it suffices"; absent / false = the 6 : 3 cost split, same hash):
# a combo's Tornado row earns w x ((V_combo - V_lone) - cost_w x Tornado cost) -- V_lone = what a LONE Rocket at its best blast
# point held on the same bodies where they stood at the Tornado's cast (lone_value) -- and -w x cost_w x Tornado cost when
# V_lone >= spell_value_lone_min (a lone Rocket already had the clump); the Rocket row keeps its whole event reward.
LONE_DEFAULTS = {"spell_value_lone_min": 9.0}   # the clump a lone Rocket must already hold: = LIVE_OPTIONS --rocket-value 9
CAST_TICKS = 20               # a Tornado first seen this long after its cast is that cast (normal stops: <= decide_every apart)
ROCKET_R_TILES = 2.0          # catalog Rocket radius (decision_options.rocket_radius_tiles)
TORNADO_R_TILES = 5.5         # catalog Tornado radius (decision_options.tornado_radius_tiles)
BODY_SLACK_TILES = 0.25       # a body counts when its edge is within the blast + this (scenarios.impact)
SETUP_TICKS = 40              # a setup Tornado was first seen at most this long before the impact (window 4-28 + a 10-tick stop)
ARM_TICKS = 12                # an armed Rocket that never shows up stops the single stepping after this
PLAY_MATCH_TICKS = 40         # a spell first seen this long after a play's landing is not that play
TILE = 18000                  # engine subtiles per tile (royale_env.SCALE x 1000)
KING_TOWER, PRINCESS_TOWER = 2, 3   # royalegym.protocol.EntityKind (the engine contract; tests check it where royalegym imports)
_FORM = re.compile(r"(_EV\d.*|Hero(_.*)?|_[Rr]ework.*|_kamikaze_form)$")   # evo / hero / rework unit names -> the base unit


@lru_cache(maxsize=None)
def body_value(unit: str, card: str) -> float:
    """Elixir value of one full-hp enemy body: its own unit (engine ``unit_types`` name; evo / hero / rework forms valued as the
    base unit; a child such as a Witch's Skeleton = the Skeletons card's 1/3) by decision_options.rocket_unit_table (card cost /
    bodies the card puts out), else its CARD's per-body value; 0 when neither is known (spells, towers, markers).
    ponytail: an unknown child of a one-body card is valued as the card's body (e.g. a Balloon's bomb, if hit); a unit table
    keyed by unit name is the upgrade if a census shows such bodies matter."""
    from pipeline import vocab
    from pipeline.body_identity import BODY_ALIASES
    from pipeline.decision_options import rocket_unit_table
    t = rocket_unit_table()
    b = _FORM.sub("", unit or "")
    k = vocab.engine_key(b) if b else None
    for key in (BODY_ALIASES.get(b), k, k and k + "s", vocab.engine_key(card or "")):
        if key in t:
            return float(t[key][0])
    return 0.0


def to_board(x: float, y: float, side: int) -> tuple:
    """Engine subtiles -> board tiles in ``side``'s frame (me at the bottom: y >= 16 is my half), as fastplays/scenarios.to_board."""
    X, Y = x / 18.0, y / 18.0
    if side == 1:
        X, Y = 18000 - X, 32000 - Y
    return round(X / 1000.0, 2), round(32.0 - Y / 1000.0, 2)


class SpellTracker:
    """One match, one side: its Rocket impacts (+ the setup Tornado) as ``events``. Holds no env reference (search_s0 forks
    deep-copy it with the env's dict). ``env`` is read once, for card ids / costs / unit names."""

    def __init__(self, env, side: int):
        self.side = int(side)
        self.rocket, self.tornado = env.ids.get("Rocket"), env.ids.get("Tornado")
        self.cost = {c.card_id: int(c.elixir) for c in env.core.cards()}
        ut = getattr(env.core, "unit_types", None)
        self.units = (ut() if ut else None) or []
        self.names = dict(env.names)
        self.king, self.princess = KING_TOWER, PRINCESS_TOWER
        self.armed = None             # tick of an accepted Rocket deploy not seen yet
        self.flying = {}              # (aim_x, aim_y) subtiles -> first tick seen
        self.last = None              # the previous tick's state while busy
        self.pending = []             # [(event, bodies, towers)] waiting for the next tick's hp
        self.tornados = []            # [first, last, x, y, cast bodies or None] subtiles
        self.casts = []               # [(tick, {uid: [x, y, reach]})]: enemy bodies (board tiles) when my Tornado was cast
        self.now = None               # the last observed state = the one a play at this tick is cast on (no engine call)
        self.events = []

    def __getstate__(self):           # search_s0 forks deep-copy the tracker: never the engine state reference (a fork's
        return {**self.__dict__, "now": None}   # play lands after an _advance_to, which observes again)

    def busy(self, tick: int) -> bool:
        """True = royale_env steps one tick (a Rocket armed, in flight, or an impact waiting for its hp)."""
        if self.armed is not None and tick - self.armed > ARM_TICKS:
            self.armed = None
        return bool(self.flying or self.pending or self.armed is not None)

    def played(self, side: int, card_id: int, tick: int) -> None:
        if side == self.side and card_id == self.rocket:
            self.armed = int(tick)
        elif side == self.side and card_id == self.tornado and self.now is not None and int(self.now.tick) == int(tick):
            self.casts.append((int(tick), self._cast_bodies(self.now)))   # before the pull moved anything

    def _cast_bodies(self, st) -> dict:
        """Enemy bodies on ``st`` -> {uid: [x, y, reach]}: board tiles in my frame, reach = the distance from a blast centre
        within which the ENGINE's area hit reaches the body: Rocket radius + its collision radius (RoyaleSim spell.rs
        in_range_edge, AoeHitTest::EdgeInclusive). Not _inside's + slack: that is a measuring superset (the hp drop decides
        there), here it would only widen the lone Rocket (10-18 hand check: +0.25 per body). ponytail: a building is a disc
        here, the engine's square (in_square) reaches its corners up to 1.41 x its radius."""
        return {e.uid: [*to_board(e.x, e.y, self.side), round(ROCKET_R_TILES + e.radius / TILE, 4)]
                for e in st.entities if e.team != self.side and e.hp > 0 and int(e.kind) not in (self.king, self.princess)}

    def observe(self, st) -> None:
        """After every engine step: resolve waiting impacts, log my Tornados, find my Rockets that landed in this step."""
        t = int(st.tick)
        for ev, bodies, towers in self.pending:
            self._resolve(ev, bodies, towers, st)
        self.pending = []
        now = set()
        for s in st.spells:
            if s.team != self.side:
                continue
            if s.card_id == self.rocket:
                now.add((s.aim_x, s.aim_y))
            elif s.card_id == self.tornado:
                rec = next((r for r in self.tornados if (r[2], r[3]) == (s.x, s.y) and t - r[1] <= 30), None)
                if rec is None:
                    cast = [c for c in self.casts if 0 <= t - c[0] <= CAST_TICKS]     # the latest cast before it
                    self.tornados.append([t, t, s.x, s.y, cast[-1][1] if cast else None])
                    self.casts = [c for c in self.casts if c not in cast[-1:]]
                else:
                    rec[1] = t
        self.tornados = [r for r in self.tornados if t - r[1] <= 2 * SETUP_TICKS]
        self.casts = [c for c in self.casts if t - c[0] <= CAST_TICKS]
        for k in now - set(self.flying):
            self.flying[k] = t
            self.armed = None
        for k in [k for k in self.flying if k not in now]:            # gone during this step: the impact
            prev = self.last if self.last is not None else st
            ev = {"tick": t, "seen": self.flying.pop(k), "aim": to_board(k[0], k[1], self.side),
                  "cost": self.cost.get(self.rocket, 6)}
            self.pending.append((ev, *self._inside(prev, k)))
        if st.game_over:                                              # no next tick: the final state is the after
            for ev, bodies, towers in self.pending:
                self._resolve(ev, bodies, towers, st)
            self.pending = []
        self.last = st if (self.flying or self.armed is not None) else None
        self.now = st

    def _inside(self, st, aim) -> tuple:
        """Enemy bodies / crown towers inside the blast at ``aim`` on state ``st`` -> ([(uid, hp, max_hp, value, name)],
        [(uid, kind, hp)])."""
        ax, ay = aim
        bodies, towers = [], []
        for e in st.entities:
            if e.team == self.side or e.hp <= 0:
                continue
            d = math.hypot(e.x - ax, e.y - ay) / TILE
            if int(e.kind) in (self.king, self.princess):
                if d <= ROCKET_R_TILES + e.radius / TILE:
                    towers.append((e.uid, int(e.kind), int(e.hp)))
            elif d <= ROCKET_R_TILES + e.radius / TILE + BODY_SLACK_TILES:
                ut = e.unit_type if 0 <= getattr(e, "unit_type", -1) < len(self.units) else -1
                unit = self.units[ut] if ut >= 0 else ""
                card = self.names.get(e.card_id, "")
                bodies.append((e.uid, int(e.hp), max(int(e.max_hp), 1), body_value(unit, card), unit or card))
        return bodies, towers

    def _resolve(self, ev: dict, bodies: list, towers: list, st) -> None:
        hp = {e.uid: int(e.hp) for e in st.entities}
        kill = dmg = 0.0
        hit, uids = [], []
        for uid, h0, mx, v, name in bodies:
            h1 = max(hp.get(uid, 0), 0)
            if h1 >= h0:
                continue
            f = min((h0 - h1) / mx, 1.0)                      # an engine overheal (h0 > max) never counts > the body
            if h1 == 0:
                kill += v * f
            else:
                dmg += v * f
            hit.append([name, round(v, 3), round(f, 3), h1 == 0])
            uids.append(uid)
        down = [(kind, h0 - max(hp.get(uid, 0), 0)) for uid, kind, h0 in towers if max(hp.get(uid, 0), 0) < h0]
        tor = self._setup(ev)
        if tor is not None and tor.get("cast") is not None:  # spell_value_lone: each hit body where it stood at the cast
            tor["cast"] = [tor["cast"].get(u) for u in uids]  # (None = not on the board then, e.g. spawned during the pull)
        ev.update(kill=round(kill, 4), dmg=round(dmg, 4), bodies=hit,
                  princess=any(k == self.princess for k, _ in down), king=any(k == self.king for k, _ in down),
                  tower_dmg=int(sum(d for _, d in down)), tornado=tor)
        self.events.append(ev)

    def _setup(self, ev: dict):
        """My Tornado that set this Rocket up: first seen <= SETUP_TICKS before the impact, centre within its radius of the
        aim (the latest such) -> {"seen", "aim", "cost"} (+ "cast": its cast's enemy bodies when that was recorded) or None."""
        ax, ay = ev["aim"]
        best = None
        for first, last, x, y, cast in self.tornados:
            bx, by = to_board(x, y, self.side)
            if 0 <= ev["tick"] - first <= SETUP_TICKS and math.hypot(bx - ax, by - ay) <= TORNADO_R_TILES:
                if best is None or first > best[0]:
                    best = (first, (bx, by), cast)
        if best is None:
            return None
        out = {"seen": best[0], "aim": best[1], "cost": self.cost.get(self.tornado, 3)}
        return out if best[2] is None else {**out, "cast": best[2]}


# ---------------------------------------------------------------------------------------------------- learner side (pure)
def event_reward(ev: dict, p: dict) -> tuple:
    """One Rocket event -> (troop value V, gross G, reward) in elixir / elixir / reward units:
    V = elixir of the bodies it killed (their hp share at impact, <= 1) + dmg_w x that of the bodies it only damaged;
    G = V x (1 + tower_bonus) when an enemy princess was in the blast and V >= tower_min (a real clump), else V;
    reward = w x (G - cost_w x Rocket cost), floored at 0 when an enemy princess tower was hit (tower Rocket-cycling is never
    charged, but the clump must beat the Rocket's cost to earn), clipped to +- event_cap."""
    v = float(ev["kill"]) + p["spell_value_dmg_w"] * float(ev["dmg"])
    g = v * (1.0 + p["spell_value_tower_bonus"]) if ev["princess"] and v >= p["spell_value_tower_min"] else v
    r = p["spell_value_w"] * (g - p["spell_value_cost_w"] * float(ev["cost"]))
    if ev["princess"]:
        r = max(r, 0.0)
    cap = p["spell_value_event_cap"]
    return v, g, float(np.clip(r, -cap, cap))


def _crossings(a, b) -> list:
    """The 0-2 points where two circles (x, y, r, ...) cross."""
    (x0, y0, r0), (x1, y1, r1) = a[:3], b[:3]
    d = math.hypot(x1 - x0, y1 - y0)
    if d == 0 or d > r0 + r1 or d < abs(r0 - r1):
        return []
    a_ = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(max(r0 * r0 - a_ * a_, 0.0))
    mx, my, ux, uy = x0 + a_ * (x1 - x0) / d, y0 + a_ * (y1 - y0) / d, (x1 - x0) / d, (y1 - y0) / d
    return [(mx + h * uy, my - h * ux), (mx - h * uy, my + h * ux)]


def lone_value(ev: dict, p: dict):
    """spell_value_lone's counterfactual -> V_lone (elixir) or None (no setup Tornado, or its cast was not recorded): the troop
    value a LONE Rocket would have held at its best blast point on this event's hit bodies where they stood when the Tornado
    was cast (before any pull). Each body counts what the combo's blast took from it (value x hp share; damaged-only ones
    x dmg_w, as event_reward), inside a blast when its distance from the centre <= its reach (Rocket radius + its collision
    radius: the engine's own area-hit rule, _cast_bodies). The best point is exact (an optimal region's corner is a reach
    circle's centre or two circles' crossing), anywhere on the board, i.e. an ORACLE-aimed lone Rocket. Capped at V_combo.
    ponytail: the SAME bodies only (one the combo missed is not counted), static (no walk during a lone Rocket's flight) and
    oracle-aimed, so V_lone is an upper bound for a real lone Rocket: the Tornado's credit for HOLDING a clump that a flying
    Rocket would see walk out is not counted, only for gathering it (L74/combo/RL_COMBO_REWARD.md 10-18); a body spawned after
    the cast counts 0 (e.g. a Witch's Skeletons). A forked engine replay of the real lone Rocket is the upgrade."""
    tor = ev.get("tornado")
    cast = tor.get("cast") if tor else None
    if cast is None:
        return None
    dw = p["spell_value_dmg_w"]
    pts = [(c[0], c[1], c[2], b[1] * b[2] * (1.0 if b[3] else dw)) for b, c in zip(ev.get("bodies") or (), cast) if c is not None]
    cand = [q[:2] for q in pts] + [x for i, a in enumerate(pts) for b in pts[i + 1:] for x in _crossings(a, b)]
    best = max((sum(w for x, y, r, w in pts if math.hypot(cx - x, cy - y) <= r + 1e-6) for cx, cy in cand), default=0.0)
    return min(best, float(ev["kill"]) + dw * float(ev["dmg"]))


def tornado_credit(ev: dict, v: float, p: dict) -> tuple:
    """spell_value_lone: one combo's Tornado row -> (reward, V_lone); (0.0, None) when V_lone is unknown. ``v`` = the event's
    troop value V_combo (event_reward's V: no princess bonus -- the pull gathers troops). reward = w x ((V_combo - V_lone) -
    cost_w x Tornado cost), or w x (-cost_w x Tornado cost) when V_lone >= spell_value_lone_min (a lone Rocket already held
    the clump: the Tornado was not needed), clipped to +- event_cap."""
    lone = lone_value(ev, p)
    if lone is None:
        return 0.0, None
    gain = 0.0 if lone + 1e-9 >= p["spell_value_lone_min"] else v - lone
    r = p["spell_value_w"] * (gain - p["spell_value_cost_w"] * float(ev["tornado"]["cost"]))
    cap = p["spell_value_event_cap"]
    return float(np.clip(r, -cap, cap)), round(lone, 4)


def _slug(name) -> str:
    return re.sub(r"[^a-z]", "", str(name).split("@")[0].lower())


def _row_of(seen: int, card: str, plays: list, row: dict):
    """The traj row that decided the play of ``card`` this spell (first seen at ``seen``) came from: the latest ACCEPTED play
    of it landing at or before ``seen`` (within PLAY_MATCH_TICKS) -> its decision tick's row index, or None."""
    best = None
    for q in plays:
        land = int(q.get("land_tick", q["tick"]))
        if q["accepted"] and _slug(q["card"]) == card and seen - PLAY_MATCH_TICKS <= land <= seen:
            best = q if best is None or land >= int(best.get("land_tick", best["tick"])) else best
    return None if best is None else row.get(int(best["tick"]))


def row_rewards(events, plays, row_ticks, p: dict) -> dict:
    """One match: its Rocket events (SpellTracker.events, time order), its side's ``plays`` (e1_eval play records: tick, card,
    accepted, land_tick) and the decision tick of every traj row -> {"r": reward per row, "events": per-event rows}.
    Credit: each event's reward lands on the row that DECIDED the Rocket; with a setup Tornado it is split by elixir cost
    (6 : 3) with the row that decided the Tornado -- both choices made the combo, a miss charges both. ``spell_value_lone``
    on instead: the Rocket row keeps the whole event reward (its own marginal: the Tornado was played) and the Tornado row
    gets tornado_credit (ITS marginal over a lone Rocket). Clipped per event (event_cap), then the match's running sum is kept
    within +- match_cap (later events clipped; the Rocket part before the Tornado part)."""
    ticks = np.asarray(row_ticks, dtype=np.int64)
    row = {int(t): i for i, t in enumerate(ticks)}
    r = np.zeros(len(ticks))
    total, out = 0.0, []
    m = p["spell_value_match_cap"]
    lone_on = bool(p.get("spell_value_lone"))
    for ev in sorted(events or (), key=lambda e: e["tick"]):
        v, g, e = event_reward(ev, p)
        e = float(np.clip(total + e, -m, m) - total)
        total += e
        ir = _row_of(int(ev["seen"]), "rocket", plays, row)
        tor = ev.get("tornado")
        it = _row_of(int(tor["seen"]), "tornado", plays, row) if tor else None
        if lone_on:
            te, vl = tornado_credit(ev, v, p) if tor else (0.0, None)
            te = float(np.clip(total + te, -m, m) - total)
            total += te
            if ir is not None:
                r[ir] += e
            if it is not None:
                r[it] += te
        elif ir is not None and it is not None:
            share = float(tor["cost"]) / (float(ev["cost"]) + float(tor["cost"]))
            r[ir] += e * (1.0 - share)
            r[it] += e * share
        elif ir is not None:
            r[ir] += e
        out.append({"tick": int(ev["tick"]), "value": round(v, 3), "gross": round(g, 3), "reward": round(e, 4),
                    "row": ir, "tornado_row": it, "combo": tor is not None, "princess": bool(ev["princess"]),
                    **({"lone": vl, "tornado_reward": round(te, 4)} if lone_on else {})})
    return {"r": r, "events": out}


def match_summary(events, p: dict = None) -> dict:
    """One match's spell numbers (eval rows, train monitors): Rockets that landed, combos, troop value / gross / reward sums,
    misses (V < 2 elixir, no princess), cheap-swarm hits (every body hit worth < 1 elixir, >= 3 hit), princess hits, combos
    on my half (aim y >= 16) and near my king (aim within 7 tiles of (9, 28.65)). ``spell_value_lone`` on: + combos whose
    V_lone is known / already >= spell_value_lone_min (a Tornado a lone Rocket did not need), the elixir the pulls added
    (V_combo - V_lone) and the Tornado rows' reward (also in ``reward``)."""
    p = {**DEFAULTS, **LONE_DEFAULTS, **(p or {})}
    lone_on = bool(p.get("spell_value_lone"))
    s = {k: 0 for k in ("rockets", "combos", "misses", "swarm", "princess", "king", "my_half", "near_my_king",
                        "combo_my_half")}
    s.update(value=0.0, gross=0.0, reward=0.0, bodies=0)
    if lone_on:
        s.update(lone_known=0, lone_suffices=0, tornado_gain=0.0, tornado_reward=0.0)
    for ev in events or ():
        v, g, e = event_reward(ev, p)
        if lone_on and ev.get("tornado") is not None:
            te, vl = tornado_credit(ev, v, p)
            s["lone_known"] += vl is not None
            s["lone_suffices"] += vl is not None and vl + 1e-9 >= p["spell_value_lone_min"]
            s["tornado_gain"] += 0.0 if vl is None else v - vl
            s["tornado_reward"] += te
            e += te
        b = ev.get("bodies") or []
        mine = ev["aim"][1] >= 16.0
        s["rockets"] += 1
        s["combos"] += ev.get("tornado") is not None
        s["misses"] += v < 2.0 and not ev["princess"]
        s["swarm"] += len(b) >= 3 and all(x[1] < 1.0 for x in b)
        s["princess"] += bool(ev["princess"])
        s["king"] += bool(ev["king"])
        s["my_half"] += mine
        s["near_my_king"] += math.hypot(ev["aim"][0] - 9.0, ev["aim"][1] - 28.65) <= 7.0
        s["combo_my_half"] += mine and ev.get("tornado") is not None
        s["value"] += v
        s["gross"] += g
        s["reward"] += e
        s["bodies"] += len(b)
    m = p["spell_value_match_cap"]
    s["reward"] = float(np.clip(s["reward"], -m, m))
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}


def batch_stats(summaries: list, rewarded: list) -> dict:
    """Per-update training monitors over the batch's matches: ``summaries`` (match_summary) and ``rewarded`` (the summed row
    reward each match actually received; 0 under w = 0). ``dominates`` = mean |match spell reward| / 1 (the win reward):
    above ~0.25 the spell term is louder than a quarter of winning."""
    n = max(len(summaries), 1)
    tot = {k: sum(s[k] for s in summaries) for k in (summaries[0] if summaries else ())}
    rw = np.asarray(rewarded, dtype=np.float64)
    return {"matches": len(summaries), **{f"{k}_per_match": round(v / n, 4) for k, v in tot.items()},
            "dominates": float(np.abs(rw).mean()) if len(rw) else 0.0,
            "reward_min": float(rw.min()) if len(rw) else 0.0, "reward_max": float(rw.max()) if len(rw) else 0.0}
