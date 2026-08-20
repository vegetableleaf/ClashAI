"""What does it COST to ignore this? The question the bot never asked.

THE GAP THIS FILLS
------------------
Every counter rule in this project answers "what beats X". None of them answered "is X worth
beating". So the policy would spend a card on a lone Skeletons -- and it is not close to correct:
at tower level 15 an ignored Skeletons deals **17 damage, 0.4% of a Princess Tower**, while the
cheapest card in the deck costs 1 elixir and a tempo beat. Every guide states the principle
("if a card don't solve a situation or don't affect the battle, don't play it"; "don't defend
single weak units when accepting 100-200 damage costs less elixir") but always as prose, never as
a number, so nothing downstream could act on it.

The number is computable from our own card DB, so it is here rather than in a prompt.

THE MODEL
---------
One lone unit walks into a Princess Tower and neither side gets help. The tower kills bodies one
at a time; each body deals its DPS until the tower reaches it. `FIRST_HIT` reflects the tower's
slower first shot. The result is expressed as a FRACTION OF OUR OWN TOWER'S HP, because that is
the currency the decision is actually in.

It is deliberately optimistic about our side (no second tower, no king, no defenders), so a card
this calls ignorable is ignorable with margin. It is NOT a damage prediction -- it is a triage
threshold.

THE RANGE CORRECTION, which the naive version got badly wrong
-------------------------------------------------------------
The first cut of this table said the enemy PRINCESS was ignorable at 0.4%, and a Dart Goblin at
1.4%. That is the model's assumption failing, not a fact: a unit whose attack range exceeds the
tower's 7.5 tiles never enters the trade at all. It chips forever and the tower never answers.
So anything that outranges the tower is UNBOUNDED, never ignorable, regardless of how little
health it has. Same for siege.
"""
from __future__ import annotations

from typing import Optional

from . import levels

#: Princess Tower hit speed (s) and the slower first shot after acquiring a target.
TOWER_HIT_SPEED = 0.8
TOWER_FIRST_HIT = 1.0
#: Princess Tower attack range in tiles (sim.tower_range).
TOWER_RANGE = 7.5

#: Below this fraction of our tower, a lone threat is not worth a card.
IGNORE_FRAC = 0.05
#: Above this, it must be answered -- letting it through loses the tower outright over a match.
MUST_ANSWER_FRAC = 0.20


def _num(c: dict, *keys) -> Optional[float]:
    for k in keys:
        v = c.get(k)
        if v:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def tower_dps(tower_level: int = 15) -> float:
    dmg = levels.TOWER_DMG[min(int(tower_level), len(levels.TOWER_DMG) - 1)]
    return dmg / TOWER_HIT_SPEED


def tower_hp(tower_level: int = 15) -> int:
    return levels.PRINCESS_HP[min(int(tower_level), len(levels.PRINCESS_HP) - 1)]


def _bodies(db, base: str, enemy_level: int = 11):
    """[(hp, dps)] for one card's bodies, or None when the tower cannot resolve it at all."""
    c = db.get(base) if db is not None else None
    if not c:
        return None
    if str(c.get("type", "")).lower() == "spell":
        return None                       # a spell is not a body; triage does not apply
    hp = _num(c, "hitpoints", "hp")
    dmg = _num(c, "damage", "damage_per_hit")
    hs = _num(c, "hit_speed", "hit_speed_s")
    if not hs and (dmg or _num(c, "death_damage")) and hp:
        flags = c.get("flags") or []
        if c.get("kamikaze") or "kamikaze" in flags:
            return None                   # handled by _burst_cost: it hits ONCE and dies
    if not hp or not dmg or not hs:
        return None                       # unknown card: never assume it is safe to ignore
    rng = _num(c, "range", "range_tiles") or 0.0
    if rng >= TOWER_RANGE or bool(c.get("siege")):
        return None                       # outranges the tower: it chips forever, unanswered
    count = max(1, int(c.get("count") or 1))
    hp = levels.scale(hp, enemy_level, 11)
    dmg = levels.scale(dmg, enemy_level, 11)
    return [(hp, dmg / hs)] * count


