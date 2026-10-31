"""S0: decision-time rollout SEARCH over the frozen generalist, on RoyaleSim, closed loop, NO training (L69).

    research/ext/Royale/.venv/Scripts/python.exe -m pipeline.search_s0 --out scratchpad/gauntlet/L69/s0/run1 \
        --seeds 0:8 --opps gen,s1 --arms plain,search,force_play,random,never [--horizon 12] [--interval 1] \
        [--topk 4] [--cells 3] [--threads 2] [--workers 1] [--tail-cap 7200] [--max-wall-min 0]
        [--device cpu] [--search-min-p 0] [--gen CKPT] [--opp-gen CKPT]
    ... -m pipeline.search_s0 --summarise scratchpad/gauntlet/L69/s0/run1       (re-read matches.jsonl)

Writes ``<out>/matches.jsonl`` (one line per (arm, opponent, seed), flushed as each ends), ``<out>/summary.json``
(per arm x opponent: W/L/D, mean crowns diff, mean crown-tower HP diff; per seed PAIRED deltas of every arm against
``plain``) and ``<out>/run.json`` (args, checkpoint shas). CPU by default: CUDA only behind --device cuda.

WHICH MODEL PLAYS WHICH ROLE
  ``--gen``      OUR policy (every arm), AND the rollout self-model: inside a fork the opponent is simulated by this same
                 model (``Runner.learner``), whatever the real opponent is.
  ``--opp-gen``  ONLY the real, frozen ``gen`` opponent (``--opps gen``). Default None = ``--gen`` (the old behaviour: a
                 separate object loaded from the same file). Lets a candidate checkpoint (e.g. an RL
                 ``league1c_u*.pt``) be ours while the opponent stays the frozen gen_v1_s0. Its path and sha256 go in
                 run.json (``opp_gen``, ``opp_gen_sha256``) and in every match line. The ``s1`` opponent is ``--s1``.
  The candidate's grid must equal ``--opp-gen``'s (Runner checks it).
  POSTURE (rl_royale C1): a ``--gen`` checkpoint carrying rl["posture_head"] plays its ARGMAX posture (re-chosen every
  ``posture_every`` ticks from its g + public ctx) as a gate-threshold offset on our side: + dtau on the tau in force
  (plain tau, or tau_phase / tau_threatened via decide_batch's tau_delta; e1_eval.posture_live; the sample policy
  through sample_decide_batch); each match line gets ``posture_shares`` / ``posture_decisions`` / ``posture_choices``.
  ABILITY (rl_royale B6): a ``--gen`` checkpoint carrying rl["ability_head"] decides OUR hero / champion presses
  GREEDILY (press iff p > 0.5, e1_eval.ability_decide; needs --hero-abilities; the opponent keeps the rule); the line
  gets ``ability_head`` {decisions, presses, p_mean}. ``--ability-stats`` (opt-in, any checkpoint) adds
  ``ability_stats`` = our accepted presses, elixir on them, enemy bodies in the ability radius at the press and how many
  of those lost HP / died within 2 s (royale_env ability_outcomes; any damage source). Our side in a fork does not
  decide presses (its rule is off too).
  Our side inside a search fork does not apply it. No head = unchanged.

DESIGN (lead-fixed, L69 ticket S0)
  Our side: icebow, ``gen_v1_s0`` on CPU, under the measured live condition (clean obs, opp-elixir counter, action
  delay 26, extrapolate 26, decide every 10 ticks, rl_royale.yaml's afford/stall keys). Arms at our decisions:
    plain       the live rule at tau 0.35 (e1_eval.live_decide_batch; no search).
    search      at every decision (``--interval`` 1) with >= 1 affordable card: candidates = WAIT + the top ``--topk``
                affordable cards (the policy's hand-masked card logits) x the top ``--cells`` cells each (that card's
                cell logits); each scored by ONE rollout, argmax played, ties -> WAIT. Nothing affordable -> WAIT, no
                search. Off-interval decisions play the plain rule.
    force_play  the top candidate (top card, top cell), no rollouts -- "does playing at all explain the gain".
    random      a uniform pick among the same shortlist's PLAY candidates ONLY (WAIT is never drawn, as in the old
                harness's random control) -- "does choosing matter".
    never       our side never plays (anti-stall included) -- the restraint floor: the Scorer subtracts spent elixir
                over a 12 s horizon, so WAIT can win by construction; search must beat THIS, not only plain.
  ``--search-min-p P`` (default 0 = the faithful design, search every decision): search arm only, a decision whose
  plain gate p < P with no anti-stall is a WAIT without rollouts (counted ``unsearched`` / ``gate_skipped``).
  ``--device cuda`` moves our policy, the rollout self-model and the opponents to the GPU (default cpu; no CUDA call
  is made otherwise). Recorded in run.json and in every match line (device, search_min_p, searched, unsearched).
  A chosen action is a decision at the current tick, applied through ``SelfPlaySide.apply``: with delay 26 it is queued
  and lands at tick + 26 exactly as the plain policy's play would.
  ROLLOUT: fork = RoyaleSim ``save_state``/``load_state`` into a pooled engine + deep copies of the env's python fields
  and BOTH sides' python state (models / cfg / deck shared, never copied). In a fork our candidate lands normally and
  our side then makes NO further plays (``--rollout-self idle``, the default = S0; ``policy``: our side keeps
  deciding with its OWN live path -- the plain arm's rule, gen_v1_s0 at tau 0.35, afford mask, stall, delay 26,
  extrapolation 26, counter -- batched across forks per role like the opponent; the scorer charges EVERY accepted
  play of ours in the fork, candidate + follow-ups, so follow-ups never add board/tower value for free); the
  opponent keeps deciding through its own SelfPlaySide code path and its own
  cfg, but with policy = gen_v1_s0 on the opponent's deck, live rule tau 0.27 (a SELF-MODEL: against S1 the rollout
  does not know S1's policy). If the opponent also decides at the root tick, its fork decision is the self-model's.
  Horizon ``--horizon`` s (12 s = 240 ticks) = the fork env's tail_cap. All forks of one decision run in LOCKSTEP
  rounds so the opponent's forward passes are ONE batch across forks.
  SCORE = the old ``clashrl.sim.rollout_search.Scorer.score`` (crown weight 1.0), ported (``Scorer`` below):
      (enemy tower fraction destroyed) - (our tower fraction lost) - spent * 0.061
      + [(our board value - theirs) at the horizon - the same at the root] + 1.0 * (crowns taken - crowns lost)
  Mapping, old sim -> RoyaleSim ``BattleState``:
      eng.towers[team] (2 princess + king), t.hp, towers[team][0].max_hp
          -> entities of kind KING_TOWER / PRINCESS_TOWER with that team, max(0, hp); ref = a PRINCESS max_hp of the
             team (remembered, so a destroyed/removed tower cannot change the unit)
      eng.crowns(team)                  -> players[team].crowns
      eng.units (team, hp > 0, kind troop/building), u.spec.base
          -> entities of kind TROOP / BUILDING, hp > 0, card_id != EMPTY; base = dataset_gen.card_key(catalogue name)
             of the entity's CARD (RoyaleSim tags bodies with the card that made them). threat_value collapses bodies
             to cards through the DB's own count, as before. Spawned bodies carry their spawner's card id (e.g. a
             hut's goblins count as huts) -- a known approximation.
      u.spec.elixir / (squad_count or count)  (bodies with no finite ignore cost)
          -> CardInfo.elixir / max(1, CardInfo.count) from the RoyaleSim catalogue
      db                                -> clashrl.cards.shared() (icebow's card DB), threat_value unchanged
      tower_level (old: 15)             -> the ENGINE's: the princess max_hp at the root mapped through
                                           levels.PRINCESS_HP (RoyaleSim: 3052 = level 11; king 4824 = KING_HP[11]
                                           cross-checked); no exact match -> ValueError. The tower term's unit
                                           (princess max_hp) and threat_value's (tower_hp(tower_level)) are then the
                                           same number, which Scorer.tower_frac enforces.
      enemy_level (old: threat_value default 11) -> the engine's card_level (RoyaleSim 11; the DB's stats are
                                           stored at REF_LEVEL 11 and equal the engine's CardInfo.hitpoints)
      spent                             -> ``fork_spent``: the catalogue costs of ALL our plays ACCEPTED in the fork
                                           between root and horizon. Idle: only the candidate can play, so this is
                                           the candidate's cost iff it landed (the old Scorer's ``spent``); policy:
                                           candidate + follow-ups (lead ruling, L69 option 1).
  Team 0 of the old scorer = OUR side (the learner), team 1 = the opponent.
  ``--scorer v2`` (L69 scorer upgrade; default v1 = everything above, unchanged): only the BOARD value changes. v1 prices
  every body at its card's catalogue HP wherever it stands. v2 gives each body a multiplier
      m = hp_frac * pos,   hp_frac = clip(hp / max_hp, 0, 1)   (the entity's own engine max_hp; shields ignored)
      pos = 0.5 + clip((y - y_own) / (y_opp - y_own), 0, 1)     in [0.5, 1.5]
  where y_own / y_opp = the princess-tower y line of the unit's OWN team / of the other team (engine frame; cached per
  team from the first state with BOTH its princess towers present, else the arena constant ARENA_PRINCESS_Y). So for OUR units pos grows as they advance toward the enemy towers (threat) and for
  ENEMY units as they approach OUR towers (danger): 0.5 at/behind their own princess line (threatens nothing yet),
  1.0 at the river midpoint (= the v1 price), 1.5 at/past the opposing princess line (on a tower). Linear, bounded,
  symmetric, mean 1 over the lane, one constant (POS_HALF = 0.5). Elixir-priced bodies (no finite ignore cost): v1's
  per-body value x m. The pooled threat_value part stays POOLED (v1's superlinear clearing queue) and is multiplied by
  the elixir-weighted mean m of its bodies (weight = catalogue elixir / count; plain mean if every weight is 0), so a
  lone unit is exactly v1 x m. BOARD_CAP applies after, as in v1. Known limits: a defender standing at its own tower
  is discounted to 0.5 (the ticket's threat/danger reading, not "useful on defence"); the pooled HP scaling is linear
  although threat_value's queue is superlinear in HP.

DISCLOSED OPTIMISM: rollouts start from the TRUE engine state -- the opponent's hidden hand, cycle, exact elixir and
any play it has already committed (pending) included -- none of which the live bot can see. The self-model opponent
is the only deliberate information limit. A gain here is an UPPER bound on what the same search gets from a belief
state; a null here is strong evidence against the approach.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
import time
import zlib
from pathlib import Path
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "icebow" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline import e1_eval as E                                                   # noqa: E402
from pipeline.decision_options import match_kwargs as decision_match_kwargs         # noqa: E402

GEN_CKPT = "icebow/data/pipeline/gen_v1_s0/gen_s0.pt"
S1_CKPT = "icebow/data/pipeline/s1_icebow_v6aug_s1.pt"
CENSUS = "scratchpad/gauntlet/L68/selfplay/loadable_decks.json"
ARMS = ("plain", "search", "force_play", "random", "never")
ROLLOUT_SELF = ("idle", "policy")      # our side inside a fork after its candidate: nothing (S0) / its live rule
TAU_PLAIN, TAU_OPP = 0.35, 0.27
CROWN_W = 1.0
SCORERS = ("v1", "v2")                  # --scorer: v1 = the ported Scorer; v2 = board value x current HP x position
ARENA_PRINCESS_Y = (117000.0, 459000.0)  # RoyaleSim princess-tower y, team 0 / 1 (engine frame, symmetric about 288000)
POS_HALF = 0.5                          # v2 position factor = 1 -+ POS_HALF (own princess line .. enemy princess line)
BOARD_CAP = 1.0                         # old Scorer: each side's pooled board value capped at one tower fraction
NEVER = 10 ** 9                         # a fork's our-side next_tick: it never decides again
WAIT = {"play": False, "slot": -1, "cell": -1, "why": "search_wait"}
GATE_SKIP = {"play": False, "slot": -1, "cell": -1, "why": "search_gate_skip"}   # --search-min-p: WAIT, no search
NEVER_PLAY = {"play": False, "slot": -1, "cell": -1, "why": "never"}
SHARED_SIDE = ("env", "model", "other", "deck", "ep", "cfg", "entry")   # never copied into a fork
SHARED_ENV = ("core", "eng", "ids", "names", "subs", "_code_names", "elixir_regen_schedule", "_elixir")


# ------------------------------------------------------------------------------------------------------
# the ported Scorer
# ------------------------------------------------------------------------------------------------------
class Scorer:
    """``clashrl.sim.rollout_search.Scorer`` on RoyaleSim states (mapping: module docstring). ``us`` = our team."""

    def __init__(self, catalogue, *, tower_level: int, card_level: int, crown_w: float = CROWN_W, db=None,
                 version: str = "v1"):
        from clashrl import threat_value as TV
        from clashrl.cards import shared
        from pipeline.dataset_gen import card_key
        self.TV, self.db = TV, (db if db is not None else shared())
        self.cards = {c.card_id: c for c in catalogue}
        self.base = {c.card_id: card_key(c.name) for c in catalogue}
        self.crown_w, self.tower_level, self.card_level = float(crown_w), int(tower_level), int(card_level)
        self.princess_hp = float(TV.tower_hp(self.tower_level))   # threat_value's unit = the tower term's unit
        self._finite: dict = {}
        self._ref: dict = {}
        if version not in SCORERS:
            raise ValueError(f"scorer {version!r} not in {SCORERS}")
        self.version = version
        self._yline: dict = {}           # v2: team -> its princess-tower y (engine frame), first seen

    def ylines(self, st) -> dict:
        """v2: each team's princess-tower y line, cached from the first state showing BOTH of that team's princess
        towers at one y; until then the engine's fixed arena line ARENA_PRINCESS_Y (never a king tower's y)."""
        from royalegym.protocol import EntityKind
        for team in (0, 1):
            if team not in self._yline:
                ys = {float(e.y) for e in st.entities if e.team == team and e.kind == EntityKind.PRINCESS_TOWER}
                n = sum(1 for e in st.entities if e.team == team and e.kind == EntityKind.PRINCESS_TOWER)
                if n == 2 and len(ys) == 1:
                    self._yline[team] = ys.pop()
        return {t: self._yline.get(t, ARENA_PRINCESS_Y[t]) for t in (0, 1)}

    def unit_mult(self, e, yl: dict) -> float:
        """v2 per-body multiplier: hp_frac x position factor (module docstring)."""
        hp = min(1.0, max(0.0, float(e.hp)) / max(1.0, float(e.max_hp)))
        own, opp = yl[e.team], yl[1 - e.team]
        t = min(1.0, max(0.0, (float(e.y) - own) / (opp - own)))
        return hp * (1.0 - POS_HALF + 2.0 * POS_HALF * t)

    def _has_finite_ignore(self, base: str) -> bool:
        v = self._finite.get(base)
        if v is None:
            try:
                v = math.isfinite(self.TV.ignore_cost_frac(self.db, base, tower_level=self.tower_level,
                                                             enemy_level=self.card_level))
            except Exception:           # noqa: BLE001 -- an unknown card is never ignorable (old Scorer)
                v = False
            self._finite[base] = v
        return v

    def board_value(self, st, team: int) -> float:
        from royalegym.protocol import EMPTY_CARD, EntityKind
        v2 = self.version == "v2"
        yl = self.ylines(st) if v2 else None
        finite, wm, extra = [], [], 0.0
        for e in st.entities:
            if e.team != team or e.hp <= 0 or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING) \
                    or e.card_id == EMPTY_CARD:
                continue
            b = self.base.get(e.card_id)
            m = self.unit_mult(e, yl) if v2 else 1.0
            c = self.cards[e.card_id]
            if b and self._has_finite_ignore(b):
                finite.append(b)
                wm.append((float(c.elixir) / max(1, int(c.count)), m))
            else:                                                    # v1: m = 1.0, so x * m == x exactly
                extra += (float(c.elixir) / max(1, int(c.count))) * self.TV.ELIXIR_TO_TOWER * m
        v = 0.0
        if finite:
            v = float(self.TV.bodies_ignore_frac(self.db, finite, tower_level=self.tower_level,
                                                 enemy_level=self.card_level))
            if not math.isfinite(v):
                v = BOARD_CAP
            if v2:
                wsum = sum(w for w, _ in wm)
                v *= sum(w * m for w, m in wm) / wsum if wsum > 0 else sum(m for _, m in wm) / len(wm)
        return min(BOARD_CAP, v + extra)

    def tower_frac(self, st, team: int) -> float:
        """Standing crown-tower HP of ``team`` in units of ONE of its princess towers (old Scorer.tower_frac)."""
        from royalegym.protocol import EntityKind
        tw = [e for e in st.entities if e.team == team and e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)]
        for e in tw:
            if e.kind == EntityKind.PRINCESS_TOWER and team not in self._ref:
                if float(e.max_hp) != self.princess_hp:          # tower term and board term in different units
                    raise ValueError(f"princess max_hp {e.max_hp} != threat_value tower_hp({self.tower_level}) "
                                     f"{self.princess_hp:g}: Scorer tower_level does not match the engine")
                self._ref[team] = max(1.0, float(e.max_hp))
        return sum(max(0.0, float(e.hp)) for e in tw) / self._ref.get(team, 1.0)

    def snapshot(self, st, us: int) -> dict:
        return {"ours": self.tower_frac(st, us), "theirs": self.tower_frac(st, 1 - us),
                "bv0": self.board_value(st, us), "bv1": self.board_value(st, 1 - us),
                "cr0": int(st.players[us].crowns), "cr1": int(st.players[1 - us].crowns)}

    def score(self, s0: dict, s1: dict, spent: float) -> float:
        enemy_destroyed = s0["theirs"] - s1["theirs"]
        ours_lost = s0["ours"] - s1["ours"]
        board = (s1["bv0"] - s1["bv1"]) - (s0["bv0"] - s0["bv1"])
        d_crowns = (s1["cr0"] - s0["cr0"]) - (s1["cr1"] - s0["cr1"])
        return enemy_destroyed - ours_lost - spent * self.TV.ELIXIR_TO_TOWER + board + self.crown_w * d_crowns


def fork_spent(side, n0: int) -> float:
    """Elixir ``side`` spent in a fork: the catalogue cost of every play ACCEPTED after its first ``n0`` play records
    (candidate + any follow-ups; refused / unlanded plays cost nothing)."""
    return float(sum(side.costs[r["slot"]] for r in side.plays[n0:] if r["accepted"]))


def engine_tower_level(st) -> int:
    """The crown-tower level of a RoyaleSim state: every PRINCESS max_hp mapped through levels.PRINCESS_HP, every KING
    max_hp through KING_HP; all must agree on ONE level (ValueError otherwise, or if any value is not in the table)."""
    from clashrl import levels
    from royalegym.protocol import EntityKind
    lv = set()
    for e in st.entities:
        tbl = {EntityKind.PRINCESS_TOWER: levels.PRINCESS_HP, EntityKind.KING_TOWER: levels.KING_HP}.get(e.kind)
        if tbl is None:
            continue
        hit = [i for i, v in enumerate(tbl) if i and v == int(e.max_hp)]
        if len(hit) != 1:
            raise ValueError(f"{EntityKind(e.kind).name} max_hp {e.max_hp} matches no single level in clashrl.levels")
        lv.add(hit[0])
    if len(lv) != 1:
        raise ValueError(f"crown towers disagree on (or show no) level: {sorted(lv)}")
    return lv.pop()


def make_scorer(env, version: str = "v1") -> Scorer:
    """The Scorer at the ENGINE's tower and card levels (never a hard-coded one)."""
    return Scorer(env.core.cards(), tower_level=engine_tower_level(env.core.state()),
                  card_level=int(env.core.card_level), version=version)


