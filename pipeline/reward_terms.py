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
    princess_take: on             L74 W7 (10-20, the SIM OPPONENT's crown-aware objective; option C of opp_model/OPP_MODEL.md):
                                  +princess_take_w per ENEMY princess tower the learner fells in play (tick < TIEBREAK_TICK),
                                  on the last kept row at or before the fall. It CHANGES the optimum, deliberately: an opponent
                                  trained on win / loss alone learns to stall (Stage 2: OT 66-75%); this pays converting towers.
    rocket_tower: on              L74 W10 (10-20, plan1019 Rocket use; scratchpad/gauntlet/L74/rocket/ROCKET.md): +rocket_tower_w per
                                  princess tower of ENEMY PRINCESS HP our Rocket removed (king damage never pays: owner doctrine,
                                  never the king), on the row that DECIDED the Rocket, summed <= ROCKET_MATCH_CAP per match. It
                                  CHANGES the optimum, deliberately: the potential form is policy-invariant (W6) and the tower
                                  potential (factorial factor E) did not move tower Rockets; the SIM's win-only reward shows no
                                  payoff for chip Rockets even vs the calibrated opponent (ROCKET.md). The tracker measures the
                                  damage only with rocket_dmg (actor crown_track "rocket_dmg"); otherwise its result is unchanged.
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
    play_cost: on                 L74 W18 (10-22, opp_model/DIAG_12.md): -play_cost_w per ACCEPTED play of the learner, on the
                                  row that decided it, summed <= PLAY_COST_MATCH_CAP per match. For the SIM OPPONENT's tempo: it
                                  plays 36% more cards per minute in 2x / OT than Ranked humans (style d +1.22) and wins
                                  regulation games by it. It CHANGES the optimum, deliberately: a marginal play must now pay.
    rocket_cycle: on              Plan A (10-25, owner: Rocket cycling that WINS the SIM gate; rocket_tower lost it 10-20, -4.7 /
                                  -6.5 pp vs CLX): rocket_tower's credit (+rocket_cycle_w per princess tower of enemy princess HP
                                  our Rocket removed, <= ROCKET_MATCH_CAP per match) ONLY for a FREE chip: decided at tick >=
                                  CYCLE_MIN_TICK (2x / OT), at own elixir >= CYCLE_MIN_ELIXIR (the elixir would otherwise sit
                                  near full), with none of our princess HP lost to enemy TROOPS / buildings in the
                                  CYCLE_QUIET_TICKS before (no defence owed). Enemy SPELL damage on our princesses does not block
                                  it (owner 10-25: it lands no matter what; if they spell-cycle our tower we cycle too). A Rocket
                                  the defence needed earns nothing, so the term never pays for giving up a defence.
    king_redirect: on             Plan A (10-25, owner: king redirect that WINS the SIM gate; the princess_redirect penalty lost
                                  10-20, -1.3 / -6.4 pp): +king_redirect_w per king tower of OUR KING HP lost from one of our
                                  Tornados' cast to KING_WINDOW ticks after it ends, for Tornados cast while BOTH our princesses
                                  stand that pulled their bodies >= TOWARD_MIN_TILES net toward our king (the hits the king took
                                  instead of a princess), <= KING_EVENT_CAP per Tornado and KING_MATCH_CAP per match. It pays the
                                  redirect act only; princess damage is not taxed (the penalty's over-defence incentive).
The learner side (``row_terms``) is pure: the record + the side's plays + the KEPT rows' decision ticks -> per-row reward.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from pipeline.spell_value import KING_TOWER, PRINCESS_TOWER, TILE, TORNADO_R_TILES, _row_of, to_board

TERMS = {"rocket_tower": "rocket_tower_w",                          # W10 (first: W7's princess_take edits the last line)
         "lead_protect": "lead_protect_w", "princess_redirect": "princess_redirect_w",
         "tornado_king_penalty": "tornado_king_w",
         "princess_take": "princess_take_w",                           # switch -> its weight key (rl_royale CROWN_KEYS)
         "play_cost": "play_cost_w",
         "rocket_cycle": "rocket_cycle_w", "king_redirect": "king_redirect_w"}   # Plan A 10-25                                   # W18 (10-22): the SIM opponent's tempo
DEFAULTS = {"rocket_tower_w": 0.5,           # W10: per princess tower of enemy princess HP our Rocket removed (a ~0.11
            #                                   chip = 0.055 ~ 2.75 elixir at spell_value's 0.02 / elixir; <= the match cap)
            "lead_protect_w": 0.2,            # x the win reward, once per match (DOCTRINE_MEASURED 4 R1)
            "princess_redirect_w": 0.2,       # per princess tower of HP lost while both stand: a felled first princess
            #                                   costs <= 0.2 on top of the terminal reward; |sum| < 2 w per match
            "princess_take_w": 0.2,           # W7: per enemy princess felled in play (<= 2 per match)
            "play_cost_w": 0.005,             # W18: per ACCEPTED play of the learner (~40 per match = 0.2, <= the match cap)
            "tornado_king_w": 0.01,
            "rocket_cycle_w": 0.5,            # Plan A: as rocket_tower_w, free chips only (~0.055 per 546-HP chip)
            "king_redirect_w": 0.5}           # Plan A: per king tower of OUR king HP absorbed after a redirect Tornado           # per tile of net pull toward our king (3 bodies x 3 tiles = 0.09; spell_value
#                                               prices elixir at 0.02, so a Tornado's 3 elixir = 0.06)
REDIRECT_MODES = ("penalty", "potential")
PLAY_COST_MATCH_CAP = 0.3       # W18: |play_cost reward| per match
TORNADO_EVENT_CAP, TORNADO_MATCH_CAP = 0.15, 0.3   # ponytail: fixed caps, a config key if an arm needs another
CYCLE_MIN_TICK, CYCLE_MIN_ELIXIR, CYCLE_QUIET_TICKS = 2400, 7.0, 100   # Plan A rocket_cycle: 2x / OT, >= 7 elixir, 5 s
SPELL_NEAR_TILES = 5.0          # rocket_cycle: an enemy spell aimed this close to our princess = its damage there is spell
CYCLE_MATCH_CAP = 0.6             # 10-26 owner (live: no Rocket cycling at all): rocket_cycle's own cap, ~5 free chips at w 1
KING_WINDOW, KING_EVENT_CAP, KING_MATCH_CAP = 100, 0.1, 0.2           # Plan A king_redirect: 5 s after the Tornado ends
ROCKET_MATCH_CAP = 0.3          # W10: |rocket_tower reward| per match (~5 chips at the default weight; pros fire 1.6 / match)
ROCKET_BLAST_TILES = 2.0        # catalog Rocket radius (spell_value.ROCKET_R_TILES); a tower counts by the engine's edge rule
TOWARD_MIN_TILES = 1.0          # eval slice: a Tornado "to the king" moved its bodies >= this net toward our king
TOWER_AIM_TILES = 3.0           # doctrine (habits/hablib.rocket_uses): a tower Rocket's aim is this close to a slot
ENEMY_SLOTS = ((3.5, 6.5), (14.5, 6.5), (9.0, 3.0))   # enemy princess L / R and king, board tiles, my frame
TIEBREAK_TICK = 5990            # opp_model/crowns.py's rule: a fall at clock >= this is the tiebreak tower, not play
TRACK_TICKS = 30                # SpellTracker's rule: a spell seen again at the same point within this is the same cast


def bound(p: dict) -> float:
    """max |summed reward| (or |Phi|) per match of the terms on in ``p`` (crown_cfg's dict): lead w (crowns never fall, so
    1-0 -> 1-1 happens at most once), redirect 2 w (< 2 princess towers of HP before the first falls), Tornado its cap."""
    return (ROCKET_MATCH_CAP * bool(p.get("rocket_tower"))
            + float(p.get("lead_protect_w", 0.0)) * bool(p.get("lead_protect"))
            + 2.0 * float(p.get("princess_redirect_w", 0.0)) * bool(p.get("princess_redirect"))
            + TORNADO_MATCH_CAP * bool(p.get("tornado_king_penalty"))
            + 2.0 * float(p.get("princess_take_w", 0.0)) * bool(p.get("princess_take"))
            + PLAY_COST_MATCH_CAP * bool(p.get("play_cost"))
            + CYCLE_MATCH_CAP * bool(p.get("rocket_cycle")) + KING_MATCH_CAP * bool(p.get("king_redirect")))


class CrownTracker:
    """One match, one side (rl_royale crown terms / search_s0 --crown-log). Holds no env reference after __init__."""

    def __init__(self, env, side: int, rocket_dmg: bool = False, king: bool = False, troop: bool = False):
        self.side = int(side)
        self.tornado, self.rocket = env.ids.get("Tornado"), env.ids.get("Rocket")
        self.king_track, self.klost, self.kl = bool(king), [], 0.0   # Plan A king_redirect (opt-in): own king HP lost
        self.troop_track, self.tlost, self.tl = bool(troop), [], 0.0  # Plan A rocket_cycle: own princess HP lost to non-spells
        self.pfrac, self.spell_near = None, set()                       # previous own princess fracs; uids near enemy spells
        self.rocket_dmg = bool(rocket_dmg)  # W10 rocket_tower (opt-in): our Rockets' enemy-princess damage -> "rocket_hits"
        self.fly, self.wait, self.hits, self.fpos, self.foe_last = {}, [], [], None, None
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
            if self.king_track and round(1.0 - king[2], 6) != self.kl:     # Plan A king_redirect: change points
                self.kl = round(1.0 - king[2], 6)
                self.klost.append([t, self.kl])
        own = [tw[u][2] if u in tw else 0.0 for u in self.pr]          # a tower gone from the list = destroyed
        if self.troop_track:                                           # Plan A rocket_cycle (off: never runs)
            self._troop_loss(st, t, tw, own)
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
        if self.rocket_dmg:                                            # W10 (off: never called, the result unchanged)
            self._rocket_hits(st, t, dict(zip(self.fpr, foe)))
        self.alive, self.crowns, self.prev = alive, crowns, bodies
        self.end = {"tick": t, "king": round(king[2], 4) if king else 0.0, "princess": [round(f, 4) for f in own],
                    "foe_princess": [round(f, 4) for f in foe], "crowns": crowns}

    def _troop_loss(self, st, t, tw, own) -> None:
        """Own princess HP lost since the previous stop, minus what enemy spells explain: a tower with an enemy spell aimed
        within SPELL_NEAR_TILES at this stop or the previous one counts its loss as spell damage (an in-flight Rocket lands
        the stop after it is gone). ponytail: stop resolution, so troop + spell hits on one tower in one interval count as
        spell; a rolling spell the engine does not list in st.spells (if any) counts as troop."""
        near = set()
        for s in st.spells:
            if int(s.team) == self.side:
                continue
            for u in self.pr:
                if u in tw and min(math.hypot(s.aim_x - tw[u][3], s.aim_y - tw[u][4]),
                                   math.hypot(s.x - tw[u][3], s.y - tw[u][4])) <= SPELL_NEAR_TILES * TILE:
                    near.add(u)
        if self.pfrac is not None:
            d = sum(max(0.0, a - b) for u, a, b in zip(self.pr, self.pfrac, own) if u not in near | self.spell_near)
            if d > 0:
                self.tl = round(self.tl + d, 6)
                self.tlost.append([t, self.tl])
        self.pfrac, self.spell_near = list(own), near

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

    def _rocket_hits(self, st, t, foe) -> None:
        """W10 rocket_tower: each of our Rockets -> the enemy PRINCESS HP (princess-tower units) inside its blast at its aim,
        lost from the last stop it was seen in flight to the first stop AFTER the one where it is gone (the impact shows one
        tick after the spell leaves: spell_value's rule). ponytail: stop resolution (<= 2 decision stops), so other damage on
        the same tower in that window (an X-Bow bolt, a troop) counts too; SpellTracker's single-tick stepping is the exact
        upgrade if a census shows the excess matters."""
        if self.fpos is None:
            self.fpos = {e.uid: (e.x, e.y, e.radius) for e in st.entities if e.uid in self.fpr}
        for w in [w for w in self.wait if t > w["gone"]]:
            self.hits.append({"seen": w["seen"], "impact": w["gone"],
                              "dmg": round(sum(max(0.0, w["before"][u] - foe[u]) for u in w["in"]), 4)})
        self.wait = [w for w in self.wait if t <= w["gone"]]
        here = {(s.aim_x, s.aim_y) for s in st.spells if int(s.team) == self.side and s.card_id == self.rocket}
        for k in [k for k in self.fly if k not in here]:
            f = self.fly.pop(k)
            self.wait.append({"seen": f["seen"], "gone": t, "before": f["hp"], "in": f["in"]})
        for k in here:
            if k in self.fly:
                self.fly[k]["hp"] = dict(foe)
            else:
                self.fly[k] = {"seen": t, "hp": dict(foe), "in": [u for u, (x, y, r) in self.fpos.items() if math.hypot(
                    k[0] - x, k[1] - y) <= ROCKET_BLAST_TILES * TILE + r]}
        self.foe_last = dict(foe)

    def result(self) -> dict:
        for a in self.active:                                          # the match ended under a Tornado
            self._close(a)
        self.active = []
        out = {"lost": [list(x) for x in self.lost], "falls": list(self.falls), "tornados": list(self.tornados),
               "rockets": list(self.rockets), "end": self.end}
        if self.rocket_dmg:                                            # W10: impacts still waiting resolve on the last stop
            hits = list(self.hits) + [{"seen": w["seen"], "impact": w["gone"], "dmg": round(sum(
                max(0.0, w["before"][u] - self.foe_last[u]) for u in w["in"]), 4)} for w in self.wait]
            out["rocket_hits"] = hits
        if self.troop_track:                                           # Plan A rocket_cycle (off: no key, unchanged)
            out["troop_lost"] = [list(x) for x in self.tlost]
        if self.king_track:                                            # Plan A king_redirect (off: no key, unchanged)
            out["king_lost"] = [list(x) for x in self.klost]
        return out


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
    if p.get("princess_take"):                        # W7: off = no "take" key (the W6 outputs unchanged)
        out["take"] = 0.0
        for f in crown["falls"]:
            if f["who"] == "foe" and int(f["tick"]) < TIEBREAK_TICK:
                i = int(np.searchsorted(ticks, f["tick"], side="right")) - 1
                if i >= 0:
                    r[i] += p["princess_take_w"]
                    out["take"] += p["princess_take_w"]
    if p.get("rocket_tower"):                         # W10: off = no "rocket" keys (the W6 / W7 outputs unchanged)
        if "rocket_hits" not in crown:
            raise ValueError("rocket_tower needs the tracker's rocket_hits (actor_cfg crown_track 'rocket_dmg')")
        row, total, out["rocket_unmapped"] = {int(t): i for i, t in enumerate(ticks)}, 0.0, 0
        for h in sorted(crown["rocket_hits"], key=lambda h: h["seen"]):
            e = min(p["rocket_tower_w"] * float(h["dmg"]), ROCKET_MATCH_CAP - total)
            if e <= 0:
                continue
            i = _row_of(int(h["seen"]), "rocket", plays, row)
            if i is None:
                out["rocket_unmapped"] += 1
                continue
            r[i] += e
            total += e
        out["rocket"] = total
    if p.get("play_cost"):                           # W18: off = no "play_cost" key (the outputs above unchanged)
        row, total = {int(t): i for i, t in enumerate(ticks)}, 0.0
        for pl in plays:                             # -w on the row that DECIDED each accepted play, summed <= the cap
            i = row.get(int(pl["tick"]))
            if i is None or not pl.get("accepted"):
                continue
            e = min(p["play_cost_w"], PLAY_COST_MATCH_CAP - total)
            if e <= 0:
                break
            r[i] -= e
            total += e
        out["play_cost"] = -total
    if p.get("rocket_cycle"):                         # Plan A: off = no "rocket_cycle" keys (the outputs above unchanged)
        if "rocket_hits" not in crown:
            raise ValueError("rocket_cycle needs the tracker's rocket_hits (actor_cfg crown_track 'rocket_dmg')")
        if "troop_lost" not in crown:
            raise ValueError("rocket_cycle needs the tracker's troop_lost (actor_cfg crown_track with 'troop')")
        row, total = {int(t): i for i, t in enumerate(ticks)}, 0.0
        out["rocket_cycle_unmapped"], out["rocket_cycle_free"] = 0, 0
        lost = crown["troop_lost"]                    # enemy spell damage does not block a cycle Rocket (owner 10-25)
        for h in sorted(crown["rocket_hits"], key=lambda h: h["seen"]):
            q = _play_of(int(h["seen"]), "rocket", plays)
            if q is None or row.get(int(q["tick"])) is None:
                out["rocket_cycle_unmapped"] += 1
                continue
            t0 = int(q["tick"])
            free = (t0 >= CYCLE_MIN_TICK and float(q.get("elixir_exact", q.get("elixir", 0.0))) >= CYCLE_MIN_ELIXIR
                    and _lost_before(lost, t0) == _lost_before(lost, t0 - CYCLE_QUIET_TICKS))
            e = min(p["rocket_cycle_w"] * float(h["dmg"]), CYCLE_MATCH_CAP - total) if free else 0.0
            if e <= 0:
                continue
            r[row[t0]] += e
            total += e
            out["rocket_cycle_free"] += 1
        out["rocket_cycle"] = total
    if p.get("king_redirect"):                        # Plan A: off = no "king_redirect" keys (the outputs above unchanged)
        if "king_lost" not in crown:
            raise ValueError("king_redirect needs the tracker's king_lost (actor_cfg crown_track with 'king')")
        row, total, out["king_redirect_unmapped"] = {int(t): i for i, t in enumerate(ticks)}, 0.0, 0
        for ev in sorted(crown["tornados"], key=lambda e: e["seen"]):
            if ev["down"] != 0 or ev["toward"] < TOWARD_MIN_TILES:
                continue
            kl = crown["king_lost"]
            got = _lost_before(kl, int(ev["end"]) + KING_WINDOW) - _lost_before(kl, int(ev["seen"]))
            e = min(KING_EVENT_CAP, p["king_redirect_w"] * got, KING_MATCH_CAP - total)
            if e <= 0:
                continue
            i = _row_of(int(ev["seen"]), "tornado", plays, row)
            if i is None:
                out["king_redirect_unmapped"] += 1
                continue
            r[i] += e
            total += e
        out["king_redirect"] = total
    out["r"] = r
    return out


def _lost_before(changes: list, t: int) -> float:
    """[[tick, cumulative lost]] change points -> the value at tick ``t`` (0 before the first change)."""
    v = 0.0
    for tk, x in changes:
        if int(tk) > t:
            break
        v = float(x)
    return v


def _play_of(seen: int, card: str, plays: list):
    """spell_value._row_of's rule, returning the PLAY record (its decision tick + elixir) instead of the row."""
    from pipeline.spell_value import PLAY_MATCH_TICKS, _slug
    best = None
    for q in plays:
        land = int(q.get("land_tick", q["tick"]))
        if q["accepted"] and _slug(q["card"]) == card and seen - PLAY_MATCH_TICKS <= land <= seen:
            best = q if best is None or land >= int(best.get("land_tick", best["tick"])) else best
    return best


def match_summary(crown: dict) -> dict:
    """One match's crown numbers (eval slices, training monitors)."""
    falls, end = crown["falls"], crown.get("end") or {}
    at = {}
    for f in falls:
        at.setdefault(f["tick"], []).append(f["who"])
    led = any(list(f["before"]) == [0, 0] and at[f["tick"]] == ["foe"] for f in falls)   # 0-0 -> exactly 1-0
    tor = [e for e in crown["tornados"] if e["down"] >= 1]
    s = {"king_end": end.get("king"), "lost_princess": any(f["who"] == "own" for f in falls),
            "took_princess": any(f["who"] == "foe" for f in falls), "led_10": led,
            "gave_back": bool(gave_back(crown)), "tornados": len(crown["tornados"]), "tornados_after_fall": len(tor),
            "tornado_to_king": sum(e["toward"] >= TOWARD_MIN_TILES for e in tor),
            "toward_after_fall": round(sum(max(0.0, e["toward"]) for e in tor), 4),
            "rockets": len(crown["rockets"]), "rockets_tower": sum(bool(x["tower"]) for x in crown["rockets"])}
    if "rocket_hits" in crown:                       # W10 rocket_dmg tracker only (otherwise the summary is unchanged)
        s["rocket_princess_dmg"] = round(sum(h["dmg"] for h in crown["rocket_hits"]), 4)
    return s


def batch_stats(summaries: list, sums: list) -> dict:
    """Per-update monitors: per-match means of the summaries and of each term's summed reward (``sums``: row_terms dicts)."""
    n = max(len(summaries), 1)
    st = {"matches": len(summaries)}
    for k in (summaries[0] if summaries else ()):
        vals = [s[k] for s in summaries if s[k] is not None]
        st[f"{k}_per_match"] = round(float(sum(vals)) / max(len(vals), 1), 4)
    for k in ("lead", "redirect", "tornado") + (("take",) if any("take" in s for s in sums) else ()):
        st[f"{k}_reward_per_match"] = round(sum(s[k] for s in sums) / n, 5)
    if any("play_cost" in s for s in sums):         # W18 play_cost on (off: no key, the stats unchanged)
        st["play_cost_reward_per_match"] = round(sum(s.get("play_cost", 0.0) for s in sums) / n, 5)
    if any("rocket" in s for s in sums):            # W10 rocket_tower on (off: no keys, the stats unchanged)
        st["rocket_reward_per_match"] = round(sum(s.get("rocket", 0.0) for s in sums) / n, 5)
        st["rocket_unmapped"] = int(sum(s.get("rocket_unmapped", 0) for s in sums))
    st["unmapped_tornados"] = int(sum(s["unmapped"] for s in sums))
    tot = [abs(float(s["r"].sum())) for s in sums]
    st["dominates"] = float(np.mean(tot)) if tot else 0.0          # mean |match term reward| / 1 (the win reward)
    return st


def crown_log(result: dict) -> Optional[dict]:
    """search_s0 --crown-log: the eval row's crown block (summary + events; the L series stays out of the row)."""
    c = result.get("crown")
    return None if c is None else {"summary": match_summary(c), **{k: c[k] for k in ("falls", "tornados", "rockets", "end")}}
