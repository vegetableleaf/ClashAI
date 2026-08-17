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


def ignore_cost_frac(db, base: str, tower_level: int = 15, enemy_level: int = 11) -> float:
    """Fraction of one Princess Tower lost if this card walks in unanswered.

    ``inf`` means "the tower cannot resolve this on its own" -- it outranges us, it is a siege
    building, or we have no stats for it (unknown is never ignorable).
    """
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
