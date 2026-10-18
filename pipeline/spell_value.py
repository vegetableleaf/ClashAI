"""L74 combo (owner 2026-10-17): an OPT-IN reward for OUR Rocket -- and the Tornado that set it up -- = the elixir value of the
enemy bodies the blast removes, net of the Rocket's cost, with a bonus when an enemy princess tower is caught in the same blast
as a clump (scratchpad/gauntlet/L74/combo/RL_COMBO_REWARD.md). The owner's goal: the model learns the Rocket + Tornado combo by
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
            "spell_value_dmg_w": 0.5,        # a body the blast damages but does not kill counts this share of its hp removed
            "spell_value_cost_w": 1.0,       # x the Rocket's cost, charged unless an enemy princess tower is in the blast
            "spell_value_tower_bonus": 0.5,  # troop value x (1 + this) when a princess is in the blast with >= tower_min elixir
            "spell_value_tower_min": 4.0,    # ... of troops (elixir), so a tower chip with one Skeleton earns no bonus
            "spell_value_event_cap": 0.3,    # |one Rocket's reward| <= this
            "spell_value_match_cap": 0.5}    # |a match's summed spell reward| <= this (rl_royale's critic scale needs 1 + it)
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
        self.tornados = []            # [first, last, x, y] subtiles
        self.events = []

    def busy(self, tick: int) -> bool:
        """True = royale_env steps one tick (a Rocket armed, in flight, or an impact waiting for its hp)."""
        if self.armed is not None and tick - self.armed > ARM_TICKS:
            self.armed = None
        return bool(self.flying or self.pending or self.armed is not None)

    def played(self, side: int, card_id: int, tick: int) -> None:
        if side == self.side and card_id == self.rocket:
            self.armed = int(tick)

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
                    self.tornados.append([t, t, s.x, s.y])
                else:
                    rec[1] = t
        self.tornados = [r for r in self.tornados if t - r[1] <= 2 * SETUP_TICKS]
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
        hit = []
        for uid, h0, mx, v, name in bodies:
            h1 = max(hp.get(uid, 0), 0)
            if h1 >= h0:
                continue
            f = (h0 - h1) / mx
            if h1 == 0:
                kill += v * f
            else:
                dmg += v * f
            hit.append([name, round(v, 3), round(f, 3), h1 == 0])
        down = [(kind, h0 - max(hp.get(uid, 0), 0)) for uid, kind, h0 in towers if max(hp.get(uid, 0), 0) < h0]
        ev.update(kill=round(kill, 4), dmg=round(dmg, 4), bodies=hit,
                  princess=any(k == self.princess for k, _ in down), king=any(k == self.king for k, _ in down),
                  tower_dmg=int(sum(d for _, d in down)), tornado=self._setup(ev))
        self.events.append(ev)

    def _setup(self, ev: dict):
        """My Tornado that set this Rocket up: first seen <= SETUP_TICKS before the impact, centre within its radius of the
        aim (the latest such) -> {"seen", "aim", "cost"} or None."""
        ax, ay = ev["aim"]
        best = None
        for first, last, x, y in self.tornados:
            bx, by = to_board(x, y, self.side)
            if 0 <= ev["tick"] - first <= SETUP_TICKS and math.hypot(bx - ax, by - ay) <= TORNADO_R_TILES:
                if best is None or first > best[0]:
                    best = (first, (bx, by))
        return None if best is None else {"seen": best[0], "aim": best[1], "cost": self.cost.get(self.tornado, 3)}


# ---------------------------------------------------------------------------------------------------- learner side (pure)
def event_reward(ev: dict, p: dict) -> tuple:
    """One Rocket event -> (troop value V, gross G, reward) in elixir / elixir / reward units:
    V = elixir of the bodies it killed (their hp share at impact) + dmg_w x that of the bodies it only damaged;
    G = V x (1 + tower_bonus) when an enemy princess was in the blast and V >= tower_min, else V;
    reward = w x (G - cost_w x Rocket cost), the cost charged only when NO enemy princess tower was hit (a tower Rocket stays
    the win reward's business: neutral, as today), clipped to +- event_cap."""
    v = float(ev["kill"]) + p["spell_value_dmg_w"] * float(ev["dmg"])
    g = v * (1.0 + p["spell_value_tower_bonus"]) if ev["princess"] and v >= p["spell_value_tower_min"] else v
    cost = 0.0 if ev["princess"] else p["spell_value_cost_w"] * float(ev["cost"])
    cap = p["spell_value_event_cap"]
    return v, g, float(np.clip(p["spell_value_w"] * (g - cost), -cap, cap))


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
    (6 : 3) with the row that decided the Tornado -- both choices made the combo, a miss charges both. Clipped per event
    (event_cap), then the match's running sum is kept within +- match_cap (later events clipped)."""
    ticks = np.asarray(row_ticks, dtype=np.int64)
    row = {int(t): i for i, t in enumerate(ticks)}
    r = np.zeros(len(ticks))
    total, out = 0.0, []
    m = p["spell_value_match_cap"]
    for ev in sorted(events or (), key=lambda e: e["tick"]):
        v, g, e = event_reward(ev, p)
        e = float(np.clip(total + e, -m, m) - total)
        total += e
        ir = _row_of(int(ev["seen"]), "rocket", plays, row)
        tor = ev.get("tornado")
        it = _row_of(int(tor["seen"]), "tornado", plays, row) if tor else None
        if ir is not None and it is not None:
            share = float(tor["cost"]) / (float(ev["cost"]) + float(tor["cost"]))
            r[ir] += e * (1.0 - share)
            r[it] += e * share
        elif ir is not None:
            r[ir] += e
        out.append({"tick": int(ev["tick"]), "value": round(v, 3), "gross": round(g, 3), "reward": round(e, 4),
                    "row": ir, "tornado_row": it, "combo": tor is not None, "princess": bool(ev["princess"])})
    return {"r": r, "events": out}


def match_summary(events, p: dict = None) -> dict:
    """One match's spell numbers (eval rows, train monitors): Rockets that landed, combos, troop value / gross / reward sums,
    misses (V < 2 elixir, no princess), cheap-swarm hits (every body hit worth < 1 elixir, >= 3 hit), princess hits, combos
    on my half (aim y >= 16) and near my king (aim within 7 tiles of (9, 28.65))."""
    p = {**DEFAULTS, **(p or {})}
    s = {k: 0 for k in ("rockets", "combos", "misses", "swarm", "princess", "king", "my_half", "near_my_king",
                        "combo_my_half")}
    s.update(value=0.0, gross=0.0, reward=0.0, bodies=0)
    for ev in events or ():
        v, g, e = event_reward(ev, p)
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