def choose(wait_score: float, scores) -> int:
    """Index of the best candidate, -1 = WAIT. Strict improvement over WAIT required: ties -> WAIT; among equal
    candidates the first (the policy's higher-ranked) wins."""
    best, best_s = -1, float(wait_score)
    for i, s in enumerate(scores):
        if s > best_s:
            best, best_s = i, s
    return best


def tower_hp(st, team: int) -> int:
    from royalegym.protocol import EntityKind
    return int(sum(max(0, e.hp) for e in st.entities
                   if e.team == team and e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)))


# ---- --habit-log (owner 10-17 live observations; MEASUREMENT ONLY, the decisions are never touched) -----------------
# Board y, me at the bottom, 0..1 (engine_play.cell_center): live offensive X-Bows sit at 0.609 (lattice row 39, 19.5
# tiles: the bridge lock row, reaching the enemy princess), defensive ones at 0.67-0.70 (rows 43-45); the cut is between.
XBOW_BRIDGE_Y = 0.64
LATE_TICK = 2400                        # double elixir (120 s): the "late stage"


def _slug(name) -> str:
    import re
    return re.sub(r"[^a-z]", "", str(name).split("@")[0].lower())


def habit_board(bs) -> dict:
    """What our Rocket decision saw (its BoardState, my frame): enemy princesses (L, R) alive / hp_frac, enemy bodies."""
    from pipeline.decision_options import enemy_body_tiles
    return {"alive": [bool(t.alive) for t in bs.towers[4:6]], "hp": [t.hp_frac for t in bs.towers[4:6]],
            "bodies": enemy_body_tiles(bs)}


