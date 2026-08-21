"""DRILLS: short, segmented scenarios that rehearse ONE interaction at a time.

THE IDEA (project owner, 2026-08-20). A full match is three minutes and ~180 decisions, and the
payoff for a skill like "Tornado the attacker into your own King Tower" is buried somewhere in
that noise -- the policy has to stumble into the state, choose the right card, place it within a
tile, and then wait out the match to find out whether it mattered. A drill removes everything
else: put exactly that board on the table, hand the agent exactly the cards the interaction needs,
and end the episode the moment the question is answered. Success or failure in a few seconds,
thousands of repetitions, and immediate credit assignment.

WHY THIS SHOULD WORK HERE SPECIFICALLY. The pipeline audit (HANDOFF 3l) found that the live game
cannot supply enough data to learn from -- 72k decisions ever, against a 2,072-action space -- and
that the sim is the only place real learning can happen. It also found the sim's cell head could
be pushed DOWN but never UP, so placement never sharpened. Drills attack both: they multiply
effective sample count on the states that matter, and they make the reward for a good placement
immediate and unambiguous instead of a rounding error inside a 3-minute return.

WHAT A DRILL IS
---------------
A `Scenario` is data, not code: where the units start, what the scripted opponent does, which
cards the agent may hold, and two predicates -- `success` and `failure` -- each reading engine
state directly (a unit's `target`, a tower's `hp` or `active` flag, whether a unit is alive, the
clock). The episode ends the instant either fires, or at `time_limit`.

Predicates read ENGINE VALUES, never vibes. The owner's own correction on the king-activation
drill is the reason this matters: "success" there is not "the king woke up" -- the king also wakes
from ordinary chip damage, which would score a FAILED pull as a win -- it is "the attacker is now
going for the KING tower instead of the princess". That distinction is only expressible against
`unit.target`, so predicates take the engine and return a bool.

RANDOMISATION IS PART OF THE DRILL, not an afterthought: a scenario that always spawns the same
Hog at the same bridge at the same second teaches one board, and the policy will memorise the
tile. Every scenario declares what varies per repetition (lane, timing, which enemy card, our
elixir), so the skill has to generalise to count as mastered.

HOW IT PLUGS IN
---------------
`drill_env.DrillEnv` subclasses the ordinary `SimMatchEnv`, so a drill is scored by THE SAME
reward terms as a real match -- deliberately. A drill with its own bespoke reward would train a
policy that is good at the drill; using the match's own terms means the drill only concentrates
experience, it never changes the objective. Integration into full play is then a mixing ratio
rather than a hand-off, which is what keeps the skills from being forgotten the moment ordinary
training resumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# A predicate reads the engine (and the drill's own scratch dict) and answers yes/no.
Predicate = Callable[["object", dict], bool]
# A spawn is (base, team, x, y, at_seconds). team 1 = the opponent.
Spawn = Tuple[str, int, float, float, float]


@dataclass(frozen=True)
class Scenario:
    """One rehearsable interaction.

    Coordinates are the engine's: x in [0,1] left to right, y in [0,1] with OUR side at HIGH y
    (our princesses ~0.80, our king ~0.91) and the enemy at LOW y (theirs ~0.20), the river at
    ~0.50.
    """

    name: str
    goal: str                                   # one line, for the report
    tier: str = "foundational"                  # foundational | compound | matchup
    hand: Sequence[str] = ()                    # bases the agent may hold ( () = the whole deck )
    elixir: float = 10.0                        # ours at t=0
    spawns: Sequence[Spawn] = ()                # fixed board + scripted opponent, by time
    success: Optional[Predicate] = None
    failure: Optional[Predicate] = None
    time_limit: float = 12.0
    randomise: Sequence[str] = ()               # what varies per rep: lane, timing, card, elixir
    graded_by: Sequence[str] = ()               # reward terms that already price this
    prereq: Sequence[str] = ()                  # drills to master first
    # ARBITRARY ENGINE STATE, applied after the spawns land. A spawn list can only say "this card,
    # here"; a great many interactions are only themselves once the king is already awake, the
    # princess is at 60%, the clock is in overtime, or a defender is already locked onto our bow.
    # One callable covers all of those without a dataclass field per drill.
    setup: Optional[Callable] = None
    # THE HAND-WRITTEN CORRECT LINE: (card base, x, y, earliest t). Played by `run.py drills` as a
    # third column, which is the only way to tell a drill that is UNWINNABLE from one the doctrine
    # merely cannot solve -- and the second of those is a finding, not a broken scenario. Also
    # doubles as documentation: it states in coordinates what this drill thinks the answer is.
    reference: Sequence[Tuple[str, float, float, float]] = ()
    notes: str = ""

    def __post_init__(self):
        if self.success is None and self.failure is None:
            raise ValueError("scenario %r has neither a success nor a failure predicate; an "
                             "episode that can never resolve is a timer, not a drill" % self.name)


# ---------------------------------------------------------------------------------------------
# Predicate helpers. These exist so scenarios stay declarative AND so the engine-value discipline
# is enforced in one place rather than re-derived (and mis-derived) per drill.
# ---------------------------------------------------------------------------------------------

def our_towers(eng):
    return eng.towers[0]


def our_king(eng):
    t = eng.towers[0]
    return t[2] if len(t) > 2 else None


def our_princesses(eng, s=None):
    """Our princess towers -- or just the ONE the drill's interaction threatens, when the drill
    recorded a lane.

    Lane-awareness exists so a drill can carry NOISE in the other lane without that noise reading
    as the drill's own answer failing. With no lane recorded (every scenario before noise existed)
    this returns both towers, exactly as it always did.
    """
    towers = [t for t in eng.towers[0][:2]]
    lane = (s or {}).get("lane")
    if lane is None or not towers:
        return towers
    return [towers[int(lane)]] if int(lane) < len(towers) else towers


def enemy_units(eng):
    """Live enemies the DRILL IS ABOUT -- tagged noise is deliberately invisible here.

    Noise units are real to the engine and real in the observation the policy sees; they are only
    hidden from the grader. Without this, every "no enemy alive" predicate would be unsatisfiable
    the moment a distractor was added, and 12 drills use exactly that.
    """
    tag = getattr(eng, "_drill_component", None)
    out = [u for u in eng.units
           if u.team == 1 and u.hp > 0 and not getattr(u, "drill_noise", False)]
    if tag is None:
        return out
    # COMPOUND DRILL: only the component currently being graded. Set by the verdict while it walks
    # the components; unset for every ordinary drill, which therefore behaves exactly as before.
    return [u for u in out if int(getattr(u, "drill_tag", -1)) == int(tag)]


def noise_units(eng):
    """The distractors, for diagnostics that want to see them."""
    return [u for u in eng.units if u.hp > 0 and getattr(u, "drill_noise", False)]


def targets_our_king(eng, _s=None) -> bool:
    """Any live enemy is now attacking our KING TOWER.

    THE point of a Tornado king-activation, and the owner's corrected success test: the pull has
    to REDIRECT the attacker, not merely wake the tower. A king that woke from chip damage while
    the attacker keeps walking at the princess is a FAILED pull, and testing `king.active` alone
    would have scored it as a win.
    """
    king = our_king(eng)
    if king is None:
        return False
    return any(getattr(u, "target", None) is king for u in enemy_units(eng))


def targets_our_princess(eng, _s=None) -> bool:
    """Any live enemy is attacking one of our PRINCESS towers -- the failure side of the same
    question."""
    princes = our_princesses(eng)
    return any(getattr(u, "target", None) in princes for u in enemy_units(eng))


def princess_hp_lost(eng, s, limit: float) -> bool:
    """Our princesses have lost more than `limit` HP since the drill began."""
    start = (s or {}).get("princess_hp0")
    if start is None:
        return False
    return (start - sum(float(t.hp) for t in our_princesses(eng, s))) > limit


def all_enemies_dead(eng, _s=None) -> bool:
    return not enemy_units(eng)


def enemy_base_dead(base: str) -> Predicate:
    def _p(eng, _s=None):
        return not any(u.spec.base == base for u in enemy_units(eng))
    return _p


def enemy_base_alive_past(base: str, y: float) -> Predicate:
    """A named enemy is still alive AND has walked past `y` (deeper into our half)."""
    def _p(eng, _s=None):
        return any(u.spec.base == base and u.y > y for u in enemy_units(eng))
    return _p


def our_base_alive(base: str) -> Predicate:
    def _p(eng, _s=None):
        return any(u.team == 0 and u.hp > 0 and u.spec.base == base for u in eng.units)
    return _p


def enemy_tower_hp_lost(eng, s, limit: float) -> bool:
    start = (s or {}).get("enemy_tower_hp0")
    if start is None:
        return False
    return (start - sum(float(t.hp) for t in eng.towers[1][:2])) > limit


def hits_taken(s) -> int:
    """How many agent steps our princess towers took damage in -- see DrillEnv.step.

    The LEVEL-INVARIANT alternative to an HP threshold. Enemy levels roll 13-16, so the same play
    costs a different number of hitpoints every episode and a fixed HP bar cannot separate a small
    effect from the noise; the number of connections it prevents is the same at every level.
    """
    return int((s or {}).get("hits_taken", 0))


def hits_at_most(s, n: int) -> bool:
    return hits_taken(s) <= int(n)


def enemy_base_below_frac(eng, base: str, frac: float) -> bool:
    """Is every enemy `base` on the board under `frac` of its OWN max HP (or gone)?

    A FRACTION, because enemy levels roll 13-16 and an absolute HP bar means something different
    in each episode: one Earthquake takes an Elixir Collector to 22% of its bar at any level, but
    that is 1187 hitpoints at 16 and 950 at 13. Scoring the fraction is the same statement about
    the play at every level; scoring the hitpoints is not.
    """
    live = [u for u in enemy_units(eng) if u.spec.base == base]
    if not live:
        return True                                   # dead, or never there, counts as under
    return all(float(u.hp) <= frac * max(1.0, float(u.spec.hp)) for u in live)


def spent_more_than(eng, s, limit: float) -> bool:
    """The agent has committed more elixir than the interaction is worth -- the failure mode
    triage exists to prevent, and one a purely outcome-based predicate would never catch."""
    return float((s or {}).get("spent", 0.0)) > limit


def both(*ps: Predicate) -> Predicate:
    def _p(eng, s=None):
        return all(p(eng, s) for p in ps)
    return _p


def either(*ps: Predicate) -> Predicate:
    def _p(eng, s=None):
        return any(p(eng, s) for p in ps)
    return _p


def negate(p: Predicate) -> Predicate:
    def _p(eng, s=None):
        return not p(eng, s)
    return _p


# ---------------------------------------------------------------------------------------------
# The PLAY LEDGER: what the agent actually played, where, and in what order. A card that was
# played and then died leaves the same board as one never played, so outcome-only predicates
# cannot express "never sent the Hog" or "rocket before tornado" -- these can.
# ---------------------------------------------------------------------------------------------

def plays(s):
    return list((s or {}).get("plays", ()))


def played(s, *bases) -> bool:
    """Did we deploy any of these cards (and did the elixir actually leave the bar)?"""
    want = set(bases)
    return any(p["base"] in want for p in plays(s))


def n_plays(s) -> int:
    return len(plays(s))


def first_play_t(s, base):
    """Seconds into the drill when `base` was first deployed, or None."""
    for p in plays(s):
        if p["base"] == base:
            return float(p["t"])
    return None


def played_before(s, first: str, second: str) -> bool:
    """Both were played, and `first` went down strictly earlier -- an ORDER test.

    Order is a real skill and an invisible one: the same two cards in the other sequence is a
    different play entirely (rocket-then-tornado vs tornado-then-rocket), and the board a few
    seconds later can look identical.
    """
    a, b = first_play_t(s, first), first_play_t(s, second)
    return a is not None and b is not None and a < b


def play_xy(s, base):
    """Where `base` was first put down, or None."""
    for p in plays(s):
        if p["base"] == base:
            return (float(p["x"]), float(p["y"]))
    return None


# ---------------------------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------------------------
_REGISTRY: Dict[str, Scenario] = {}


def register(sc: Scenario) -> Scenario:
    if sc.name in _REGISTRY:
        raise ValueError("duplicate scenario name: %s" % sc.name)
    _REGISTRY[sc.name] = sc
    return sc


def get(name: str) -> Scenario:
    return _REGISTRY[name]


def all_scenarios() -> List[Scenario]:
    return list(_REGISTRY.values())


def by_tier(tier: str) -> List[Scenario]:
    return [s for s in _REGISTRY.values() if s.tier == tier]


def names() -> List[str]:
    return sorted(_REGISTRY)


def load_deck_scenarios(deck: str) -> int:
    """Import the deck's own drill definitions. Returns how many are registered.

    Deck-specific drills live in `sim/drills_<deck>.py` so the framework here stays deck-agnostic
    and the two decks cannot drift into each other's doctrine.
    """
    import importlib
    try:
        importlib.import_module("clashrl.sim.drills_%s" % deck)
    except ModuleNotFoundError:
        pass
    return len(_REGISTRY)


def load_all() -> int:
    """Import EVERY `drills_*.py` in this package, whichever deck we are.

    The registry is populated by import side-effect, so a trainer that never imported the deck's
    drill module would mix in an empty pool and silently train ordinary matches -- a failure that
    looks exactly like "drills do not help". Discovering the modules removes the chance to forget.
    """
    import importlib
    import pkgutil
    for m in pkgutil.iter_modules(__path__ if "__path__" in dir() else []):
        pass
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in sorted(os.listdir(here)):
        if fn.startswith("drills_") and fn.endswith(".py"):
            try:
                importlib.import_module("clashrl.sim.%s" % fn[:-3])
            except Exception:  # noqa: BLE001 -- a broken drill file must not kill training
                continue
    return len(_REGISTRY)