def _dealt(bodies, tower_level: int) -> float:
    """Damage a group lands while a single-target tower works through it, body by body.

    SUPERLINEAR IN COUNT, which is the whole reason this is not a sum of per-card numbers: each
    extra body extends the time EVERY surviving body keeps firing. Three Skeletons cost 0.4% of a
    tower; twelve are not 4 x 0.4%, because the tower needs four times as long to clear them and
    the tail is shooting for all of it.
    """
    dps_t = tower_dps(tower_level)
    elapsed, dealt = 0.0, 0.0
    for hp, dps in bodies:
        elapsed += hp / dps_t                            # tower finishes this body at `elapsed`
        dealt += dps * max(0.0, elapsed - TOWER_FIRST_HIT)
    return dealt



def _burst_cost(db, base: str, tower_level: int, enemy_level: int):
    """Tower HP a KAMIKAZE card lands on the way in, or None if it is not one.

    These cards have `hitpoints` and `damage` but no `hit_speed`, because they do not have one --
    they hit once and die. `_bodies` requires all three, so it returned None for every one of them
    and `ignore_cost_frac` read that as "the tower cannot resolve this" -> inf -> NEVER IGNORABLE.
    A 1-elixir Ice Spirit therefore outranked a Golem in every priority comparison, and Wall
    Breakers read as must-answer-at-any-cost (2026-08-20).

    The honest price is the burst itself, once per body, plus anything it leaves behind: a Battle
    Ram breaks into two Barbarians and a Skeleton Barrel drops seven Skeletons, and those bodies
    ARE resolved by the tower, so they go through the ordinary superlinear model.
    """
    c = db.get(base) if db is not None else None
    if not c:
        return None
    flags = c.get("flags") or []
    if not (c.get("kamikaze") or "kamikaze" in flags):
        return None
    hit = _num(c, "damage", "damage_per_hit") or 0.0
    if not hit:
        hit = _num(c, "death_damage") or 0.0
    count = max(1, int(c.get("count") or 1))
    dealt = levels.scale(hit, enemy_level, 11) * count
    spawn = c.get("spawns") or {}
    n_death = int(spawn.get("on_death") or 0)
    if n_death and spawn.get("unit"):
        # what it LEAVES BEHIND still has to be chewed through by the tower
        sub = _bodies(db, str(spawn["unit"]), enemy_level)
        if sub:
            per = sub[0]
            dealt += _dealt([per] * n_death, tower_level)
    return dealt

def ignore_cost_frac(db, base: str, tower_level: int = 15, enemy_level: int = 11) -> float:
    """Fraction of one Princess Tower lost if this card walks in unanswered.

    ``inf`` means "the tower cannot resolve this on its own" -- it outranges us, it is a siege
    building, or we have no stats for it (unknown is never ignorable).
    """
    burst = _burst_cost(db, base, tower_level, enemy_level)
    if burst is not None:
        return burst / float(tower_hp(tower_level))
    bodies = _bodies(db, base, enemy_level)
    if bodies is None:
        return float("inf")
    return _dealt(bodies, tower_level) / float(tower_hp(tower_level))


def triage(db, base: str, tower_level: int = 15, enemy_level: int = 11) -> str:
    """'ignore' | 'cheap' | 'must_answer' -- how much this threat is worth spending on."""
    f = ignore_cost_frac(db, base, tower_level, enemy_level)
    if f < IGNORE_FRAC:
        return "ignore"
    if f >= MUST_ANSWER_FRAC:
        return "must_answer"
    return "cheap"


def group_ignore_frac(db, bases, tower_level: int = 15, enemy_level: int = 11) -> float:
    """Ignore cost of a whole enemy group, pooling every body into ONE clearing queue.

    Not a sum of the per-card numbers, which is what this did first and it was wrong in the
    direction that matters: four Skeletons cards came to 4 x 0.38% = 1.5% and triaged as
    "ignorable", when twelve skeletons chewing on a tower plainly are not. The tower kills one
    body at a time, so every extra body extends the window for all the survivors -- pooling them
    captures that and summing cannot.
    """
    pooled = []
    for b in bases:
        bodies = _bodies(db, b, enemy_level)
        if bodies is None:
            return float("inf")
        pooled.extend(bodies)
    if not pooled:
        return 0.0
    return _dealt(pooled, tower_level) / float(tower_hp(tower_level))


# ---------------------------------------------------------------------------------------------
# CAN THIS CARD EVEN ANSWER THAT? (2026-08-20, user report: "the advisor is suggesting unrealistic
# counters... placing knight on a balloon (knight can't even see the balloon) or rocketing wall
# breakers (a horrible elixir trade)".)
#
# The advisor prompt already forbade both IN WORDS and still produced them, exactly like the triage
# tier above: the fix is KB-grounded CODE that vetoes the pick, not a louder sentence. Used by the
# live advisor path and by the sim's doctrine so both sides refuse the same impossible answers.