def habits(m) -> dict:
    """--habit-log: the learner's play habits in one match, from its ACCEPTED plays (cell = the decided cell, my frame):
    X-Bow in the opening hand (the deal's first four); the first two plays and whether an OFFENSIVE X-Bow (board y <
    XBOW_BRIDGE_Y) is among them; Rockets whose blast covers an ALIVE enemy princess at the decision (catalog Rocket
    radius + tower radius, rocket_target_cells' rule) -- of them the strictly lower-HP (or only) alive princess, and with no enemy
    body in the blast (pure tower chip); Rockets / Logs the finisher rule forced (why lethal_rocket / lethal_log); late
    (landing tick >= LATE_TICK) offensive X-Bows, Rockets, Rockets on a princess, Tornados (all / centre on the enemy half)."""
    from pipeline.decision_options import (ENEMY_TOWERS_TILES, ROCKET_BODY_SLACK_TILES, cell_centres_tiles, is_xbow,
                                           rocket_radius_tiles)
    from pipeline.public_geometry import constants
    side = m.learner
    xs, ys = cell_centres_tiles(side.cfg["grid"])
    r_tower = rocket_radius_tiles() + constants()["tower_radius"]["PrincessTower"] / 1000.0
    r_body = rocket_radius_tiles() + ROCKET_BODY_SLACK_TILES
    plays = [q for q in side.plays if q["accepted"]]
    h = {k: 0 for k in ("xbow", "xbow_off", "rocket", "rocket_princess", "rocket_princess_lower", "rocket_princess_bodyless",
                        "rocket_lethal", "log_lethal", "tornado")}
    late = {k: 0 for k in ("xbow_off", "rocket", "rocket_princess", "tornado", "tornado_enemy_half")}
    xbow_y, first2, off_first2 = [], [], False
    for i, q in enumerate(plays):
        x, y, card = float(xs[q["cell"]]), float(ys[q["cell"]]), _slug(q["card"])
        is_late = int(q.get("land_tick", q["tick"])) >= LATE_TICK
        if i < 2:
            first2.append(card)
        if is_xbow(q["card"]):
            off = y / 32.0 < XBOW_BRIDGE_Y
            h["xbow"] += 1
            h["xbow_off"] += off
            late["xbow_off"] += off and is_late
            xbow_y.append(round(y / 32.0, 4))
            off_first2 |= i < 2 and off
        elif card == "rocket":
            b = m.habit_dec.get(int(q["tick"]))
            on = [math.hypot(x - tx, y - ty) <= r_tower and (b is None or b["alive"][j])
                  for j, (tx, ty) in enumerate(ENEMY_TOWERS_TILES[1:])]
            h["rocket"] += 1
            h["rocket_lethal"] += q["why"] == "lethal_rocket"
            late["rocket"] += is_late
            if any(on):
                h["rocket_princess"] += 1
                late["rocket_princess"] += is_late
                if b is not None:            # lower = the only alive princess, or the strictly lower-HP one (a tie: none)
                    hp = {j: 1.0 if v is None else float(v) for j, (v, a) in enumerate(zip(b["hp"], b["alive"])) if a}
                    low = min(hp, key=hp.get) if len(hp) == 1 or (len(hp) == 2 and hp[0] != hp[1]) else None
                    h["rocket_princess_lower"] += low is not None and on[low]
                    h["rocket_princess_bodyless"] += not any(math.hypot(x - bx, y - by) <= r_body for bx, by in b["bodies"])
        elif card == "tornado":
            h["tornado"] += 1
            late["tornado"] += is_late
            late["tornado_enemy_half"] += is_late and y / 32.0 < 0.5
        elif card in ("log", "thelog"):
            h["log_lethal"] += q["why"] == "lethal_log"
    return {"xbow_open_hand": any(is_xbow(n) for n in m.env.deal[side.side][:4]), "first2": first2,
            "xbow_off_first2": bool(off_first2), **h, "late": late, "xbow_y": xbow_y}


# ---- --record-board (W22 ape_score.py; MEASUREMENT ONLY, the decisions are never touched) ---------------------------
# Ported from the L74/habits/pod copy's HABITS_REC record (same 'hab' format): both sides' plays at engine x,y and a 1-s
# sample of the learner's board (towers, enemy bodies, own X-Bows). Engine millitiles, not mirrored.
HAB_EVERY = 20


def hab_sample(m, s) -> list:
    """[tick, opp truth, counter now (true counter), model's opp input, own elixir, towers [side, type, x, y, hp],
    enemy bodies [uid, name, hp, max_hp, x, y], own X-Bows [uid, hp, x, y]] (engine millitiles)."""
    tick, bs, view = s._cur
    raw = s.state
    pub = s.public
    est = getattr(pub, "_hab_est", pub.estimate_at)(tick) if pub is not None else None
    tw = [[t["side"], t["type"][0], round(t["x"], 1), round(t["y"], 1), int(t["hp"])]
          for t in raw["episode"]["crown_towers"]]
    en = [[e["entity_id"], e["name"], int(e["hp"]), int(e["max_hp"]), round(e["x"], 1), round(e["y"], 1)]
          for e in raw["entities"] if e["side"] != s.side]
    xb = [[e["entity_id"], int(e["hp"]), round(e["x"], 1), round(e["y"], 1)]
          for e in raw["entities"] if e["side"] == s.side and str(e["name"]).lower().replace("-", "") == "xbow"]
    return [int(tick), None if bs.opp_elixir is None else round(float(bs.opp_elixir), 3),
            None if est is None else round(float(est), 3), None if view.opp_elixir is None else round(float(view.opp_elixir), 3),
            round(float(bs.my_elixir), 3), tw, en, xb]


def hab_plays(side) -> list:
    """[decision tick, landing tick, card, accepted, why, elixir seen, cell x, cell y (my frame 0..1), engine X, Y]."""
    out = []
    for q in side.plays:
        X, Y = side.ep.cell_to_engine(q["cell"], side.mirror, side.cfg["grid"])
        x, y = side.ep.cell_center(q["cell"], side.cfg["grid"])
        out.append([int(q["tick"]), int(q.get("land_tick", q["tick"])), q["card"], bool(q["accepted"]), q["why"],
                    q["elixir_exact"], round(float(x), 2), round(float(y), 2), X, Y])
    return out


# ------------------------------------------------------------------------------------------------------
# forking
# ------------------------------------------------------------------------------------------------------
def fork_into(m, env2, blob: bytes, fresh: tuple = ()):
    """A copy of SelfPlayMatch ``m`` on the pooled env ``env2``: engine = ``blob`` (m.env.core.save_state()), env python
    fields and both sides' python state deep-copied; models / cfg / deck / modules shared. -> a SelfPlayMatch.
    ``fresh``: side attributes started EMPTY in the fork instead of copied (rl_royale cf_credit: the record ``traj``,
    which no decision reads and which grows to hundreds of rows)."""
    env = m.env
    for k, v in env.__dict__.items():
        if k not in ("core", "eng"):
            env2.__dict__[k] = v if k in SHARED_ENV else copy.deepcopy(v)
    env2.eng.last_episode = copy.deepcopy(env.eng.last_episode)
    if getattr(env2, 'behaviour_telemetry', None) is not None:
        env2.behaviour_telemetry = None  # hypothetical forks are not acceptance plays
    env2.core.load_state(blob)
    f = object.__new__(type(m))
    f.env, f.spec = env2, m.spec
    new = {}
    for s in (m.learner, m.opp):
        c = object.__new__(type(s))
        c.__dict__.update({k: (v if k in SHARED_SIDE else type(v)() if k in fresh else copy.deepcopy(v))
                           for k, v in s.__dict__.items()})
        c.env = env2
        new[id(s)] = c
    f.learner, f.opp = new[id(m.learner)], new[id(m.opp)]
    f.learner.other, f.opp.other = f.opp, f.learner
    f.sides = sorted((f.learner, f.opp), key=lambda s: s.side)
    return f


# ------------------------------------------------------------------------------------------------------
# the runner
# ------------------------------------------------------------------------------------------------------
def live_cfg(tau: float, grid: str, device: str = "cpu") -> dict:
    """The measured live condition (rl_royale.yaml keys + noise_off=all, counter, delay 26, extrapolate 26)."""
    return {"policy": "live", "tau": float(tau), "afford_mask": True, "stall_elixir": E.STALL_ELIXIR_LIVE, "stall_seconds": E.STALL_SECONDS_LIVE,
            "obs": "live", "noise": E.parse_noise_off(",".join(E.NOISE_NAMES)), "p_random": 0.0,
            "random_hand_only": False, "grid": grid, "device": device, "decide_every": 10, "slot": 0, "port": 0,
            "T": 0.5, "record": False, "opp_elixir": "counter", "action_delay_ticks": 26, "extrapolate_ticks": 26}


def forward(s):
    """(p, enc, heads, hand) for ONE prepared side under its own model -- run_selfplay_batch's per-group forward."""
    model = s.model
    if isinstance(model, E.GenPolicy):
        enc, heads, p, hand = model.forward_batch([s.gen_row(model)], s.cfg["device"])
    else:
        enc, heads, p, hand = E.model_forward_batch(model, *zip(*[s._obs]), device=s.cfg["device"])
    return p[0], enc, heads, hand[0]


def shortlist(model, enc, heads, allowed: np.ndarray, topk: int, cells: int) -> list[dict]:
    """PLAY candidates: top ``topk`` allowed deck slots by the hand-masked card logits x top ``cells`` cells each."""
    import torch
    with torch.no_grad():
        logits = heads["card"][0]
        logits = logits.masked_fill(~torch.from_numpy(np.asarray(allowed, bool)).to(logits.device), float("-inf"))
        order = [int(i) for i in torch.argsort(logits, descending=True).tolist() if allowed[int(i)]][:topk]
        out = []
        for slot in order:
            cl = model.cell_logits(enc, torch.tensor([slot], device=logits.device))[0]
            out += [{"play": True, "slot": slot, "cell": int(c), "why": "search"}
                    for c in torch.topk(cl, cells).indices.tolist()]
    return out


# ------------------------------------------------------------------------------------------------------
# W18 P-D payoff probe (--probe-xbow-start ARM; SIM-only measurement, opponent-model work): every match starts at a live
# Ranked bridge-X-Bow state (rl_royale.draw_xbow_start's table) with OUR X-Bow forced at its live point; the opponent's FIRST
# decision is scripted per ARM, both policies play on, the match stops 12 s (240 ticks) later. ARM:
#   policy  the opponent's own answer (its deck's building dealt into its hand, so the option exists)
#   bfront / bnear  its deck's BUILDING at the tower front (9.5 tiles from our X-Bow) / 6 tiles from it (just past the river)
#   tfront / tnear  its CHEAPEST GROUND TROOP there (the troop dealt into its hand instead)
# Opponent decks are redrawn (seeded) until they hold a building AND a ground troop, so every arm plays the same deck / state.
# ------------------------------------------------------------------------------------------------------
PROBE_ARMS = ("policy", "bfront", "bnear", "tfront", "tnear")
PROBE_TICKS = 240
PROBE_FRONT_TILES, PROBE_NEAR_TILES = 9.5, 6.0
PROBE_AIR = {"minions", "minionhorde", "bats", "megaminion", "babydragon", "infernodragon", "balloon", "lavahound",
             "skeletondragons", "electrodragon", "phoenix", "flyingmachine", "skeletonballoon"}


