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


# ------------------------------------------------------------------------------------------------------
# forking
# ------------------------------------------------------------------------------------------------------
def fork_into(m, env2, blob: bytes):
    """A copy of SelfPlayMatch ``m`` on the pooled env ``env2``: engine = ``blob`` (m.env.core.save_state()), env python
    fields and both sides' python state deep-copied; models / cfg / deck / modules shared. -> a SelfPlayMatch."""
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
        c.__dict__.update({k: (v if k in SHARED_SIDE else copy.deepcopy(v)) for k, v in s.__dict__.items()})
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


class Runner:
    """Plays one (arm, opponent, seed) match. ``learner`` = our policy (also the rollout self-model of the opponent);
    ``opps`` = {id: (policy, cfg)}; ``make_env()`` -> RoyaleSelfPlayEnv."""

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
        opp, ocfg = self.opps[opp_id]
        return E.SelfPlayMatch(self.make_env(), spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0},
                               self.learner, opp)

    def play(self, arm: str, m, deadline: Optional[float] = None) -> dict:
        if arm not in ARMS:
            raise ValueError(f"arm {arm!r} not in {ARMS}")
        rng = random.Random(zlib.crc32(f"{m.spec['tag']}:s0random".encode()))
        st = {"eligible": 0, "searched": 0, "unsearched": 0, "gate_skipped": 0, "search_s": 0.0, "overrides": 0,
              "chose_wait": 0, "plain_wait_overridden": 0, "moved_cell": 0, "n_cands": 0}
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
                "crowns_for": r["crowns_for"], "crowns_against": r["crowns_against"],
                "crowns_diff": r["crowns_for"] - r["crowns_against"],
                "tower_hp_for": hp_for, "tower_hp_against": hp_against, "tower_hp_diff": hp_for - hp_against,
                "device": self.dev, "search_min_p": self.search_min_p, "rollout_self": self.rollout_self,
                "end_tick": r["end_tick"], "tail_cap": int(env.tail_cap), "wall_truncated": truncated,
                "plays_attempted": r["plays_attempted"], "plays_accepted": r["plays_accepted"],
                "opp_plays_accepted": r["opp_side"]["plays_accepted"], "decisions": r["decisions"],
                **st, "search_s": round(st["search_s"], 2),
                "s_per_searched": round(st["search_s"] / st["searched"], 3) if st["searched"] else None,
                **({k: r[k] for k in ("hero_abilities", "ability_presses", "ability_policy", "ability_fallback_generic",
                                      "ability_deployments") if k in r} if "hero_abilities" in r else {}),
                **({'behaviour': r['behaviour']} if 'behaviour' in r else {}),
                **({'public_lookahead_counts': r['public_lookahead_counts']} if 'public_lookahead_counts' in r else {}),
                **({k: r[k] for k in ("forms_mode", "form_fallbacks")} if "forms_mode" in r else {}),
                "wall_s": round(time.perf_counter() - t0, 1)}

    def round(self, m, ds, arm: str, st: dict, rng: random.Random) -> None:
        """One round of run_selfplay_batch for one match (prepare all, decide each on its own model, apply in side
        order), with our side's decision replaced per ``arm``."""
        from pipeline.e1_eval import live_decide_batch
        for s in ds:
            s.prepare()
        todo = []
        for s in ds:
            p, enc, heads, hand = forward(s)
            _, allowed, stalled = s.pre(hand)
            d = live_decide_batch(s.model, enc, heads, [p], allowed[None], np.array([stalled]), tau=s.cfg["tau"],
                                  device=s.cfg["device"], **decision_match_kwargs([s]))[0]
            if s is m.learner and arm == "never":
                d = NEVER_PLAY                              # our side never plays (stall rule included)
            elif s is m.learner and arm != "plain" and allowed.any():
                st["eligible"] += 1
                if (st["eligible"] - 1) % self.interval == 0:
                    d = self.arm_decide(m, ds, arm, p, enc, heads, allowed, d, st, rng, stalled=bool(stalled))
                else:
                    st["unsearched"] += 1                   # off-interval: the plain decision stands
            todo.append((s, p, d))
        for s, p, d in todo:
            s.apply(p, d)

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
    cap, fm = int(args["tail_cap"]), args.get("forms_mode", "base")
    learner_cfg = live_cfg(args.get('tau_plain', TAU_PLAIN), gi['grid'], dev)
    if args.get('decision_options'):
        learner_cfg.update(args['decision_options'])
    if args.get('behaviour_telemetry'):
        learner_cfg['behaviour_telemetry'] = True
    _W["runner"] = Runner(gen, opps, learner_cfg,
                          lambda: RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=cap, forms_mode=fm,
                                                    hero_abilities=args.get("hero_abilities", False),
                                                    ability_policy=args.get("ability_policy", "generic")),
                          horizon_s=args["horizon"], interval=args["interval"], topk=args["topk"], cells=args["cells"],
                          search_min_p=args["search_min_p"], rollout_self=args.get("rollout_self", "idle"),
                          scorer_version=args.get("scorer", "v1"))
    _W["census"] = league_decks(REPO / args.get("census", CENSUS))


