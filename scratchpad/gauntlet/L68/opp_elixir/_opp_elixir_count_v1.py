"""Opponent elixir from PUBLIC events only (L68 live memory-reader path).

Two separable layers:

(a) ACCOUNTING -- ``OppElixirCounter``: elixir is deterministic. Start ``START_ELIXIR`` at tick 0, regenerate
    per ``REGEN_SCHEDULE``, cap at 10 (regen while capped is lost), minus each play's cost. A play the estimate
    cannot afford proves the estimate was LOW: re-base up to exactly the cost (the least it can have been) and
    count it. A missed play makes the estimate HIGH, and nothing truth-blind corrects that side.

    Constants DERIVED from the driven sandbox corpora (scratchpad/gauntlet/ext/corpus_v6/{icebow,hogeq},
    scripts + .out in scratchpad/gauntlet/L68/opp_elixir/):
      start  6.0 at tick 0 -- every replay's first frame (800/800 sampled, first 400 per deck) is 6.178 at tick 10 = 6.0 + 10 x 0.0178; the live probe
             (L68/live_reader/probe1.jsonl) agrees exactly: side 0, no plays, elixir_raw 96668 at tick 206 =
             60000 + 206 x 178. NOT 5.0.
      regen  178 / 357 / 537 raw (1e-4 elixir) per tick = 1 elixir per 2.81 / 1.40 / 0.93 s (median clean
             frame-pair rate per 200-tick bin, _rate_probe, 600 replays; bins agree to 4 decimals):
             single [0, 2400), double [2400, 4800) (regulation double AND overtime's first minute),
             triple [4800, 6002), none from 6002 (end of overtime / tiebreak drain; mode of 616+395 solves at
             6002/6003). Boundaries solved from every clean frame pair straddling them over all 3403
             replays (_boundary_probe: 5461 pairs -> 2400, 2178 -> 4800). The live reader confirms the single
             rate only; double / triple / 6002 are engine-derived, untested live.

(b) DETECTION -- ``PlayDetector``: reader frames -> play events. It NEVER reads ``players[].elixir_raw`` of
    either side (the opponent's is the hidden value); it reads only entities and which hand is visible.
    Rules (engine-corpus evidence in L68/opp_elixir/kind_survey.out; NONE validated on reader recordings):
      * my side, crown towers (card_id < 0) and addresses already seen are ignored;
      * new bodies of the same (side, card) within ``swarm_ticks`` of that card's first new body = ONE play;
      * spawned bodies carry the PARENT's card id (engine: Witch skeletons are 'Witch' hp 81 vs the witch's
        839; hut goblins 133 vs hut 1180; golemites 1039 vs golem 5120): a new body whose max_hp is not one of
        the max_hps that card showed when it was played is a spawn, not a play;
      * a new body first seen in a non-deploying ``kind`` is a spawn (Witch / Night Witch / Tombstone spawns
        are never kind 14 in the engine corpus; fresh plays are 12/14). Hut / Furnace spawns DO show kind 14,
        so the max_hp rule is what stops those.
    Spells without bodies (log, zap, arrows, fireball, rocket, tornado, ...) are INVISIBLE: the reader decodes
    no effects, so they are never charged and the estimate runs high by their cost. Spells that drop bodies
    carrying the spell's card id (Graveyard, Goblin Barrel, Barbarian Barrel, Royal Delivery, Clone) are
    charged through those bodies. Mirror (no fixed cost) is charged as the mirrored card, i.e. 1 low.
    Not modelled: Elixir Collector production, Elixir Golem death payouts.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from . import vocab
from .live_mem import my_side_of
from .obs_contract import DEPLOYING_KINDS, REPO, _catalog_names

START_ELIXIR = 6.0
MAX_ELIXIR = 10.0
# (from_tick, elixir per tick), ascending. Raw engine units are 1e-4 elixir.
REGEN_SCHEDULE: tuple[tuple[int, float], ...] = ((0, 0.0178), (2400, 0.0357), (4800, 0.0537), (6002, 0.0))


def regen_between(t0: float, t1: float) -> float:
    """Elixir regenerated over [t0, t1) ignoring the cap."""
    total = 0.0
    for i, (lo, rate) in enumerate(REGEN_SCHEDULE):
        hi = REGEN_SCHEDULE[i + 1][0] if i + 1 < len(REGEN_SCHEDULE) else float("inf")
        a, b = max(t0, lo), min(t1, hi)
        if b > a:
            total += rate * (b - a)
    return total


class OppElixirCounter:
    """Layer (a). Feed plays in tick order with ``play``; read with ``at``. Time only moves forward."""

    def __init__(self, start: float = START_ELIXIR):
        self.tick = 0
        self.est = float(start)
        self.rebases = 0          # plays the estimate could not afford (estimate was low)
        self.rebase_total = 0.0   # elixir added by those re-bases
        self.plays: list[tuple[int, str, Optional[float]]] = []

    def _advance(self, tick: int) -> None:
        if tick > self.tick:      # capped regen is lost; rates are >= 0 so one clamp == clamping per tick
            self.est = min(MAX_ELIXIR, self.est + regen_between(self.tick, tick))
            self.tick = tick

    def at(self, tick: int) -> float:
        """Estimate at ``tick`` (plays at this tick already fed are included)."""
        self._advance(int(tick))
        return self.est

    def play(self, tick: int, key: str, cost: Optional[float]) -> None:
        self._advance(int(tick))
        self.plays.append((int(tick), key, cost))
        if cost is None:          # Mirror / unknown card: nothing to charge
            return
        if self.est < cost:
            self.rebases += 1
            self.rebase_total += cost - self.est
            self.est = float(cost)
        self.est -= cost


@dataclass
class PlayEvent:
    tick: int
    key: str              # base vocab key, e.g. 'knight', 'goblin_barrel'
    cost: Optional[float]
    n_bodies: int = 1


@dataclass
class _Open:
    event: PlayEvent
    first_tick: int
    hps: set = field(default_factory=set)


_DB = None


def card_db():
    """The shared ``clashrl.cards.CardDB`` (icebow/config/cards.yaml), as opp_est_audit builds it."""
    global _DB
    if _DB is None:
        src = str(REPO / "icebow" / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from clashrl.cards import CardDB
        _DB = CardDB(path=REPO / "icebow" / "config" / "cards.yaml")
    return _DB


def card_cost(key: str) -> Optional[float]:
    c = card_db().elixir(key)
    return None if c is None else float(c)


class PlayDetector:
    """Layer (b). ``feed(frame)`` -> the NEW opponent play events that frame reveals."""

    def __init__(self, swarm_ticks: int = 6, swarm_ticks_by_key: Optional[Mapping[str, int]] = None):
        self.swarm_ticks = int(swarm_ticks)       # UNMEASURED on the reader: a swarm's bodies land together
        # Graveyard keeps emitting skeletons for ~9.5 s (200 ticks) after one cast.
        self.swarm_ticks_by_key = {"graveyard": 200, **dict(swarm_ticks_by_key or {})}
        self.seen: set = set()
        self.open: dict[str, _Open] = {}          # key -> the latest play of that card
        self.play_hps: dict[str, set] = {}        # key -> max_hps its played bodies showed
        self.spawns = 0                           # new bodies judged spawns (not charged)
        self.unknown_ids: set = set()
        self.my_side: Optional[int] = None

    def feed(self, frame: Mapping[str, Any]) -> list[PlayEvent]:
        if self.my_side is None:
            self.my_side = my_side_of(frame)
        tick = int(frame["game_tick"])
        new: list[PlayEvent] = []
        for e in frame.get("entities") or ():
            addr = e["address"]
            if addr in self.seen:
                continue
            self.seen.add(addr)
            cid = int(e["card_id"])
            if cid < 0 or int(e["side"]) == self.my_side:
                continue
            name = _catalog_names().get(cid)
            key = vocab.engine_key(name) if name else None
            if key is None:
                self.unknown_ids.add(cid)
                continue
            hp = int(e.get("max_hp", -1))
            op = self.open.get(key)
            if op is not None and tick - op.first_tick <= self.swarm_ticks_by_key.get(key, self.swarm_ticks):
                op.event.n_bodies += 1                     # same cast: swarm body / staggered spell body
                op.hps.add(hp)
                continue
            known = self.play_hps.get(key)
            if (known and hp not in known) or int(e.get("kind", -1)) not in DEPLOYING_KINDS:
                self.spawns += 1                           # spawned by a building / troop / death
                continue
            ev = PlayEvent(tick, key, card_cost(key))
            self.open[key] = _Open(ev, tick, {hp})
            self.play_hps.setdefault(key, set()).add(hp)
            new.append(ev)
        for op in self.open.values():                      # swarm bodies widen the card's played-hp set
            self.play_hps[op.event.key] |= op.hps
        return new


class LiveOppElixir:
    """Both layers wired: ``update(frame)`` -> estimated opponent elixir at the frame's tick."""

    def __init__(self, **detector_kw: Any):
        self.detector = PlayDetector(**detector_kw)
        self.counter = OppElixirCounter()

    def update(self, frame: Mapping[str, Any]) -> float:
        for ev in self.detector.feed(frame):
            self.counter.play(ev.tick, ev.key, ev.cost)
        return self.counter.at(int(frame["game_tick"]))