def _norm(n) -> str:
    return "".join(ch for ch in str(n).split("@")[0].lower() if ch.isalnum())


def probe_cards(env, deck_names) -> tuple:
    """(building, cheapest ground troop) engine names of a deck (None when absent), from the engine's own catalogue."""
    if not hasattr(env, "_probe_kinds"):
        env._probe_kinds = {int(c.card_id): (str(c.card_kind).upper(), float(c.elixir)) for c in env.core.cards()}
    b = t = None
    for n in deck_names:
        try:
            k = env._probe_kinds.get(env.card_id(str(n).split("@")[0]))
        except (KeyError, ValueError):
            k = None
        if k is None:
            continue
        if "BUILDING" in k[0] and b is None:
            b = str(n).split("@")[0]
        elif "TROOP" in k[0] and _norm(n) not in PROBE_AIR and (t is None or k[1] < t[1]):
            t = (str(n).split("@")[0], k[1])
    return b, (t[0] if t else None)


def probe_spec(spec: dict, seed: int, arm: str, card) -> dict:
    """The live X-Bow start for OUR side (the learner here = icebow) + the card the opponent gets in hand."""
    from pipeline.rl_royale import draw_xbow_start
    st = draw_xbow_start(1.0, f"probe:{int(seed)}")
    xb = st["force"]["board"]
    ox, oy = 18.0 * (1.0 - xb[0]), 32.0 * (1.0 - xb[1])    # our X-Bow in the OPPONENT's own (rotated) frame, tiles
    dist = PROBE_FRONT_TILES if arm.endswith("front") else PROBE_NEAR_TILES
    spec["start"] = {"tick": st["tick"], "row": st["row"], "learner": dict(st["opp"]), "opp": dict(st["learner"]),
                     "force": {"card": "Xbow", "board": xb, "side": "learner"}, "hand": {"opp": card}}
    spec["probe"] = {"arm": arm, "card": card, "row": st["row"],
                     "target_tiles": None if arm == "policy" else [round(ox, 2), round(oy + dist, 2)]}
    return spec


def probe_towers(env, side: int) -> dict:
    """{engine x: (hp, max_hp)} of ``side``'s princess towers now."""
    st = env.core.state()
    return {int(e.x): (int(e.hp), int(e.max_hp)) for e in st.entities if e.tower_slot in (1, 2) and int(e.team) == side}


def probe_decision(s, target_tiles, card) -> dict:
    """The scripted first decision of the opponent side ``s``: ``card`` at the cell nearest ``target_tiles`` (its own frame)."""
    from pipeline import engine_play as ep
    from pipeline.model_v3 import GRID_X, GRID_Y
    slot = s.deck.slot_of(E.vocab.engine_key(card))
    tx, ty = target_tiles[0] / 18.0, target_tiles[1] / 32.0
    cell = min(range(GRID_X * GRID_Y), key=lambda c: (ep.cell_center(c, s.cfg["grid"])[0] - tx) ** 2
               + (ep.cell_center(c, s.cfg["grid"])[1] - ty) ** 2)
    return {"play": True, "slot": int(slot), "cell": int(cell), "why": "probe"}


