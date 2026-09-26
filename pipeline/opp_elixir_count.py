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
    Rules (see ``PlayDetector``; engine evidence in L68/opp_elixir/kind_survey.out and gap_sim.out; NONE
    validated on reader recordings):
      * my side, crown towers (card_id < 0) and addresses already seen are ignored;
      * new bodies of the same card in one frame, or within ``swarm_ticks`` (100) of that card's last play = ONE
        play (no same-card re-play within 111 ticks in the corpus);
      * spawned bodies carry the PARENT's card id (engine: Witch skeletons are 'Witch' hp 81 vs the witch's
        839; hut goblins 133 vs hut 1180; golemites 1039 vs golem 5120), so a new group is a spawn when a
        higher-max_hp body of that card is (or <= 60 ticks ago was) on the board, or a lower-max_hp one just
        died beside it;
      * ``kind`` is NOT required: fresh troops go 14 -> 15 and buildings 12 -> 13 at ~20 ticks (kind_survey),
        so a first sight after a >= 1 s reader gap is still charged.
    Spells without bodies (log, zap, arrows, fireball, rocket, tornado, ...) are INVISIBLE: the reader decodes
    no effects, so they are never charged and the estimate runs high by their cost. Spells that drop bodies
    carrying the spell's card id (Graveyard, Goblin Barrel, Barbarian Barrel, Royal Delivery, Clone) are
    charged through those bodies. Mirror (no fixed cost) is charged as the mirrored card, i.e. 1 low.
    Not modelled: Elixir Collector production, Elixir Golem death payouts.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from . import vocab
from .live_mem import my_side_of
from .obs_contract import REPO, _catalog_names

START_ELIXIR = 6.0
MAX_ELIXIR = 10.0
# (from_tick, elixir per tick), ascending. Raw engine units are 1e-4 elixir.
REGEN_SCHEDULE: tuple[tuple[int, float], ...] = ((0, 0.0178), (2400, 0.0357), (4800, 0.0537), (6002, 0.0))


def regen_between(t0: float, t1: float, schedule: tuple[tuple[int, float], ...] = REGEN_SCHEDULE) -> float:
    """Elixir regenerated over [t0, t1) ignoring the cap, under ``schedule`` (default: the real engine's)."""
    total = 0.0
    for i, (lo, rate) in enumerate(schedule):
        hi = schedule[i + 1][0] if i + 1 < len(schedule) else float("inf")
        a, b = max(t0, lo), min(t1, hi)
        if b > a:
            total += rate * (b - a)
    return total


