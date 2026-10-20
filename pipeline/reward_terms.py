"""L74 W6 (10-20; plan1019 TUESDAY D / I / I2, DOCTRINE_MEASURED 4 R1, memory reward-redirect-to-king): three OPT-IN crown
reward terms for rl_royale, ONE config key each (one change per arm), plus the eval crown log (search_s0 --crown-log).
Off (absent / null / false) = no tracker, no extra engine call, the same rows, behaviour and config hash.

    lead_protect: on              R1: -lead_protect_w (win = +1; default 0.2 = the SIM's under-pricing of a given-back lead:
                                  1-0 -> 1-1 drops P(win) 0.93 -> 0.54 in the SIM vs 0.87 -> 0.27 live), once, on the last kept
                                  row at or before the tick OUR princess falls while we lead exactly 1-0.
    princess_redirect: penalty    owner 10-19: while BOTH our princesses stand, -princess_redirect_w per princess tower of HP
                                  they lose (hp / max_hp; the hit that fells the first one counts, nothing after it), on the
                                  kept row the damage follows. King damage is never charged, so moving an attacker onto the
                                  king pays. No end-of-match refund: it CHANGES the optimum, deliberately (as R1 does).
    princess_redirect: potential  the same quantity as a potential Phi = -w x lost, Phi = 0 at the match end (rl_royale's
                                  residual critic, B["phi"]). Policy-INVARIANT by construction (gae_batch's docstring: with a
                                  converged critic A = the unshaped advantage), so it can speed credit assignment but never
                                  make the redirect pay. The literal 10-20 ticket; the arm yaml uses penalty.
    tornado_king_penalty: on      owner 10-19 I2: each of OUR Tornados cast while >= 1 own princess is down costs
                                  tornado_king_w x the NET displacement (tiles) of the enemy bodies it caught TOWARD our king,
                                  floored at 0 and capped, on the row that decided it. A Tornado that holds its bodies in place
                                  or pulls them away costs nothing.

CrownTracker (actor side): ``observe`` reads the engine state at every SelfPlayMatch.due() stop (e1_eval). It never steps or
changes the engine, so a match with the tracker plays exactly as one without it. -> ``result()`` (plain JSON types):
    lost      [[tick, L]] change points of L = own princess HP lost (princess-tower units) while both stand, frozen at the
              first own fall (which counts the fallen tower whole)
    falls     [{tick, who: own | foe, before: [own crowns, foe crowns] at the previous stop}] for every princess fall
    tornados  [{seen, end, down (own princesses down at the cast), toward (tiles), n (bodies caught)}]
    rockets   [{seen, aim (board tiles, my frame), tower (aim within 3 tiles of an enemy princess / king slot)}]
    end       {tick, king, princess, foe_princess (hp fractions), crowns} at the last stop
The learner side (``row_terms``) is pure: the record + the side's plays + the KEPT rows' decision ticks -> per-row reward.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from pipeline.spell_value import KING_TOWER, PRINCESS_TOWER, TILE, TORNADO_R_TILES, _row_of, to_board

TERMS = {"lead_protect": "lead_protect_w", "princess_redirect": "princess_redirect_w",
         "tornado_king_penalty": "tornado_king_w"}                     # switch -> its weight key (rl_royale CROWN_KEYS)
DEFAULTS = {"lead_protect_w": 0.2,            # x the win reward, once per match (DOCTRINE_MEASURED 4 R1)
            "princess_redirect_w": 0.2,       # per princess tower of HP lost while both stand: a felled first princess
            #                                   costs <= 0.2 on top of the terminal reward; |sum| < 2 w per match
            "tornado_king_w": 0.01}           # per tile of net pull toward our king (3 bodies x 3 tiles = 0.09; spell_value
#                                               prices elixir at 0.02, so a Tornado's 3 elixir = 0.06)
REDIRECT_MODES = ("penalty", "potential")
TORNADO_EVENT_CAP, TORNADO_MATCH_CAP = 0.15, 0.3   # ponytail: fixed caps, a config key if an arm needs another
TOWARD_MIN_TILES = 1.0          # eval slice: a Tornado "to the king" moved its bodies >= this net toward our king
TOWER_AIM_TILES = 3.0           # doctrine (habits/hablib.rocket_uses): a tower Rocket's aim is this close to a slot
ENEMY_SLOTS = ((3.5, 6.5), (14.5, 6.5), (9.0, 3.0))   # enemy princess L / R and king, board tiles, my frame
TRACK_TICKS = 30                # SpellTracker's rule: a spell seen again at the same point within this is the same cast


def bound(p: dict) -> float:
    """max |summed reward| (or |Phi|) per match of the terms on in ``p`` (crown_cfg's dict): lead w (crowns never fall, so
    1-0 -> 1-1 happens at most once), redirect 2 w (< 2 princess towers of HP before the first falls), Tornado its cap."""
    return (float(p.get("lead_protect_w", 0.0)) * bool(p.get("lead_protect"))
            + 2.0 * float(p.get("princess_redirect_w", 0.0)) * bool(p.get("princess_redirect"))
            + TORNADO_MATCH_CAP * bool(p.get("tornado_king_penalty")))


class CrownTracker:
    """One match, one side (rl_royale crown terms / search_s0 --crown-log). Holds no env reference after __init__."""

    def __init__(self, env, side: int):
        self.side = int(side)
        self.tornado, self.rocket = env.ids.get("Tornado"), env.ids.get("Rocket")
        self.pr = self.fpr = None          # own / foe princess uids (first stop: the match start, all towers stand)
        self.alive = self.crowns = None    # at the previous stop
        self.prev = None                   # enemy non-tower bodies at the previous stop: uid -> (x, y, radius) subtiles
        self.king = None                   # our king's (x, y) subtiles
        self.L, self.frozen = 0.0, False
        self.lost, self.falls, self.tornados, self.rockets = [], [], [], []
        self.active = []                   # open Tornados
        self.rk = {}                       # Rocket aim (subtiles) -> last tick seen
        self.end = None

    def _dk(self, b) -> float:
        return 0.0 if self.king is None else math.hypot(b[0] - self.king[0], b[1] - self.king[1]) / TILE

    @staticmethod
    def _in(b, xy) -> bool:
        return math.hypot(b[0] - xy[0], b[1] - xy[1]) <= TORNADO_R_TILES * TILE + b[2]

    def observe(self, st) -> None:
        t, me = int(st.tick), self.side
        tw, bodies = {}, {}
        for e in st.entities:
            k = int(e.kind)
            if k in (KING_TOWER, PRINCESS_TOWER):
                tw[e.uid] = (int(e.team), k, max(0.0, float(e.hp)) / max(float(e.max_hp), 1.0), e.x, e.y)
            elif int(e.team) != me and e.hp > 0:
                bodies[e.uid] = (e.x, e.y, e.radius)
        if self.pr is None:
            self.pr = sorted(u for u, v in tw.items() if v[0] == me and v[1] == PRINCESS_TOWER)
            self.fpr = sorted(u for u, v in tw.items() if v[0] != me and v[1] == PRINCESS_TOWER)
            if len(self.pr) != 2 or len(self.fpr) != 2:
                raise ValueError(f"CrownTracker: first stop (tick {t}) shows {len(self.pr)} / {len(self.fpr)} princesses")
        king = next((v for v in tw.values() if v[0] == me and v[1] == KING_TOWER), None)
        if king is not None:
            self.king = (king[3], king[4])
        own = [tw[u][2] if u in tw else 0.0 for u in self.pr]          # a tower gone from the list = destroyed
        foe = [tw[u][2] if u in tw else 0.0 for u in self.fpr]
        alive = dict(zip(self.pr + self.fpr, [f > 0 for f in own + foe]))
        crowns = [int(st.players[me].crowns), int(st.players[1 - me].crowns)]
        if self.alive is not None:
            for u in self.pr + self.fpr:
                if self.alive[u] and not alive[u]:
                    self.falls.append({"tick": t, "who": "own" if u in self.pr else "foe", "before": list(self.crowns)})
        if not self.frozen:
            L = round(sum(1.0 - f for f in own), 6)
            if L != self.L:
                self.L = L
                self.lost.append([t, L])
            self.frozen = not all(alive[u] for u in self.pr)
        self._tornados(st, t, bodies, sum(not alive[u] for u in self.pr))
        self._rockets(st, t)
        self.alive, self.crowns, self.prev = alive, crowns, bodies
        self.end = {"tick": t, "king": round(king[2], 4) if king else 0.0, "princess": [round(f, 4) for f in own],
                    "foe_princess": [round(f, 4) for f in foe], "crowns": crowns}

    def _tornados(self, st, t, bodies, down) -> None:
        here = {(s.x, s.y) for s in st.spells if int(s.team) == self.side and s.card_id == self.tornado}
        for xy in here - {a["xy"] for a in self.active}:              # a new cast: its bodies as they stood BEFORE it
            src = self.prev if self.prev is not None else bodies
            self.active.append({"xy": xy, "seen": t, "last": t, "down": down,
                                "d0": {u: self._dk(b) for u, b in src.items() if self._in(b, xy)}, "d1": {}})
        for a in self.active:
            if a["xy"] in here:
                a["last"] = t
                for u, b in bodies.items():                           # a body walking in joins where it stands
                    if u not in a["d0"] and self._in(b, a["xy"]):
                        a["d0"][u] = self._dk(b)
            for u in a["d0"]:                                          # the last position seen (incl. the first stop after)
                if u in bodies:
                    a["d1"][u] = self._dk(bodies[u])
        for a in [a for a in self.active if a["xy"] not in here]:
            self._close(a)
        self.active = [a for a in self.active if a["xy"] in here]

    def _close(self, a) -> None:
        toward = sum(d - a["d1"].get(u, d) for u, d in a["d0"].items())
        self.tornados.append({"seen": a["seen"], "end": a["last"], "down": a["down"], "toward": round(toward, 4),
                              "n": len(a["d0"])})

    def _rockets(self, st, t) -> None:
        for s in st.spells:
            if int(s.team) == self.side and s.card_id == self.rocket:
                k = (s.aim_x, s.aim_y)
                if k not in self.rk or t - self.rk[k] > TRACK_TICKS:
                    ax, ay = to_board(s.aim_x, s.aim_y, self.side)
                    self.rockets.append({"seen": t, "aim": [ax, ay], "tower": any(
                        math.hypot(ax - x, ay - y) <= TOWER_AIM_TILES for x, y in ENEMY_SLOTS)})
                self.rk[k] = t

    def result(self) -> dict:
        for a in self.active:                                          # the match ended under a Tornado
            self._close(a)
        self.active = []
        return {"lost": [list(x) for x in self.lost], "falls": list(self.falls), "tornados": list(self.tornados),
                "rockets": list(self.rockets), "end": self.end}


# ---------------------------------------------------------------------------------------------------- learner side (pure)
def lost_at(crown: dict, ticks) -> np.ndarray:
    """L (own princess HP lost while both stood) at each tick: the latest change point at or before it, 0 before any."""
    ticks = np.asarray(ticks, dtype=np.int64)
    if not crown["lost"]:
        return np.zeros(len(ticks))
    T = np.array([p[0] for p in crown["lost"]], dtype=np.int64)
    V = np.array([p[1] for p in crown["lost"]], dtype=np.float64)
    i = np.searchsorted(T, ticks, side="right") - 1
    return np.where(i >= 0, V[np.maximum(i, 0)], 0.0)


def gave_back(crown: dict) -> list:
    """Own princess falls that happened while we led exactly 1-0 (at most one per match)."""
    return [f for f in crown["falls"] if f["who"] == "own" and list(f["before"]) == [1, 0]]


def row_terms(crown: dict, plays: list, ticks, p: dict) -> dict:
    """One match: its crown record, its side's plays (e1_eval play records) and the decision tick of every KEPT row (time
    order) -> {"r": the terms' reward per kept row, "phi": princess_redirect potential per row or None, per-term sums
    "lead" / "redirect" / "tornado", "unmapped" Tornado penalties with no deciding row}. Damage before the first kept row
    is not charged (no kept decision preceded it)."""
    ticks = np.asarray(ticks, dtype=np.int64)
    n = len(ticks)
    r, out = np.zeros(n), {"phi": None, "lead": 0.0, "redirect": 0.0, "tornado": 0.0, "unmapped": 0}
    if p.get("lead_protect"):
        for f in gave_back(crown):
            i = int(np.searchsorted(ticks, f["tick"], side="right")) - 1
            if i >= 0:
                r[i] -= p["lead_protect_w"]
                out["lead"] -= p["lead_protect_w"]
    mode = p.get("princess_redirect")
    if mode and n:
        L = lost_at(crown, ticks)
        if mode == "penalty":
            end = crown["lost"][-1][1] if crown["lost"] else 0.0
            d = -p["princess_redirect_w"] * (np.r_[L[1:], end] - L)
            r += d
            out["redirect"] = float(d.sum())
        else:
            out["phi"] = -p["princess_redirect_w"] * L
    if p.get("tornado_king_penalty"):
        row, total = {int(t): i for i, t in enumerate(ticks)}, 0.0
        for ev in sorted(crown["tornados"], key=lambda e: e["seen"]):
            if ev["down"] < 1 or ev["toward"] <= 0:
                continue
            e = min(TORNADO_EVENT_CAP, p["tornado_king_w"] * ev["toward"], TORNADO_MATCH_CAP - total)
            if e <= 0:
                break
            i = _row_of(int(ev["seen"]), "tornado", plays, row)
            if i is None:
                out["unmapped"] += 1
                continue
            r[i] -= e
            total += e
        out["tornado"] = -total
    out["r"] = r
    return out


def match_summary(crown: dict) -> dict:
    """One match's crown numbers (eval slices, training monitors)."""
    falls, end = crown["falls"], crown.get("end") or {}
    at = {}
    for f in falls:
        at.setdefault(f["tick"], []).append(f["who"])
    led = any(list(f["before"]) == [0, 0] and at[f["tick"]] == ["foe"] for f in falls)   # 0-0 -> exactly 1-0
    tor = [e for e in crown["tornados"] if e["down"] >= 1]
    return {"king_end": end.get("king"), "lost_princess": any(f["who"] == "own" for f in falls),
            "took_princess": any(f["who"] == "foe" for f in falls), "led_10": led,
            "gave_back": bool(gave_back(crown)), "tornados": len(crown["tornados"]), "tornados_after_fall": len(tor),
            "tornado_to_king": sum(e["toward"] >= TOWARD_MIN_TILES for e in tor),
            "toward_after_fall": round(sum(max(0.0, e["toward"]) for e in tor), 4),
            "rockets": len(crown["rockets"]), "rockets_tower": sum(bool(x["tower"]) for x in crown["rockets"])}


def batch_stats(summaries: list, sums: list) -> dict:
    """Per-update monitors: per-match means of the summaries and of each term's summed reward (``sums``: row_terms dicts)."""
    n = max(len(summaries), 1)
    st = {"matches": len(summaries)}
    for k in (summaries[0] if summaries else ()):
        vals = [s[k] for s in summaries if s[k] is not None]
        st[f"{k}_per_match"] = round(float(sum(vals)) / max(len(vals), 1), 4)
    for k in ("lead", "redirect", "tornado"):
        st[f"{k}_reward_per_match"] = round(sum(s[k] for s in sums) / n, 5)
    st["unmapped_tornados"] = int(sum(s["unmapped"] for s in sums))
    tot = [abs(float(s["r"].sum())) for s in sums]
    st["dominates"] = float(np.mean(tot)) if tot else 0.0          # mean |match term reward| / 1 (the win reward)
    return st


def crown_log(result: dict) -> Optional[dict]:
    """search_s0 --crown-log: the eval row's crown block (summary + events; the L series stays out of the row)."""
    c = result.get("crown")
    return None if c is None else {"summary": match_summary(c), **{k: c[k] for k in ("falls", "tornados", "rockets", "end")}}