class Runner:
    """Plays one (arm, opponent, seed) match. ``learner`` = our policy (also the rollout self-model of the opponent);
    ``opps`` = {id: (policy, cfg)}; ``make_env()`` -> RoyaleSelfPlayEnv."""
    probe_xbow_focus = False    # --probe-xbow-focus (SIM-only measurement probe, owner 2026-10-15); False = unchanged

    def __init__(self, learner, opps: dict, learner_cfg: dict, make_env, *, horizon_s: float = 12.0,
                 interval: int = 1, topk: int = 4, cells: int = 3, scorer: Optional[Scorer] = None,
                 search_min_p: float = 0.0, rollout_self: str = "idle", scorer_version: str = "v1"):
        self.learner, self.opps, self.lcfg, self.make_env = learner, opps, learner_cfg, make_env
        self.dev = learner_cfg["device"]                  # our policy AND the rollout self-model's forwards
        self.search_min_p = float(search_min_p)
        if rollout_self not in ROLLOUT_SELF:
            raise ValueError(f"rollout_self {rollout_self!r} not in {ROLLOUT_SELF}")
        self.rollout_self = rollout_self
        self.H = int(round(float(horizon_s) / E.TICK_S))
        self.interval, self.topk, self.cells = max(1, int(interval)), int(topk), int(cells)
        for oid, (_, oc) in opps.items():
            if oc["grid"] != learner_cfg["grid"]:    # a pending opponent play would land in the wrong grid in a fork
                raise ValueError(f"opponent {oid} grid {oc['grid']} != self-model grid {learner_cfg['grid']}")
        self.pool: list = []
        self.scorer = scorer
        if scorer_version not in SCORERS:
            raise ValueError(f"scorer {scorer_version!r} not in {SCORERS}")
        self.scorer_version = scorer_version

    def _pool(self, n: int) -> list:
        while len(self.pool) < n:
            self.pool.append(self.make_env())
        return self.pool[:n]

    # -- rollouts --------------------------------------------------------------------------------------
    def rollout_scores(self, m, ds, cands: list[dict], p: float) -> tuple[float, list[float]]:
        """Score WAIT and every candidate by one lockstep rollout from ``m``'s current (prepared) state; ``ds`` = the
        sides deciding now. -> (wait score, [candidate scores]). Leaves ``m`` untouched."""
        from pipeline.e1_eval import live_decide_batch
        env, L = m.env, m.learner.side
        if self.scorer is None:
            self.scorer = make_scorer(env, self.scorer_version)
        blob = env.core.save_state()
        acts = [WAIT] + cands
        forks = [fork_into(m, e2, blob) for e2 in self._pool(len(acts))]
        s0 = self.scorer.snapshot(env.core.state(), L)
        cap = min(env.tail_cap, int(env.tick) + self.H)
        ocfg = {**m.opp.cfg, "policy": "live", "tau": TAU_OPP, "grid": self.lcfg["grid"], "device": self.dev}
        n0 = len(m.learner.plays)                                 # the candidate's record index in every fork
        for f, a in zip(forks, acts):
            f.env.tail_cap = cap
            f.opp.model, f.opp.cfg = self.learner, ocfg
            f.learner.apply(p, a)
            if self.rollout_self == "idle":
                f.learner.next_tick = NEVER                       # S0: our side makes no further plays
            # "policy": our side keeps its next_tick, model (gen_v1_s0) and cfg (the plain arm's live rule, tau 0.35)
        first = [f.opp for f in forks] if m.opp in ds else []     # the opponent decides at the root too: self-model
        active = list(forks)
        while True:
            due, first = first, []
            if not due:
                for f in list(active):
                    got = f.due()
                    if got:
                        due += got
                    else:
                        active.remove(f)
                if not due:
                    break
                for s in due:
                    s.prepare()
            # one batched forward + decide PER ROLE across forks (opponent self-model at tau 0.27; with --rollout-self
            # policy, our side at its own cfg tau); decide all, then apply in due order (run_selfplay_batch's order)
            todo = {}
            for role in (1 - L, L):
                sides = [s for s in due if s.side == role]
                if not sides:
                    continue
                enc, heads, pp, hand = self.learner.forward_batch([s.gen_row(self.learner) for s in sides], self.dev)
                pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
                dec = live_decide_batch(self.learner, enc, heads, pp, np.stack([x[1] for x in pre]),
                                        np.array([x[2] for x in pre], dtype=bool), tau=sides[0].cfg["tau"],
                                        device=self.dev, **decision_match_kwargs(sides))
                todo.update({id(s): (pp[r], dec[r]) for r, s in enumerate(sides)})
            for s in due:
                s.apply(*todo[id(s)])
        self.last_forks = forks                                   # kept for inspection (tests)
        out = []
        for f, a in zip(forks, acts):
            out.append(self.scorer.score(s0, self.scorer.snapshot(f.env.core.state(), L), fork_spent(f.learner, n0)))
        return out[0], out[1:]

    # -- one match -------------------------------------------------------------------------------------
    def setup(self, opp_id: str, seed: int, opp_deck: list, tag: Optional[str] = None):
        spec = {"tag": tag or f"s0:{opp_id}:{seed}", "opp": {"id": opp_id}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
                "opp_deck": list(opp_deck), "learner_side": int(seed) % 2, "seed": int(seed)}
        rates = getattr(self, "opp_tower_troops", None)      # L74 troops (--opp-tower-troops); None = no key (unchanged)
        if rates is not None:
            from pipeline.rl_royale import draw_tower_troop
            spec["opp_tower"] = draw_tower_troop(rates, f"{int(seed)}:{','.join(map(str, opp_deck))}")
        table = getattr(self, "live_levels", None)           # L74 factor D (--live-levels); None = no key (unchanged)
        if table is not None:                                # drawn per (seed, opponent deck): paired across checkpoints
            from pipeline.rl_royale import draw_live_levels
            spec["levels"] = draw_live_levels(table, spec["learner_deck"], spec["opp_deck"],
                                              f"{int(seed)}:{','.join(map(str, opp_deck))}")
        opp, ocfg = self.opps[opp_id]
        probe = getattr(self, "probe", None)                 # W18 P-D (--probe-xbow-start); None = unchanged
        if probe is None:
            return E.SelfPlayMatch(self.make_env(), spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0},
                                   self.learner, opp)
        env = self.make_env()
        b, t = probe_cards(env, opp_deck)
        if b is None or t is None:
            raise E.UnsupportedProbeDeck(f"probe needs a building and a ground troop: {list(opp_deck)}")
        probe_spec(spec, seed, probe, t if probe.startswith("t") else b)
        m = E.SelfPlayMatch(env, spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0}, self.learner, opp)
        m.probe = dict(spec["probe"], t0=int(env.tick), towers0=probe_towers(env, m.opp.side), answered=None)
        env.tail_cap = int(env.tick) + PROBE_TICKS
        return m

    def play(self, arm: str, m, deadline: Optional[float] = None) -> dict:
        if arm not in ARMS:
            raise ValueError(f"arm {arm!r} not in {ARMS}")
        rng = random.Random(zlib.crc32(f"{m.spec['tag']}:s0random".encode()))
        st = {"eligible": 0, "searched": 0, "unsearched": 0, "gate_skipped": 0, "search_s": 0.0, "overrides": 0,
              "chose_wait": 0, "plain_wait_overridden": 0, "moved_cell": 0, "n_cands": 0}
        if self.probe_xbow_focus:   # the match row shows the probe ran: our X-Bow decisions seen / cells it moved
            st.update(probe_xbow_focus_xbows=0, probe_xbow_focus_changed=0)
        if getattr(self, "habit_log", False):
            m.habit_dec = {}        # --habit-log: decision tick -> the board our Rocket decisions saw (habit_board)
        if getattr(self, "record_board", False):
            m.hab_samples = []      # --record-board: 1-s board samples (hab_sample)
        t0, truncated = time.perf_counter(), False
        while True:
            if deadline is not None and time.time() > deadline:
                truncated = True
                break
            ds = m.due()
            if not ds:
                break
            self.round(m, ds, arm, st, rng)
        env = m.env
        r = self.last_result = m.result()
        cst = env.core.state()
        L = m.learner.side
        hp_for, hp_against = tower_hp(cst, L), tower_hp(cst, 1 - L)
        return {"arm": arm, "opp": m.spec["opp"]["id"], "seed": int(m.spec["seed"]), "tag": m.spec["tag"],
                "learner_side": L, "opp_deck": m.spec["opp_deck"], "outcome": r["outcome"],
                **({"opp_tower": m.spec["opp_tower"]} if "opp_tower" in m.spec else {}),
                **({"levels": m.spec["levels"]} if "levels" in m.spec else {}),
                "crowns_for": r["crowns_for"], "crowns_against": r["crowns_against"],
                "crowns_diff": r["crowns_for"] - r["crowns_against"],
                "tower_hp_for": hp_for, "tower_hp_against": hp_against, "tower_hp_diff": hp_for - hp_against,
                "device": self.dev, "search_min_p": self.search_min_p, "rollout_self": self.rollout_self,
                "end_tick": r["end_tick"], "tail_cap": int(env.tail_cap), "wall_truncated": truncated,
                "plays_attempted": r["plays_attempted"], "plays_accepted": r["plays_accepted"],
                "opp_plays_accepted": r["opp_side"]["plays_accepted"], "decisions": r["decisions"],
                **({"plays_tap_lost": r["plays_tap_lost"]} if "plays_tap_lost" in r else {}),   # --tap-loss (W18)
                **({"plays_tap_slow": r["plays_tap_slow"]} if "plays_tap_slow" in r else {}),   # --tap-slow (W18)
                **({"plays_tap_held": r["plays_tap_held"]} if "plays_tap_held" in r else {}),   # --tap-hold (RECON-7)
                **st, "search_s": round(st["search_s"], 2),
                "s_per_searched": round(st["search_s"] / st["searched"], 3) if st["searched"] else None,
                **({k: r[k] for k in ("hero_abilities", "ability_presses", "ability_policy", "ability_fallback_generic",
                                      "ability_deployments") if k in r} if "hero_abilities" in r else {}),
                **({'behaviour': r['behaviour']} if 'behaviour' in r else {}),
                **({'public_lookahead_counts': r['public_lookahead_counts']} if 'public_lookahead_counts' in r else {}),
                **({k: r[k] for k in ("forms_mode", "form_fallbacks")} if "forms_mode" in r else {}),
                **{k: r[k] for k in ("ability_head", "ability_stats") if k in r},   # B6 / --ability-stats
                **self.posture_fields(m.learner),
                **({"probe": self.probe_row(m)} if getattr(m, "probe", None) is not None else {}),
                "wall_s": round(time.perf_counter() - t0, 1)}

    @staticmethod
    def probe_row(m) -> dict:
        """W18 P-D: the opponent's princess HP lost over the 12 s (the X-Bow's lane and all), the forced X-Bow, the answer."""
        from pipeline import engine_play as ep
        pr = m.probe
        X, _ = ep.board_to_engine(*m.spec["start"]["force"]["board"], m.learner.mirror)
        a, b = pr["towers0"], probe_towers(m.env, m.opp.side)
        lane = min(a, key=lambda x: abs(x - X)) if a else None
        lost = lambda x: max(0, a[x][0] - b.get(x, (0, a[x][1]))[0]) / max(1, a[x][1])  # noqa: E731
        return {"arm": pr["arm"], "card": pr["card"], "row": pr["row"], "target_tiles": pr["target_tiles"],
                "forced": m.forced, "answered": pr["answered"], "ticks": int(m.env.tick) - pr["t0"],
                "lane_lost": round(lost(lane), 4) if lane is not None else None,
                "towers_lost": round(sum(lost(x) for x in a), 4),
                "answer_accepted": any(p.get("why") == "probe" and p["accepted"] for p in m.opp.plays)}

    @staticmethod
    def posture_fields(side) -> dict:
        """C1 (a checkpoint with a posture head, ``_init_worker``): our decisions' share under each posture (argmax) and
        the number of choices; {} without a posture (the match line unchanged)."""
        c = getattr(side, "posture_counts", None)
        if c is None:
            return {}
        from pipeline.rl_royale import POSTURES
        n = sum(c)
        return {"posture_shares": {k: round(v / n, 4) for k, v in zip(POSTURES, c)}, "posture_decisions": n,
                "posture_choices": int(getattr(side, "posture_choices", 0))}

    def round(self, m, ds, arm: str, st: dict, rng: random.Random) -> None:
        """One round of run_selfplay_batch for one match (prepare all, decide each on its own model, apply in side
        order), with our side's decision replaced per ``arm``."""
        from pipeline.e1_eval import live_decide_batch
        rb = getattr(self, "record_board", False)
        for s in ds:
            s.prepare()
            if rb and s is m.learner and (not m.hab_samples or s._cur[0] - m.hab_samples[-1][0] >= HAB_EVERY):
                m.hab_samples.append(hab_sample(m, s))       # --record-board: read only
        todo = []
        for s in ds:
            p, enc, heads, hand = forward(s)
            _, allowed, stalled = s.pre(hand)
            if s.cfg.get("policy") == "sample":   # --opp-policy sample (lead 2026-10-08); --learner-policy sample (10-13)
                d = E.sample_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), [s], s.cfg)[0]
            else:                                 # rl_royale C1: posture_live (no cfg posture = tau / kwargs unchanged)
                E.ability_decide([s], enc, s.cfg)  # rl_royale B6: greedy learned press (no cfg ability = no-op)
                tau, kw = E.posture_live([s], enc, s.cfg, s.cfg["tau"], decision_match_kwargs([s]))
                d = live_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), tau=tau,
                                      device=s.cfg["device"], **kw)[0]
            pr = getattr(m, "probe", None)
            if pr is not None and s is m.opp and pr["answered"] is None:   # W18 P-D: the opponent's first decision
                pr["answered"] = False
                if pr["arm"] != "policy" and bool(allowed[s.deck.slot_of(E.vocab.engine_key(pr["card"]))]):
                    d = probe_decision(s, pr["target_tiles"], pr["card"])
                    pr["answered"] = True
            if s is m.learner and self.probe_xbow_focus and d["play"]:
                d = self.probe_xbow(s, enc, d, st)
            if s is m.learner and arm == "never":
                d = NEVER_PLAY                              # our side never plays (stall rule included)
            elif s is m.learner and arm != "plain" and allowed.any():
                st["eligible"] += 1
                if (st["eligible"] - 1) % self.interval == 0:
                    d = self.arm_decide(m, ds, arm, p, enc, heads, allowed, d, st, rng, stalled=bool(stalled))
                else:
                    st["unsearched"] += 1                   # off-interval: the plain decision stands
            if hasattr(m, "habit_dec") and s is m.learner and d["play"] and _slug(s.deck.cards[d["slot"]]) == "rocket":
                m.habit_dec[int(s._cur[0])] = habit_board(s._cur[1])   # --habit-log: read only, the decision unchanged
            todo.append((s, p, d))
        for s, p, d in todo:
            s.apply(p, d)

    def probe_xbow(self, s, enc, d: dict, st: dict) -> dict:
        """--probe-xbow-focus on our decided play (decision_options.probe_xbow_focus_cell): an offensive X-Bow cell that
        misses the focus enemy princess moves to the model's best cell reaching it. Counts into ``st``."""
        import torch
        from pipeline.decision_options import is_xbow, probe_xbow_focus_cell
        if not is_xbow(s.deck.cards[d["slot"]]):
            return d
        st["probe_xbow_focus_xbows"] += 1
        towers = s._cur[1].towers[3:6]                      # the decision's engine BoardState (my frame): K, L, R
        with torch.no_grad():
            logits = s.model.cell_logits(enc, torch.tensor([d["slot"]], device=s.cfg["device"]))[0]
        cell = probe_xbow_focus_cell(logits, int(d["cell"]), tuple(bool(t.alive) for t in towers),
                                     tuple(t.hp_frac for t in towers[1:]), s.cfg["grid"])
        if cell == int(d["cell"]):
            return d
        st["probe_xbow_focus_changed"] += 1
        return {**d, "cell": cell}

    def arm_decide(self, m, ds, arm, p, enc, heads, allowed, plain: dict, st: dict, rng, stalled: bool = False) -> dict:
        if arm == "search" and p < self.search_min_p and not stalled:
            st["unsearched"] += 1                           # --search-min-p: gate too low -> WAIT without search
            st["gate_skipped"] += 1
            st["overrides"] += int(plain["play"])           # only if tau < p < P: the plain rule would have played
            return GATE_SKIP
        cands = shortlist(self.learner, enc, heads, allowed, self.topk, self.cells)
        st["searched"] += 1
        st["n_cands"] += len(cands)
        t = time.perf_counter()
        if arm == "force_play":
            d = {**cands[0], "why": "force_play"}
        elif arm == "random":
            d = {**rng.choice(cands), "why": "random"}
        else:
            ws, sc = self.rollout_scores(m, ds, cands, p)
            i = choose(ws, sc)
            d = WAIT if i < 0 else cands[i]
            st["chose_wait"] += int(i < 0)
        st["search_s"] += time.perf_counter() - t
        if d["play"] != plain["play"] or (d["play"] and d["slot"] != plain["slot"]):
            st["overrides"] += 1
            st["plain_wait_overridden"] += int(d["play"] and not plain["play"])
        elif d["play"] and d["cell"] != plain["cell"]:
            st["overrides"] += 1
            st["moved_cell"] += 1
        return d


# ------------------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------------------
def opp_deck_for(seed: int, census: list[dict]) -> dict:
    """Seeded census deck (icebow excluded by league_decks), league weights (rl_royale.yaml alpha 0.5 / floor 0.5)."""
    from pipeline.rl_royale import deck_weights
    w = deck_weights([d["sides"] for d in census], 0.5, 0.5)
    return census[int(np.random.default_rng([int(seed), 69]).choice(len(census), p=w))]


_W: dict = {}