class OppElixirCounter:
    """Layer (a). Feed plays in tick order with ``play``; read with ``at``. Time only moves forward.
    ``schedule``: the regen schedule of the engine being counted, (from_tick, elixir per tick) ascending; None = the
    real engine's ``REGEN_SCHEDULE`` (live, and every caller before T12b). A simulator with a different schedule passes
    its own (``royale_env.RoyalePoolEnv.elixir_regen_schedule``), so the counter's error in simulation is the real one
    (missed plays) and not a schedule mismatch."""

    def __init__(self, start: float = START_ELIXIR, schedule: Optional[tuple[tuple[int, float], ...]] = None):
        self.schedule = REGEN_SCHEDULE if schedule is None else tuple((int(t), float(r)) for t, r in schedule)
        self.tick = 0
        self.est = float(start)
        self.rebases = 0          # plays the estimate could not afford (estimate was low)
        self.rebase_total = 0.0   # elixir added by those re-bases
        self.plays: list[tuple[int, str, Optional[float]]] = []

    def _advance(self, tick: int) -> None:
        if tick > self.tick:      # capped regen is lost; rates are >= 0 so one clamp == clamping per tick
            self.est = min(MAX_ELIXIR, self.est + regen_between(self.tick, tick, self.schedule))
            self.tick = tick

    def regen(self, t0: float, t1: float) -> float:
        """``regen_between`` under this counter's schedule."""
        return regen_between(t0, t1, self.schedule)

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
    """Layer (b). ``feed(frame)`` -> the NEW opponent play events that frame reveals.

    Per frame, the opponent's new addresses are grouped by card. New bodies of a card within ``swarm_ticks``
    of its last charged play join that play: the same side never re-played the same card within 111 ticks in
    207,639 corpus re-plays (L68/opp_elixir/replay_gap.out), so 100 ticks absorbs staggered swarm / spell
    bodies (Goblin Barrel goblins land 60-80 ticks after the cast) and early spawns (Evo Skeletons) for free.
    Otherwise a group is a SPAWN (never charged) when
      * a body of the same card with a HIGHER max_hp is on the board, or left it <= ``parent_memory`` ticks ago
        counted from the first frame WITHOUT it, so a reader gap does not age it out (a live or just-dead
        parent: Witch 839 -> skeletons 81, Hut 1180 -> goblins 133, Golem 5120 -> golemites 1039, Skeleton
        Barrel 532 -> skeletons 81 20-40 ticks after the balloon vanishes), or
      * a body of the same card with a LOWER max_hp left the board (same memory) within ``death_radius`` of
        the group (a death spawn stronger than its parent: Phoenix egg -> Phoenix, Goblin Cage -> Brawler);
    otherwise it is ONE play, charged once however late it is first seen (``kind`` is not used: a fresh body
    leaves deploy kinds 12/14 after ~20 ticks, so any reader gap >= 1 s would lose the play). The reference is
    always a body recently on the board, so a spawn's max_hp never becomes the test for a later wave.
    """

    def __init__(self, swarm_ticks: int = 100, swarm_ticks_by_key: Optional[Mapping[str, int]] = None,
                 death_radius: float = 1500.0, parent_memory: int = 60):
        self.swarm_ticks = int(swarm_ticks)
        self.parent_memory = int(parent_memory)   # engine frames: death spawns land <= 40 ticks after the parent
        # Graveyard keeps emitting skeletons for ~9.5 s (200 ticks) after one cast.
        self.swarm_ticks_by_key = {"graveyard": 200, **dict(swarm_ticks_by_key or {})}
        self.death_radius = float(death_radius)   # engine units (1000 = 1 tile); UNMEASURED
        self.reset()

    def reset(self) -> None:
        self.seen: set = set()
        self.open: dict[str, tuple[PlayEvent, int]] = {}   # key -> (latest play of that card, its tick)
        # addr -> ((key, max_hp, x, y), tick of the first frame it was missing from, None while on the board);
        # counting from the first frame WITHOUT it (not its last sighting) keeps a parent through a reader gap
        self.recent: dict[Any, tuple[tuple[str, int, float, float], Optional[int]]] = {}
        self.play_hp: dict[str, int] = {}         # key -> strongest max_hp a CHARGED group of it showed
        self.spawns = 0                           # new bodies judged spawns (not charged)
        self.unknown_ids: set = set()
        self.my_side: Optional[int] = None

    def feed(self, frame: Mapping[str, Any]) -> list[PlayEvent]:
        if self.my_side is None:
            try:
                self.my_side = my_side_of(frame)
            except ValueError:                    # no visible hand (loading / end screen): nothing to attribute
                return []
        tick = int(frame["game_tick"])
        cur: dict[Any, tuple[str, int, float, float]] = {}
        groups: dict[str, dict[Any, tuple[str, int, float, float]]] = {}   # key -> {new addr: body}
        for e in frame.get("entities") or ():
            cid = int(e["card_id"])
            if cid < 0 or int(e["side"]) == self.my_side:
                continue
            name = _catalog_names().get(cid)
            key = vocab.engine_key(name) if name else None
            if key is None:
                self.unknown_ids.add(cid)
                continue
            body = (key, int(e.get("max_hp", -1)), float(e["x"]), float(e["y"]))
            cur[e["address"]] = body
            if e["address"] not in self.seen:
                self.seen.add(e["address"])
                groups.setdefault(key, {})[e["address"]] = body
        self.recent = {a: (b, tick if gone is None else gone) for a, (b, gone) in self.recent.items() if a not in cur}
        self.recent = {a: bg for a, bg in self.recent.items() if tick - bg[1] <= self.parent_memory}
        self.recent.update((a, (b, None)) for a, b in cur.items())
        new: list[PlayEvent] = []
        for key, group in groups.items():
            bodies = list(group.values())
            op = self.open.get(key)
            if op is not None and tick - op[1] <= self.swarm_ticks_by_key.get(key, self.swarm_ticks):
                op[0].n_bodies += len(bodies)             # same cast: swarm body / staggered spell body
                continue
            # max_hp <= 0 = unreadable (engine frames show e.g. a Witch at -1 for stretches): such a group can
            # never be proven a spawn; such a BOARD body is a parent iff the group is weaker than the strongest
            # body this card was ever charged with (a spawn-class hp; spawns never enter play_hp).
            m = max((b[1] for b in bodies if b[1] > 0), default=float("inf"))
            board = [b for a, (b, _) in self.recent.items() if b[0] == key and a not in group]
            parent = any(b[1] > m or (b[1] <= 0 and m < self.play_hp.get(key, 0)) for b in board)
            dead = [b for a, (b, _) in self.recent.items() if a not in cur and b[0] == key and 0 < b[1] < m]
            death_spawn = any((d[2] - b[2]) ** 2 + (d[3] - b[3]) ** 2 <= self.death_radius ** 2
                              for d in dead for b in bodies)
            if parent or death_spawn:
                self.spawns += len(bodies)
                continue
            ev = PlayEvent(tick, key, card_cost(key), len(bodies))
            self.open[key] = (ev, tick)
            if m != float("inf"):
                self.play_hp[key] = max(self.play_hp.get(key, 0), m)
            new.append(ev)
        return new


class LiveOppElixir:
    """Both layers wired: ``update(frame)`` -> estimated opponent elixir at the frame's tick. One match per
    state; it resets itself when the tick goes backwards or the battle object changes (``reset()`` by hand)."""

    def __init__(self, **detector_kw: Any):
        self.detector = PlayDetector(**detector_kw)
        self.reset()

    def reset(self) -> None:
        self.detector.reset()
        self.counter = OppElixirCounter()
        self.battle: Any = None

    def update(self, frame: Mapping[str, Any]) -> float:
        tick = int(frame["game_tick"])
        battle = (frame.get("chain") or {}).get("battle")
        if tick < self.counter.tick or (battle is not None and self.battle is not None and battle != self.battle):
            self.reset()
        self.battle = battle if battle is not None else self.battle
        for ev in self.detector.feed(frame):
            self.counter.play(ev.tick, ev.key, ev.cost)
        return self.counter.at(tick)
