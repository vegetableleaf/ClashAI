"""S0: decision-time rollout SEARCH over the frozen generalist, on RoyaleSim, closed loop, NO training (L69).

        --seeds 0:8 --opps gen,s1 --arms plain,search,force_play,random,never [--horizon 12] [--interval 1] \
        [--topk 4] [--cells 3] [--threads 2] [--workers 1] [--tail-cap 7200] [--max-wall-min 0]

Writes ``<out>/matches.jsonl`` (one line per (arm, opponent, seed), flushed as each ends), ``<out>/summary.json``
(per arm x opponent: W/L/D, mean crowns diff, mean crown-tower HP diff; per seed PAIRED deltas of every arm against

DESIGN (lead-fixed, L69 ticket S0)
  delay 26, extrapolate 26, decide every 10 ticks, rl_royale.yaml's afford/stall keys). Arms at our decisions:
    search      at every decision (``--interval`` 1) with >= 1 affordable card: candidates = WAIT + the top ``--topk``
                affordable cards (the policy's hand-masked card logits) x the top ``--cells`` cells each (that card's
                cell logits); each scored by ONE rollout, argmax played, ties -> WAIT. Nothing affordable -> WAIT, no
                search. Off-interval decisions play the plain rule.
    force_play  the top candidate (top card, top cell), no rollouts -- "does playing at all explain the gain".
    random      a uniform pick among the same shortlist's PLAY candidates -- "does choosing matter".
    never       our side never plays (anti-stall included) -- the restraint floor: the Scorer subtracts spent elixir
                over a 12 s horizon, so WAIT can win by construction; search must beat THIS, not only plain.
  ``--search-min-p P`` (default 0 = the faithful design, search every decision): search arm only, a decision whose
  plain gate p < P with no anti-stall is a WAIT without rollouts (counted ``unsearched`` / ``gate_skipped``).
  A chosen action is a decision at the current tick, applied through ``SelfPlaySide.apply``: with delay 26 it is queued
  and lands at tick + 26 exactly as the plain policy's play would.
  ROLLOUT: fork = RoyaleSim ``save_state``/``load_state`` into a pooled engine + deep copies of the env's python fields
  and BOTH sides' python state (models / cfg / deck shared, never copied). In a fork our candidate lands normally and
  our side then makes NO further plays; the opponent keeps deciding through its own SelfPlaySide code path and its own
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
      db / tower_level                  -> clashrl.cards.shared() (icebow's card DB) / 15, threat_value unchanged
      spent                             -> the candidate's catalogue cost iff it was ACCEPTED at landing inside the fork
  Team 0 of the old scorer = OUR side (the learner), team 1 = the opponent.

DISCLOSED OPTIMISM: rollouts start from the TRUE engine state -- the opponent's hidden hand, cycle, exact elixir and
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

GEN_CKPT = "icebow/data/pipeline/gen_v1_s0/gen_s0.pt"
S1_CKPT = "icebow/data/pipeline/s1_icebow_v6aug_s1.pt"
ARMS = ("plain", "search", "force_play", "random", "never")
TAU_PLAIN, TAU_OPP = 0.35, 0.27
CROWN_W = 1.0
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

    def __init__(self, catalogue, crown_w: float = CROWN_W, tower_level: int = 15, db=None):
        from clashrl import threat_value as TV
        from clashrl.cards import shared
        from pipeline.dataset_gen import card_key
        self.TV, self.db = TV, (db if db is not None else shared())
        self.cards = {c.card_id: c for c in catalogue}
        self.base = {c.card_id: card_key(c.name) for c in catalogue}
        self.crown_w, self.tower_level = float(crown_w), int(tower_level)
        self._finite: dict = {}
        self._ref: dict = {}

    def _has_finite_ignore(self, base: str) -> bool:
        v = self._finite.get(base)
        if v is None:
            try:
                v = math.isfinite(self.TV.ignore_cost_frac(self.db, base, tower_level=self.tower_level))
            except Exception:           # noqa: BLE001 -- an unknown card is never ignorable (old Scorer)
                v = False
            self._finite[base] = v
        return v

    def board_value(self, st, team: int) -> float:
        from royalegym.protocol import EMPTY_CARD, EntityKind
        finite, extra = [], 0.0
        for e in st.entities:
            if e.team != team or e.hp <= 0 or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING) \
                    or e.card_id == EMPTY_CARD:
                continue
            b = self.base.get(e.card_id)
            if b and self._has_finite_ignore(b):
                finite.append(b)
            else:
                c = self.cards[e.card_id]
                extra += (float(c.elixir) / max(1, int(c.count))) * self.TV.ELIXIR_TO_TOWER
        v = 0.0
        if finite:
            v = float(self.TV.bodies_ignore_frac(self.db, finite, tower_level=self.tower_level))
            if not math.isfinite(v):
                v = BOARD_CAP
        return min(BOARD_CAP, v + extra)

    def tower_frac(self, st, team: int) -> float:
        """Standing crown-tower HP of ``team`` in units of ONE of its princess towers (old Scorer.tower_frac)."""
        from royalegym.protocol import EntityKind
        tw = [e for e in st.entities if e.team == team and e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)]
        for e in tw:
            if e.kind == EntityKind.PRINCESS_TOWER and team not in self._ref:
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
    """"""
    return {"policy": "live", "tau": float(tau), "afford_mask": True, "stall_elixir": 9, "stall_seconds": 12.0,
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
                 search_min_p: float = 0.0):
        self.learner, self.opps, self.lcfg, self.make_env = learner, opps, learner_cfg, make_env
        self.dev = learner_cfg["device"]                  # our policy AND the rollout self-model's forwards
        self.search_min_p = float(search_min_p)
        self.H = int(round(float(horizon_s) / E.TICK_S))
        self.interval, self.topk, self.cells = max(1, int(interval)), int(topk), int(cells)
        for oid, (_, oc) in opps.items():
            if oc["grid"] != learner_cfg["grid"]:    # a pending opponent play would land in the wrong grid in a fork
                raise ValueError(f"opponent {oid} grid {oc['grid']} != self-model grid {learner_cfg['grid']}")
        self.pool: list = []
        self.scorer = scorer

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
            self.scorer = Scorer(env.core.cards())
        blob = env.core.save_state()
        acts = [WAIT] + cands
        forks = [fork_into(m, e2, blob) for e2 in self._pool(len(acts))]
        s0 = self.scorer.snapshot(env.core.state(), L)
        cap = min(env.tail_cap, int(env.tick) + self.H)
        ocfg = {**m.opp.cfg, "policy": "live", "tau": TAU_OPP, "grid": self.lcfg["grid"], "device": self.dev}
        acc0 = m.learner.n_acc
        for f, a in zip(forks, acts):
            f.env.tail_cap = cap
            f.opp.model, f.opp.cfg = self.learner, ocfg
            f.learner.apply(p, a)
            f.learner.next_tick = NEVER
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
            enc, heads, pp, hand = self.learner.forward_batch([s.gen_row(self.learner) for s in due], self.dev)
            pre = [s.pre(hand[r]) for r, s in enumerate(due)]
            dec = live_decide_batch(self.learner, enc, heads, pp, np.stack([x[1] for x in pre]),
                                    np.array([x[2] for x in pre], dtype=bool), tau=TAU_OPP, device=self.dev)
            for r, s in enumerate(due):
                s.apply(pp[r], dec[r])
        self.last_forks = forks                                   # kept for inspection (tests)
        out = []
        for f, a in zip(forks, acts):
            spent = float(f.learner.costs[a["slot"]]) if (a["play"] and f.learner.n_acc > acc0) else 0.0
            out.append(self.scorer.score(s0, self.scorer.snapshot(f.env.core.state(), L), spent))
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
                "device": self.dev, "search_min_p": self.search_min_p,
                "end_tick": r["end_tick"], "tail_cap": int(env.tail_cap), "wall_truncated": truncated,
                "plays_attempted": r["plays_attempted"], "plays_accepted": r["plays_accepted"],
                "opp_plays_accepted": r["opp_side"]["plays_accepted"], "decisions": r["decisions"],
                **st, "search_s": round(st["search_s"], 2),
                "s_per_searched": round(st["search_s"] / st["searched"], 3) if st["searched"] else None,
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
                                  device=s.cfg["device"])[0]
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
    if "gen" in args["opps"]:
        og, oi = E.load_policy(REPO / args["gen"], dev)          # its own object (no shared state with ours)
        opps["gen"] = (og, live_cfg(TAU_OPP, oi["grid"], dev))
    if "s1" in args["opps"]:
        s1, si = E.load_policy(REPO / args["s1"], dev)
        opps["s1"] = (s1, live_cfg(TAU_OPP, str(si.get("grid", "floor")), dev))
    cap = int(args["tail_cap"])
    _W["runner"] = Runner(gen, opps, live_cfg(TAU_PLAIN, gi["grid"], dev),
                          lambda: RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=cap),
                          horizon_s=args["horizon"], interval=args["interval"], topk=args["topk"], cells=args["cells"],
                          search_min_p=args["search_min_p"])
    _W["census"] = league_decks(REPO / "scratchpad/gauntlet/L68/selfplay/loadable_decks.json")


def _run_job(job: tuple) -> dict:
    arm, opp_id, seed, deadline = job
    if deadline and time.time() > deadline:
        return {"arm": arm, "opp": opp_id, "seed": seed, "skipped": "wall budget"}
    from pipeline.dataset_gen import card_key
    from pipeline.royale_env import UnsupportedDeck
    run, census = _W["runner"], _W["census"]
    if opp_id == "s1":
        m, name = run.setup(opp_id, seed, E.ICEBOW_ENGINE_DECK), "icebow"
    else:
        for j in range(50):                                        # redraw an unloadable deck, deterministically
            d = opp_deck_for(seed * 1000 + j, census)
            if any(card_key(n) not in run.opps[opp_id][0].gid for n in d["engine"]):
                continue                                           # a card the generalist never saw
            try:
                m = run.setup(opp_id, seed, d["engine"])
                name = d["name"]
                break
            except (UnsupportedDeck, KeyError):
                continue
        else:
            return {"arm": arm, "opp": opp_id, "seed": seed, "skipped": "no loadable deck"}
    rec = run.play(arm, m, deadline or None)
    rec["opp_deck_name"] = name
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
    ap.add_argument("--gen", default=GEN_CKPT)
    ap.add_argument("--s1", default=S1_CKPT)
    ap.add_argument("--horizon", type=float, default=12.0, help="rollout horizon, seconds")
    ap.add_argument("--interval", type=int, default=1, help="search every Nth affordable decision")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--cells", type=int, default=3)
    ap.add_argument("--threads", type=int, default=2, help="torch.set_num_threads per process")
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"),
                    help="torch device for our policy, the rollout self-model and the opponents (cuda: owner's OK)")
    ap.add_argument("--search-min-p", type=float, default=0.0,
                    help="search arm: a decision with plain gate p < P and no stall is a WAIT without search (0 = off)")
    ap.add_argument("--workers", type=int, default=1, help="parallel matches (processes)")
    ap.add_argument("--tail-cap", type=int, default=7200, help="match end tick cap (RoyaleSelfPlayEnv tail_cap)")
    ap.add_argument("--max-wall-min", type=float, default=0.0,
                    help="0 = none; else no match starts after this and running matches stop (wall_truncated)")
    a = ap.parse_args(argv)
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
    deadline = time.time() + 60.0 * a.max_wall_min if a.max_wall_min else 0.0
    wargs = {"gen": a.gen, "s1": a.s1, "opps": opps, "threads": a.threads, "tail_cap": a.tail_cap, "horizon": a.horizon,
             "interval": a.interval, "topk": a.topk, "cells": a.cells,
             "device": a.device, "search_min_p": a.search_min_p}
    (a.out / "run.json").write_text(json.dumps({**vars(a), "out": str(a.out), "summarise": None,
                                                "gen_sha256": sha256(REPO / a.gen), "s1_sha256": sha256(REPO / a.s1),
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