def _init_worker(args: dict) -> None:
    import torch
    torch.set_num_threads(max(1, int(args["threads"])))
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline.rl_royale import league_decks
    dev = args["device"]
    gen, gi = E.load_policy(REPO / args["gen"], dev)
    opps = {}
    _W["opp_meta"] = {"opp_gen": args.get("opp_gen") or args["gen"], "opp_gen_sha256": args.get("opp_gen_sha256")}
    if "gen" in args["opps"]:
        og, oi = E.load_policy(REPO / _W["opp_meta"]["opp_gen"], dev)   # its own object (no shared state with ours)
        opps["gen"] = (og, live_cfg(TAU_OPP, oi["grid"], dev))
    if "s1" in args["opps"]:
        s1, si = E.load_policy(REPO / args["s1"], dev)
        opps["s1"] = (s1, live_cfg(TAU_OPP, str(si.get("grid", "floor")), dev))
    if args.get("opp_policy", "live") == "sample":   # lead 2026-10-08: the training league's sampling opponents (T),
        for o in opps.values():                       # so no-stall matches don't freeze in a mutual standoff
            o[1].update(policy="sample", T=float(args["opp_T"]))
    if args.get("opp_decide_every") is not None or args.get("opp_reaction_ticks") is not None:   # L74 human tempo
        opps = {i: (pol, E.opp_tempo(oc, args.get("opp_decide_every"), args.get("opp_reaction_ticks")))
                for i, (pol, oc) in opps.items()}
    if args.get("opp_tau") is not None:                       # L74 W18 probe: the opponent's play / wait threshold
        opps = {i: (pol, {**oc, "tau": float(args["opp_tau"])}) for i, (pol, oc) in opps.items()}
    cap, fm = int(args["tail_cap"]), args.get("forms_mode", "base")
    learner_cfg = live_cfg(args.get('tau_plain', TAU_PLAIN), gi['grid'], dev)
    if args.get('tap_loss'):                                # L74 W18: the live pilot's lost taps on OUR side only
        learner_cfg['tap_loss'] = E.parse_tap_loss(args['tap_loss'])
    if args.get('tap_slow'):                                # L74 W18: the live pilot's slow taps on OUR side only
        learner_cfg['tap_slow'] = E.parse_tap_slow(args['tap_slow'])
    if args.get('tap_hold'):                                # RECON-7: the game's hold of a tap that cannot pay yet, OUR side only
        learner_cfg['tap_hold'] = E.parse_tap_hold(args['tap_hold'])
    if args.get('play_resume'):                             # RECON-7: the next decision right after the engine ran our play (live), OUR side only
        learner_cfg['play_resume'] = args['play_resume']
    if args.get('decision_options'):
        learner_cfg.update(args['decision_options'])
    if args.get('gate_sample'):                             # GATE-SAMPLE: the trainer's sampled gate (match_kwargs)
        learner_cfg['gate_sample'] = float(args['gate_sample'])
    if args.get('learner_policy', 'live') == 'sample':   # 10-13: rl_royale's rollout sampler for OUR side (actor_cfg)
        learner_cfg.update(policy='sample', T=float(args['learner_T']),
                           sample_heads=tuple(args.get('learner_sample_heads', ('gate', 'card', 'cell'))),
                           T_gate=args.get('learner_T_gate'))
    from pipeline.rl_royale import load_posture_head
    gp = REPO / args["gen"]                                 # rl_royale C1: a trained posture head -> argmax posture on
    posture = load_posture_head(gp, dev) if gp.is_file() else None   # our gate (posture_live / sample_decide_batch);
    if posture is not None:                                 # not a file = load_policy was stubbed (tests): no head
        learner_cfg['posture'] = posture
    from pipeline.rl_royale import load_ability_head
    # rl_royale B6: the learned press, greedy. ponytail: only a .pt file is read (the posture test stubs load_policy
    # with a .py path); a head inside a checkpoint of another suffix would be ignored.
    ability = load_ability_head(gp, dev) if gp.is_file() and gp.suffix == ".pt" else None
    if ability is not None:
        if not args.get("hero_abilities"):
            raise ValueError(f"{args['gen']} carries an ability head: run with --hero-abilities (else it never decides)")
        ability['mode'] = args.get('ability_head_decode', 'greedy')   # --ability-head-decode (default greedy)
        learner_cfg['ability'] = ability
    if args.get('behaviour_telemetry'):
        learner_cfg['behaviour_telemetry'] = True
    if args.get('predict_drops'):
        learner_cfg['predict_drops'] = True
    if args.get('own_effects'):
        learner_cfg['own_effects'] = True
    if args.get('spell_log'):                               # rl_royale spell_value's tracker (measurement only)
        learner_cfg['spell_track'] = True
    if args.get('crown_log'):                               # rl_royale crown terms' tracker (read-only, measurement only)
        learner_cfg['crown_track'] = True
    if args.get('pipeline_decisions'):
        learner_cfg['pipeline_decisions'] = True
        if args.get('pipeline_tau_delta'):
            learner_cfg['pipeline_tau_delta'] = float(args['pipeline_tau_delta'])
    _W["record_plays"] = bool(args.get("record_plays"))
    _W["runner"] = Runner(gen, opps, learner_cfg,
                          lambda: RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=cap, forms_mode=fm,
                                                    hero_abilities=args.get("hero_abilities", False),
                                                    ability_policy=args.get("ability_policy", "generic"),
                                                    ability_outcomes=bool(args.get("ability_stats")),
                                                    ability_features=(ability or {}).get("features", "base")),
                          horizon_s=args["horizon"], interval=args["interval"], topk=args["topk"], cells=args["cells"],
                          search_min_p=args["search_min_p"], rollout_self=args.get("rollout_self", "idle"),
                          scorer_version=args.get("scorer", "v1"))
    _W["runner"].probe_xbow_focus = bool(args.get("probe_xbow_focus"))
    if args.get("probe_xbow_start"):                        # W18 P-D payoff probe (SIM-only)
        _W["runner"].probe = args["probe_xbow_start"]
    if args.get("opp_tower_troops") is not None:
        _W["runner"].opp_tower_troops = args["opp_tower_troops"]
    if args.get("live_levels"):                             # L74 factor D: the measured live level table
        from pipeline.rl_royale import live_levels
        _W["runner"].live_levels = live_levels({"league": True, "live_levels": True})
    if args.get("habit_log"):
        _W["runner"].habit_log = True
    if args.get("record_board"):
        _W["runner"].record_board = True
    _W["census"] = league_decks(REPO / args.get("census", CENSUS))


def setup_job(run, census, opp_id: str, seed: int):
    """-> (SelfPlayMatch, opponent deck name) for (opp_id, seed): S1 plays icebow; gen a seeded census deck, redrawn
    deterministically while unloadable or holding a card the generalist never saw. None = no loadable deck."""
    from pipeline.dataset_gen import card_key
    from pipeline.royale_env import UnsupportedDeck
    if opp_id == "s1":
        return run.setup(opp_id, seed, E.ICEBOW_ENGINE_DECK), "icebow"
    for j in range(400 if getattr(run, "probe", None) else 50):    # redraw an unloadable deck, deterministically
        d = opp_deck_for(seed * 1000 + j, census)
        if any(card_key(n) not in run.opps[opp_id][0].gid for n in d["engine"]):
            continue                                               # a card the generalist never saw
        try:
            return run.setup(opp_id, seed, d["engine"]), d["name"]
        except (UnsupportedDeck, KeyError, E.UnsupportedProbeDeck):
            continue
    return None


def _run_job(job: tuple) -> dict:
    arm, opp_id, seed, deadline = job
    if deadline and time.time() > deadline:
        return {"arm": arm, "opp": opp_id, "seed": seed, "skipped": "wall budget"}
    got = setup_job(_W["runner"], _W["census"], opp_id, seed)
    if got is None:
        return {"arm": arm, "opp": opp_id, "seed": seed, "skipped": "no loadable deck"}
    m, name = got
    rec = _W["runner"].play(arm, m, deadline or None)
    rec["opp_deck_name"] = name
    for k in ("pipeline_decisions", "follow_ups"):         # the learner side's mechanism tallies (present only when the mechanism is on)
        if k in _W["runner"].last_result:
            rec[k] = _W["runner"].last_result[k]
    if _W.get("record_plays"):     # --record-plays: our plays [decision tick, landing tick, card, accepted, elixir seen]
        rec["own_plays"] = [[q["tick"], q.get("land_tick", q["tick"]), q["card"], q["accepted"], q["elixir_exact"]]
                            for q in _W["runner"].last_result["plays"]]
        # ... + our accepted hero / champion presses [tick, card] (royale_env own_ability_events; feature_version >= 4)
        rec["own_presses"] = [[int(e["tick"]), e["card"]] for e in getattr(m.env, "own_ability_events", ())
                              if e["side"] == m.learner.side]
    if getattr(_W["runner"], "habit_log", False):           # --habit-log: the learner's habit counts (measurement only)
        rec["habits"] = habits(m)
    if getattr(_W["runner"], "record_board", False):        # --record-board: plays at x,y + 1-s board (W22 ape_score)
        L, O = m.learner, m.opp
        rec["hab"] = {"own": hab_plays(L), "opp": hab_plays(O), "samples": m.hab_samples,
                      "L": int(L.side), "mirror": [bool(L.mirror), bool(O.mirror)]}
    if "spell" in _W["runner"].last_result:                 # --spell-log: our Rocket events + their spell_value summary
        from pipeline.spell_value import match_summary
        rec["spell"] = {"summary": match_summary(_W["runner"].last_result["spell"]),
                        "events": _W["runner"].last_result["spell"]}
    if "crown" in _W["runner"].last_result:                 # --crown-log: our crown path, Tornado pulls, Rocket aims
        from pipeline.reward_terms import crown_log
        rec["crown"] = crown_log(_W["runner"].last_result)
    rec.update(_W.get("opp_meta") or {})
    return rec


