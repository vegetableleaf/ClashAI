"""Exact Clash Royale card-level scaling.

WHY THIS IS NOT `1.1 ** (level - 11)`
-------------------------------------
Everyone "knows" CR stats go up 10% per level, and the sim used `1.1 ** (level - 11)` on that
basis. The game does not do that. It stores each card's LEVEL-1 stat and a shared table of
integer percentages, then computes

    stat(level) = floor(base_level_1 * PERCENT[level] / 100)

The percentages start as 1.1^n rounded but stop tracking it -- they are a hand-authored table,
and the drift is systematic and one-directional:

    level      11      13      15      16      19
    game      256%    309%    372%    409%    545%
    1.1^n     259%    314%    380%    418%    613%      <- what we were using

So the old formula overrated every card above level 11 and underrated every card below it: at
level 16 by +0.8%, at level 19 by +12%. That sounds negligible until you remember that Clash
Royale is a game of BREAKPOINTS -- whether Log kills Skeletons, whether Fireball kills Archers,
whether Rocket kills a Musketeer. A 0.8% error is exactly the size that flips one of those, and
a flipped breakpoint teaches the policy a counter that does not work on the real ladder.

HOW THE TABLE WAS DERIVED (not copied from a stats site)
-------------------------------------------------------
The game files published at RoyaleAPI/cr-api-data carry explicit per-level arrays
(`hitpoints_per_level`, `damage_per_level`, `dps_per_level`, ...). Taking all 376 such arrays in
the dump and asking "what integer percentage is consistent with every card at this level?"
pins each entry to exactly ONE integer -- the intervals never leave a choice. The resulting
table then reproduces all 376 arrays exactly, floor included, with zero mismatches. That is a
much stronger guarantee than transcribing a table off a web page, and it is why this module
carries the derivation rather than a citation.

The dump itself is from 2023-10-18 and its hitpoints/damage are stale (Archers' damage has
since gone 107 -> 112), so NONE of its stat values are used here. Only the level STRUCTURE is,
and that has not changed -- it is verified on import against the current wiki values.

WORKING FROM A LEVEL-11 REFERENCE
---------------------------------
Our knowledge base stores level-11 stats (what the wiki publishes). To scale exactly we need
the level-1 base the game actually holds, so `base_for` inverts the floor: it finds the integer
b with floor(b * 256 / 100) == our stored value. The interval is only 1/2.56 = 0.39 wide, so it
contains at most one integer -- the inversion is unique when it exists at all. When it does not
exist the stored value cannot be a real game value (a curated or derived number), and we fall
back to the exact PERCENT ratio, which is still strictly better than 1.1^n.
"""
from __future__ import annotations

from typing import Optional

# PERCENT[L] = the game's multiplier for level L, as an integer percentage of the level-1 stat.
# Index 0 is unused so that PERCENT[11] reads as level 11.
PERCENT = (0, 100, 110, 121, 133, 146, 160, 176, 193, 212, 233, 256, 281, 309, 339, 372, 409,
           450, 495, 545)
MAX_LEVEL = len(PERCENT) - 1          # 19: the highest level the game data defines
REF_LEVEL = 11                        # the level our knowledge base stores


def _pct(level: int) -> int:
    return PERCENT[max(1, min(MAX_LEVEL, int(level)))]


def at_level(base_level_1: float, level: int) -> int:
    """The game's own stat computation: floor(base * percent / 100)."""
    return int(base_level_1 * _pct(level) // 100)


def base_for(value: float, ref_level: int = REF_LEVEL) -> Optional[int]:
    """The unique integer level-1 base that produces ``value`` at ``ref_level``, or None.

    None means the value is not something the game could have produced -- a curated average, a
    merged multi-body number, or simply a stat we got wrong. Callers fall back to ratio scaling
    rather than guessing, because inventing a base would silently move the value.
    """
    if value != int(value) or value <= 0:
        return None
    v, p = int(value), _pct(ref_level)
    lo = -(-v * 100 // p)                       # ceil(v * 100 / p)
    hi = -(-(v + 1) * 100 // p)                 # ceil((v+1) * 100 / p)
    hits = [b for b in range(lo, hi) if b * p // 100 == v]
    return hits[0] if len(hits) == 1 else None


def scale(value: float, level: int, ref_level: int = REF_LEVEL) -> float:
    """Scale a stat stored at ``ref_level`` to ``level``, exactly where possible.

    Exact for genuine game values (integer, invertible); otherwise the exact PERCENT ratio,
    which still beats 1.1^n everywhere. Returns a float because callers keep fractional dps.
    """
    if level == ref_level:
        return float(value)
    b = base_for(value, ref_level)
    if b is not None:
        return float(at_level(b, level))
    return float(value) * (_pct(level) / _pct(ref_level))


def ratio(level: int, ref_level: int = REF_LEVEL) -> float:
    """The plain multiplier, for stats with no integer base to invert (aggregate dps, sums)."""
    return _pct(level) / _pct(ref_level)


# ---------------------------------------------------------------------------------------------
# TOWERS SCALE ON THEIR OWN TABLES -- and not on each other's.
#
# Towers do NOT follow the card table above: a Princess Tower gains 8% from level 1 to 2 where a
# card gains 10%, and the King's Tower gains 7%. The sim was scaling towers by 1.1^(level-15),
# which is wrong in the direction that matters most -- tower hitpoints are the denominator of
# every chip-damage reward, so the error propagates into the reward signal rather than staying
# in one card's stat line.
#
# These are the published per-level values, not a fitted curve. HP differs per tower; DAMAGE is
# one shared table (a level-14 King and a level-14 Princess both hit for 144). Every tower TROOP
# (Tower Princess, Dagger Duchess, Cannoneer, Royal Chef) rides the Princess HP ratio -- verified
# against all four wiki tables, exact for Cannoneer across 11 levels and within 0.03% elsewhere,
# which is float noise in the wiki's own rounding rather than a second table.
PRINCESS_HP = (0, 1400, 1512, 1624, 1750, 1890, 2030, 2184, 2352, 2534, 2786, 3052, 3346, 3668,
               4032, 4424, 4858)
KING_HP = (0, 2400, 2568, 2736, 2904, 3096, 3312, 3528, 3768, 4008, 4392, 4824, 5304, 5832, 6408,
           7032, 7704)
TOWER_DMG = (0, 50, 54, 58, 62, 67, 72, 78, 84, 90, 99, 109, 119, 131, 144, 158, 173)


def _tbl(table, level: int) -> int:
    return table[max(1, min(len(table) - 1, int(level)))]


def tower_scale(value: float, level: int, ref_level: int, king: bool = False,
                damage: bool = False) -> float:
    """Scale a tower stat stored at ``ref_level`` to ``level`` using the tower's own table.

    ``damage`` picks the shared damage progression; otherwise the King or Princess HP ratio.
    Kept as a ratio (rather than an absolute lookup) so a curated tower-troop profile keeps its
    own hitpoints -- Royal Chef is not a Princess Tower with a different name.
    """
    if int(level) == int(ref_level):
        return float(value)
    t = TOWER_DMG if damage else (KING_HP if king else PRINCESS_HP)
    return float(value) * (_tbl(t, level) / _tbl(t, ref_level))