def setup_job(run, census, opp_id: str, seed: int):
    """-> (SelfPlayMatch, opponent deck name) for (opp_id, seed): S1 plays icebow; gen a seeded census deck, redrawn
    deterministically while unloadable or holding a card the generalist never saw. None = no loadable deck."""
    from pipeline.dataset_gen import card_key
    from pipeline.royale_env import UnsupportedDeck
    if opp_id == "s1":
        return run.setup(opp_id, seed, E.ICEBOW_ENGINE_DECK), "icebow"
    for j in range(50):                                            # redraw an unloadable deck, deterministically
        d = opp_deck_for(seed * 1000 + j, census)
        if any(card_key(n) not in run.opps[opp_id][0].gid for n in d["engine"]):
            continue                                               # a card the generalist never saw
        try:
            return run.setup(opp_id, seed, d["engine"]), d["name"]
        except (UnsupportedDeck, KeyError):
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
    ap.add_argument("--tau-plain", type=float, default=None,
                    help="lead 2026-10-06: the plain arm's gate threshold (default None = TAU_PLAIN 0.35, unchanged)")
    ap.add_argument("--hero-abilities", action="store_true",
                    help="press ready, affordable hero buttons within attack range + 1.5 tiles of enemies")
    ap.add_argument("--ability-policy", default="generic", choices=("generic", "v2"),
                    help="with --hero-abilities: generic = the range rule above (today); v2 = L70 per-ability calibrated "
                         "press model (heroes and champions; royale_env V2_KEYS)")
    ap.add_argument("--forms-mode", default="base", choices=("base", "deck"),
                    help="RoyaleSim card forms: base = every card as its base card (today); deck = decked evolutions / "
                         "heroes the engine loads, refused forms fall back to base (royale_env docstring)")
    ap.add_argument("--max-wall-min", type=float, default=0.0,
                    help="0 = none; else no match starts after this and running matches stop (wall_truncated)")
    a = ap.parse_args(argv)
    decision_cfg = config_from_args(a)
    decision_active = options_from_config(decision_cfg).active
    if decision_active and a.arms != 'plain':
        ap.error('decision options require --arms plain; search experiments are separate')
    if a.ability_policy == "v2" and not a.hero_abilities:
        ap.error("--ability-policy v2 needs --hero-abilities")
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
    if a.behaviour_telemetry:
        wargs['behaviour_telemetry'] = True
    if a.tau_plain is not None:
        wargs['tau_plain'] = float(a.tau_plain)
    (a.out / "run.json").write_text(json.dumps({**{k: v for k, v in vars(a).items() if (k != "census" or a.census != CENSUS) and (k != 'behaviour_telemetry' or v) and (k != 'tau_plain' or v is not None) and (decision_active or k not in decision_cfg)}, "out": str(a.out), "summarise": None,
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