def summarise(rows: list[dict]) -> dict:
    rows = [r for r in rows if not r.get("skipped")]
    cells = {}
    for r in rows:
        cells.setdefault(f"{r['arm']}|{r['opp']}", []).append(r)
    per = {}
    for k, rs in sorted(cells.items()):
        sp = [x["s_per_searched"] for x in rs if x.get("s_per_searched")]
        per[k] = {"n": len(rs), "win": sum(x["outcome"] == "win" for x in rs), "loss": sum(x["outcome"] == "loss" for x in rs),
                  "draw": sum(x["outcome"] == "draw" for x in rs),
                  "crowns_diff_mean": round(float(np.mean([x["crowns_diff"] for x in rs])), 3),
                  "tower_hp_diff_mean": round(float(np.mean([x["tower_hp_diff"] for x in rs])), 1),
                  "plays_accepted_mean": round(float(np.mean([x["plays_accepted"] for x in rs])), 1),
                  "searched": int(sum(x["searched"] for x in rs)),
                  "unsearched": int(sum(x.get("unsearched", 0) for x in rs)),
                  "gate_skipped": int(sum(x.get("gate_skipped", 0) for x in rs)), "overrides": int(sum(x["overrides"] for x in rs)),
                  "chose_wait": int(sum(x["chose_wait"] for x in rs)),
                  "s_per_searched_mean": round(float(np.mean(sp)), 3) if sp else None,
                  "wall_s_mean": round(float(np.mean([x["wall_s"] for x in rs])), 1),
                  "wall_truncated": int(sum(bool(x["wall_truncated"]) for x in rs))}
    base = {(r["opp"], r["seed"]): r for r in rows if r["arm"] == "plain"}
    paired = {}
    for arm in ARMS[1:]:
        for opp in sorted({r["opp"] for r in rows}):
            ps = [(r, base[(opp, r["seed"])]) for r in rows if r["arm"] == arm and r["opp"] == opp
                  and (opp, r["seed"]) in base]
            if not ps:
                continue
            out = {"n_pairs": len(ps)}
            for key in ("tower_hp_diff", "crowns_diff"):
                d = np.array([a[key] - b[key] for a, b in ps], dtype=np.float64)
                sd = float(d.std(ddof=1)) if len(d) > 1 else None
                out[f"{key}_delta_mean"] = round(float(d.mean()), 3)
                out[f"{key}_delta_t"] = round(float(d.mean() / (sd / math.sqrt(len(d)))), 2) if sd else None
            out["win_delta"] = sum((a["outcome"] == "win") - (b["outcome"] == "win") for a, b in ps)
            out["setup_mismatch"] = sum(a["opp_deck"] != b["opp_deck"] or a["learner_side"] != b["learner_side"]
                                        for a, b in ps)
            paired[f"{arm}_vs_plain|{opp}"] = out
    return {"per_arm_opp": per, "paired_vs_plain": paired}