# Spells that cannot touch a flying unit: the log ROLLS along the ground, the quake SHAKES it.
GROUND_ONLY_SPELLS = frozenset({"the_log", "earthquake", "barbarian_barrel"})
# Spawn spells are threats in their own right (units land), so they are never "just a spell".
SPAWN_SPELL_BASES = frozenset({"graveyard", "goblin_barrel", "royal_delivery"})
# A spell this much MORE expensive than everything it would erase is a losing trade by itself.
SPELL_OVERKILL_MARGIN = 3.0


def can_touch(db, base: str, threat_bases) -> bool:
    """False when every unit in the threat FLIES and `base` cannot reach the air.

    Air is answered by an air-attacking troop/building, by tornado (it repositions flying units
    even though it deals no real damage), or by a damage spell that is not ground-only. A knight
    cannot see a balloon at all -- that suggestion was the user's report, and it came from a
    table that only reasoned about roles.
    """
    bases = [b for b in (threat_bases or ()) if b]
    if not bases:
        return True
    if not all(bool(db.is_flying(b)) for b in bases):
        return True                      # something in the group walks -> any card can engage it
    if db.attacks_air(base):
        return True
    if base == "tornado":
        return True                      # pulls air: repositioning IS the answer (king activation)
    return db.kind(base) == "spell" and base not in GROUND_ONLY_SPELLS


def trade_sane(db, base: str, threat_bases) -> bool:
    """False for a SPELL that costs far more than the whole group it would erase.

    Only spells are judged: a troop survives its defence and keeps working, so its cost is not
    spent the way a spell's is. Rocket (6) on wall breakers (2) is the reported case -- a 4-elixir
    loss for a hit the log takes for 2.
    """
    if db.kind(base) != "spell" or base in SPAWN_SPELL_BASES:
        return True
    bases = [b for b in (threat_bases or ()) if b]
    if not bases:
        return True
    group = sum(float(db.elixir(b) or 0.0) for b in bases)
    cost = float(db.elixir(base) or 0.0)
    return cost < group + SPELL_OVERKILL_MARGIN


def pick_invalid(db, base: str, threat_bases):
    """Why `base` cannot answer this threat group, or None when it is a legal answer."""
    if not base:
        return None
    if not can_touch(db, base, threat_bases):
        return "cannot touch an all-air group"
    if not trade_sane(db, base, threat_bases):
        group = sum(float(db.elixir(b) or 0.0) for b in (threat_bases or ()) if b)
        return "a %.0f-elixir spell on a %.0f-elixir group" % (float(db.elixir(base) or 0.0), group)
    return None


# ---------------------------------------------------------------------------------------------
# ARE THEY BUILDING IN THE BACK? (2026-08-20, user rule.)
#
# The beatdown signature: elixir committed deep in their OWN half with nothing on ours yet. It is
# the one board where a full elixir bar should buy a DEFENSIVE X-Bow rather than an offensive one
# -- the offensive bow walks into a push that is already paid for and is blocked before it locks.
#
# Coordinates: both the sim and the live frame put THEIR princesses at y ~ 0.204 and treat y > 0.42
# as our half, so one threshold pair serves both sides.
BACK_Y = 0.28              # at or behind their princess line
OUR_HALF_Y = 0.42          # the river line _needs_answer already triages on
BACK_MIN_ELIXIR = 4.0      # a lone cheap card in the back is cycling, not building


def massing_in_back(db, units, back_y: float = BACK_Y, our_half_y: float = OUR_HALF_Y,
                    min_elixir: float = BACK_MIN_ELIXIR) -> bool:
    """True when they are BUILDING: `units` is [(x, y, base)] of enemy units.

    Requires BOTH halves of the signature -- meaningful elixir parked deep in their half, and
    nothing of theirs committed on ours. Once a push crosses the river this goes False and the
    ordinary defensive path (counter table, threat gate) takes over, which is why the caller can
    treat it as "the board is quiet BUT it is about to stop being quiet".
    """
    back = 0.0
    for u in (units or ()):
        try:
            x, y, base = float(u[0]), float(u[1]), str(u[2])
        except Exception:  # noqa: BLE001 -- a malformed track is not a beatdown
            continue
        if y > our_half_y:
            return False                      # already committed on our half: this is a defence
        if y <= back_y and base:
            back += float(db.elixir(base) or 0.0)
    return back >= min_elixir