def _range(spec: str) -> list[int]:
    if ":" in spec:
        a, b = (int(v) for v in spec.split(":"))
        return list(range(a, b))
    return [int(v) for v in spec.split(",") if v.strip()]


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--summarise", type=Path, default=None, help="re-summarise an existing run dir and exit")
    ap.add_argument("--seeds", default="0:2", help="a:b range or comma list; learner_side = seed %% 2")
    ap.add_argument("--opps", default="gen,s1")
    ap.add_argument("--arms", default=",".join(ARMS))
    from pipeline.decision_options import add_arguments, config_from_args, options_from_config
    add_arguments(ap)
    ap.add_argument("--gen", default=GEN_CKPT)
    ap.add_argument("--opp-gen", default=None,
                    help="checkpoint of the frozen 'gen' OPPONENT only (default None = --gen); --gen stays our policy "
                         "and the rollout self-model")
    ap.add_argument("--s1", default=S1_CKPT)
    ap.add_argument("--census", default=CENSUS, help="loadable opponent deck census JSON path (relative to repo or absolute)")
    ap.add_argument("--horizon", type=float, default=12.0, help="rollout horizon, seconds")
    ap.add_argument("--interval", type=int, default=1, help="search every Nth affordable decision")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--cells", type=int, default=3)
    ap.add_argument("--threads", type=int, default=2, help="torch.set_num_threads per process")
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"),
                    help="torch device for our policy, the rollout self-model and the opponents (cuda: owner's OK)")
    ap.add_argument("--search-min-p", type=float, default=0.0,
                    help="search arm: a decision with plain gate p < P and no stall is a WAIT without search (0 = off)")
    ap.add_argument("--rollout-self", default="idle", choices=ROLLOUT_SELF,
                    help="our side in a fork after the candidate: idle (S0) or policy (its own live rule, tau 0.35)")
    ap.add_argument("--scorer", default="v1", choices=SCORERS,
                    help="rollout Scorer: v1 (ported, default) or v2 (board value x current HP x position)")
    ap.add_argument("--workers", type=int, default=1, help="parallel matches (processes)")
    ap.add_argument('--behaviour-telemetry', action='store_true', help='Record public per-tick behaviour metrics; defaults unchanged.')
    ap.add_argument("--tail-cap", type=int, default=7200, help="match end tick cap (RoyaleSelfPlayEnv tail_cap)")
    ap.add_argument("--opp-policy", choices=("live", "sample"), default="live",
                    help="sample: opponents draw the gate/card/cell like rl_royale's league (tempered at --opp-T, "
                         "per-match seeded RNG); live (default, unchanged) = the greedy gate, which can stand off")
    ap.add_argument("--opp-T", type=float, default=0.3)
    ap.add_argument("--learner-policy", choices=("live", "sample"), default="live",
                    help="10-13 train/deploy gap: sample = OUR side draws gate/card/cell like rl_royale rollouts (tempered at "
                         "--learner-T, gate centred on --tau-plain); no decision options; default live = unchanged")
    ap.add_argument("--learner-T", type=float, default=0.5)
    ap.add_argument("--learner-T-gate", type=float, default=None,
                    help="with --learner-policy sample: the gate's own temperature (default None = --learner-T)")
    ap.add_argument("--learner-sample-heads", default="gate,card,cell",
                    help="with --learner-policy sample: heads that are drawn; the rest take the greedy live choice (eval only)")
    ap.add_argument("--tau-plain", type=float, default=None,
                    help="lead 2026-10-06: the plain arm's gate threshold (default None = TAU_PLAIN 0.35, unchanged)")
    ap.add_argument("--predict-drops", action="store_true",
                    help="learner look-ahead adds an observed Skeleton Barrel balloon's 7 skeletons 12 ticks after its "
                         "death (cfg 'predict_drops', pipeline/extrapolate.py); default off = unchanged")
    ap.add_argument("--own-effects", action="store_true",
                    help="W1: the learner look-ahead applies my own recent Log / Tornado / Rocket / hero IW freeze to the "
                         "enemy bodies they reach (cfg 'own_effects', pipeline/extrapolate.py); default off = unchanged")
    ap.add_argument("--pipeline-decisions", action="store_true",
                    help="L74: the learner's MODEL decides again while one of its plays is pending (cfg 'pipeline_decisions', "
                         "e1_eval.SelfPlaySide; needs the live delay; frame grid, <= 2 outstanding); default off = unchanged")
    ap.add_argument("--pipeline-tau-delta", type=float, default=0.0,
                    help="with --pipeline-decisions: added to the play-gate threshold while a play is pending (default 0)")
    ap.add_argument("--gate-sample", type=float, default=0.0, metavar="T",
                    help="GATE-SAMPLE 10-30: our gate = the trainer's Bernoulli(sigmoid((z - logit tau) / T)) (tau = the phase "
                         "tau, decision_options.decide gate_sample; live --gate-sample), one seeded stream per match (cfg "
                         "'gate_sample'); needs decision options, no --pipeline-decisions; 0 = the threshold gate (unchanged)")
    ap.add_argument("--record-plays", action="store_true",
                    help="each match line gets own_plays [decision tick, landing tick, card, accepted, elixir seen]")
    ap.add_argument("--hero-abilities", action="store_true",
                    help="press ready, affordable hero buttons within attack range + 1.5 tiles of enemies")
    ap.add_argument("--ability-policy", default="generic", choices=("generic", "v2"),
                    help="with --hero-abilities: generic = the range rule above (today); v2 = L70 per-ability calibrated "
                         "press model (heroes and champions; royale_env V2_KEYS)")
    ap.add_argument("--ability-stats", action="store_true",
                    help="with --hero-abilities: each line gets ability_stats (our presses, elixir on them, enemies in "
                         "radius at the press and how many lost HP / died within 2 s); default off = unchanged")
    ap.add_argument("--ability-head-decode", default="greedy", choices=("greedy", "sample"),
                    help="a checkpoint with a learned ability head (rl_royale B6): greedy = press iff p > 0.5 (default, "
                         "unchanged); sample = Bernoulli(p) as in RL rollouts, seeded per match (e1_eval.ability_decide's "
                         "rng_ability from the match tag) so paired arms draw alike (L74 overpress 10-18)")
    ap.add_argument("--forms-mode", default="base", choices=("base", "deck"),
                    help="RoyaleSim card forms: base = every card as its base card (today); deck = decked evolutions / "
                         "heroes the engine loads, refused forms fall back to base (royale_env docstring)")
    ap.add_argument("--opp-decide-every", type=int, default=None,
                    help="opponent side's decision interval in ticks (L74 human tempo, e1_eval.opp_tempo); default = ours (10)")
    ap.add_argument("--opp-reaction-ticks", type=int, default=None,
                    help="extra ticks added to the opponent's action delay (L74 human tempo); default none")
    ap.add_argument("--opp-tau", type=float, default=None,
                    help="L74 W18 probe: the opponent's play/wait threshold (sample policy: logit(tau) is subtracted from "
                         "the gate logit); default = TAU_OPP")
    ap.add_argument("--tap-loss", default=None, metavar="1x:P,2x:P,ot2x:P,ot3x:P",
                    help="L74 W18: OUR side loses a decided play with the window's probability (e1_eval.parse_tap_loss: the "
                         "live pilot's measured lost taps); default none")
    ap.add_argument("--probe-xbow-start", default=None, choices=PROBE_ARMS,
                    help="W18 P-D payoff probe (SIM-only): live X-Bow starts, the opponent's first answer scripted per arm, "
                         "12 s matches; default off")
    ap.add_argument("--tap-slow", default=None, metavar="P:EXTRA",
                    help="L74 W18: OUR decided play lands EXTRA ticks late with probability P (e1_eval.parse_tap_slow: the "
                         "live pilot's slow taps); default none")
    ap.add_argument("--tap-hold", type=int, default=None, metavar="N",
                    help="RECON-7: OUR not-enough-elixir play is retried each tick for N ticks after its landing, as the game holds a tap "
                         "that cannot pay yet (live ~22; e1_eval.parse_tap_hold); default none")
    ap.add_argument("--play-resume", default=None, choices=("land",),
                    help="RECON-7: after OUR delayed play the next decision is the tick after the engine ran it (live 26 ticks after the "
                         "decision), not the next decision-grid tick (30); default none")
    ap.add_argument("--probe-xbow-focus", action="store_true",
                    help="SIM-ONLY measurement probe (owner 2026-10-15; never live): once an enemy princess is damaged, an "
                         "offensive X-Bow of ours that misses the weaker alive princess moves to the model's best cell "
                         "reaching it (decision_options.probe_xbow_focus_cell); rows count it. Needs --arms plain, live policy")
    ap.add_argument("--opp-tower-troops", default=None,
                    help="L74 troops: the opponent fields a crown tower troop at these rates, e.g. "
                         "DaggerDuchess:0.03,Cannoneer:0.03,ChefTower:0.01 (drawn per seed + opponent deck, so paired "
                         "across checkpoints; needs the RoyaleSim fork runtime); default none = the Princess (unchanged)")
    ap.add_argument("--live-levels", action="store_true",
                    help="L74 factor D: our cards / towers at our live levels, the opponent's drawn per seed + opponent deck "
                         "from the live opponents (rl_royale.draw_live_levels, L74/levels/live_levels.json); rows carry "
                         "'levels'. Default off = every card and tower at the engine default level 11 (unchanged)")
    ap.add_argument("--record-board", action="store_true",
                    help="W22: each match line gets 'hab' (both sides' plays with engine x,y + a 1-s sample of towers, "
                         "enemy bodies and our X-Bows; the L74/habits HABITS_REC format) for ape_score.py; measurement "
                         "only, decisions unchanged; default off = lines unchanged")
    ap.add_argument("--habit-log", action="store_true",
                    help="each match line gets 'habits' (search_s0.habits: opening-hand X-Bow, offensive X-Bow in the first "
                         "two plays, Rockets on an enemy princess / forced by the finisher, late X-Bow / Rocket / Tornado); "
                         "measurement only, decisions unchanged; default off = lines unchanged")
    ap.add_argument("--spell-log", action="store_true",
                    help="each match line gets 'spell' (pipeline.spell_value: our Rocket impacts -- troop elixir value hit, "
                         "princess in the blast, setup Tornado -- and their summary); measurement only, decisions unchanged "
                         "(the engine steps one tick at a time while our Rocket is up); default off = lines unchanged")
    ap.add_argument("--crown-log", action="store_true",
                    help="each match line gets 'crown' (pipeline.reward_terms.CrownTracker: princess falls with the crowns "
                         "before each, king / princess hp at the end, our Tornados' net pull toward our king, our Rocket "
                         "aims, + match_summary); read-only (never steps the engine), decisions unchanged; default off = "
                         "lines unchanged")
    ap.add_argument("--max-wall-min", type=float, default=0.0,
                    help="0 = none; else no match starts after this and running matches stop (wall_truncated)")
    a = ap.parse_args(argv)
    decision_cfg = config_from_args(a)
    decision_active = options_from_config(decision_cfg).active
    if a.learner_policy == 'sample' and a.arms != 'plain':
        ap.error('--learner-policy sample needs --arms plain')
    if not set(a.learner_sample_heads.split(',')) <= {'gate', 'card', 'cell'}:
        ap.error('--learner-sample-heads takes a comma list of gate, card, cell')
    if a.learner_policy == 'sample' and decision_active:
        ap.error('--learner-policy sample is the plain RL rollout sampler; it takes no decision options')
    if decision_active and a.arms != 'plain':
        ap.error('decision options require --arms plain; search experiments are separate')
    if a.gate_sample and not (math.isfinite(a.gate_sample) and a.gate_sample > 0 and decision_active
                              and not a.pipeline_decisions and a.learner_policy == 'live'):
        # ponytail: no per-time exponent in the SIM: a SIM wait advances exactly decide_every (10) ticks = the pilot's
        # trained step, so k = 1 on every row; fast plays (decisions while pending) would break that -> refused
        ap.error('--gate-sample T needs T > 0, decision options, --learner-policy live and no --pipeline-decisions')
    if a.probe_xbow_focus and (a.arms != 'plain' or a.learner_policy != 'live'):
        ap.error('--probe-xbow-focus needs --arms plain and --learner-policy live')
    if a.ability_policy == "v2" and not a.hero_abilities:
        ap.error("--ability-policy v2 needs --hero-abilities")
    if a.ability_stats and not a.hero_abilities:
        ap.error("--ability-stats needs --hero-abilities")
    if a.live_levels and "search" in a.arms.split(","):
        ap.error("--live-levels: the search arm's Scorer needs one tower level for both sides (engine_tower_level)")
    try:
        E.opp_tempo({}, a.opp_decide_every, a.opp_reaction_ticks)
    except ValueError as exc:
        ap.error(str(exc))
    if a.opp_tower_troops is not None:
        from pipeline.rl_royale import opp_tower_troops
        try:
            a.opp_tower_troops = opp_tower_troops({"league": True, "opp_tower_troops": {
                k: float(v) for k, v in (x.split(":") for x in a.opp_tower_troops.split(","))}})
        except (ValueError, SystemExit) as exc:
            ap.error(f"--opp-tower-troops: {exc}")
    if a.summarise:
        rows = [json.loads(x) for x in (a.summarise / "matches.jsonl").read_text(encoding="utf-8").splitlines() if x]
        s = summarise(rows)
        (a.summarise / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
        print(json.dumps(s, indent=1))
        return 0
    if a.out is None:
        ap.error("--out is required")
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"REFUSING: {a.out} exists and is not empty")
    a.out.mkdir(parents=True, exist_ok=True)
    arms, opps, seeds = [x for x in a.arms.split(",") if x], [x for x in a.opps.split(",") if x], _range(a.seeds)
    bad = [x for x in arms if x not in ARMS] + [x for x in opps if x not in ("gen", "s1")]
    if bad:
        raise SystemExit(f"unknown arm/opponent {bad}")
    if a.opp_gen is None:
        a.opp_gen = a.gen
    deadline = time.time() + 60.0 * a.max_wall_min if a.max_wall_min else 0.0
    opp_sha = sha256(REPO / a.opp_gen)
    wargs = {"gen": a.gen, "opp_gen": a.opp_gen, "opp_gen_sha256": opp_sha, "s1": a.s1, "opps": opps, "threads": a.threads, "tail_cap": a.tail_cap, "horizon": a.horizon,
             "interval": a.interval, "topk": a.topk, "cells": a.cells,
             "device": a.device, "search_min_p": a.search_min_p, "rollout_self": a.rollout_self,
             "forms_mode": a.forms_mode, "hero_abilities": a.hero_abilities, "ability_policy": a.ability_policy, "scorer": a.scorer, "census": a.census}
    if decision_active:
        wargs['decision_options'] = decision_cfg
    if a.gate_sample:
        wargs['gate_sample'] = float(a.gate_sample)
    if a.behaviour_telemetry:
        wargs['behaviour_telemetry'] = True
    if a.opp_policy != "live":
        wargs['opp_policy'], wargs['opp_T'] = a.opp_policy, float(a.opp_T)
    if a.tau_plain is not None:
        wargs['tau_plain'] = float(a.tau_plain)
    if a.learner_policy != 'live':
        wargs['learner_policy'], wargs['learner_T'] = a.learner_policy, float(a.learner_T)
        wargs['learner_sample_heads'] = [h for h in a.learner_sample_heads.split(',') if h]
        wargs['learner_T_gate'] = a.learner_T_gate
    if a.predict_drops:
        wargs['predict_drops'] = True
    if a.own_effects:
        wargs['own_effects'] = True
    if a.pipeline_decisions:
        wargs['pipeline_decisions'] = True
        wargs['pipeline_tau_delta'] = a.pipeline_tau_delta
    if a.record_plays:
        wargs['record_plays'] = True
    if a.probe_xbow_focus:
        wargs['probe_xbow_focus'] = True
    if a.ability_stats:
        wargs['ability_stats'] = True
    if a.ability_head_decode != 'greedy':
        wargs['ability_head_decode'] = a.ability_head_decode
    if a.opp_tower_troops is not None:
        wargs['opp_tower_troops'] = a.opp_tower_troops
    if a.live_levels:
        wargs['live_levels'] = True
    if a.habit_log:
        wargs['habit_log'] = True
    if a.record_board:
        wargs['record_board'] = True
    if a.spell_log:
        wargs['spell_log'] = True
    if a.crown_log:
        wargs['crown_log'] = True
    for k in ('opp_decide_every', 'opp_reaction_ticks', 'opp_tau', 'tap_loss', 'tap_slow', 'tap_hold', 'play_resume', 'probe_xbow_start'):   # L74 tempo; W18 opp_tau / tap_loss
        if getattr(a, k) is not None:
            wargs[k] = getattr(a, k)
    if a.tap_loss is not None:
        E.parse_tap_loss(a.tap_loss)                         # fail before any worker starts
    if a.tap_slow is not None:
        E.parse_tap_slow(a.tap_slow)
    if a.tap_hold is not None:
        E.parse_tap_hold(a.tap_hold)
    (a.out / "run.json").write_text(json.dumps({**{k: v for k, v in vars(a).items() if (k not in ('tap_hold', 'play_resume') or v is not None) and (k != "census" or a.census != CENSUS) and (k != 'behaviour_telemetry' or v) and (k != 'tau_plain' or v is not None) and (k not in ('opp_policy', 'opp_T') or a.opp_policy != 'live') and (k not in ('learner_policy', 'learner_T', 'learner_sample_heads', 'learner_T_gate') or a.learner_policy != 'live') and (k != 'predict_drops' or v) and (k != 'own_effects' or v) and (k != 'ability_head_decode' or v != 'greedy') and (k not in ('pipeline_decisions', 'pipeline_tau_delta', 'gate_sample', 'record_plays', 'probe_xbow_focus', 'ability_stats', 'live_levels', 'habit_log', 'spell_log', 'crown_log', 'record_board') or v) and (k not in ('opp_decide_every', 'opp_reaction_ticks', 'opp_tower_troops', 'opp_tau', 'tap_loss', 'tap_slow', 'probe_xbow_start') or v is not None) and (decision_active or k not in decision_cfg)}, "out": str(a.out), "summarise": None,
                                                "gen_sha256": sha256(REPO / a.gen), "opp_gen_sha256": opp_sha,
                                                "s1_sha256": sha256(REPO / a.s1),
                                                "tau_plain": TAU_PLAIN, "tau_opp": TAU_OPP, "crown_w": CROWN_W,
                                                "started": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1),
                                    encoding="utf-8")
    # (opp, seed) outer, arms inner: every pair a seed needs finishes close together
    jobs = [(arm, opp, s, deadline) for opp in opps for s in seeds for arm in arms]
    rows, t0 = [], time.perf_counter()
    fh = (a.out / "matches.jsonl").open("a", encoding="utf-8")

    def emit(rec):
        rows.append(rec)
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        if rec.get("skipped"):
            print(f"[s0] skip {rec['arm']} {rec['opp']} seed {rec['seed']}: {rec['skipped']}", flush=True)
            return
        print(f"[s0] {rec['arm']:10s} {rec['opp']:3s} seed {rec['seed']} {rec['outcome']:4s} {rec['crowns_for']}-"
              f"{rec['crowns_against']} towerHP {rec['tower_hp_diff']:+d} plays {rec['plays_accepted']} searched "
              f"{rec['searched']} unsearched {rec['unsearched']} ovr {rec['overrides']} wait {rec['chose_wait']} s/dec {rec['s_per_searched']} "
              f"wall {rec['wall_s']}s{' TRUNCATED' if rec['wall_truncated'] else ''}", flush=True)

    if a.workers <= 1:
        _init_worker(wargs)
        for j in jobs:
            emit(_run_job(j))
    else:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker, initargs=(wargs,)) as pool:
            for rec in pool.imap_unordered(_run_job, jobs):
                emit(rec)
    fh.close()
    s = summarise(rows)
    s["wall_total_s"] = round(time.perf_counter() - t0, 1)
    (a.out / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    print(json.dumps(s, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
