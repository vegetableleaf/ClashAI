"""Deck predicates for tests that only make sense for a deck that actually HOLDS the card.

icebow/ and hogeq/ are one agent with two decks, and a large part of the suite is shared verbatim.
Some of it is not shareable: a test for the X-Bow overcommit ledger, the Rocket value branch or the
Tornado bad-pull charge is testing a REWARD TERM THAT ONLY EXISTS FOR THE DECK THAT PLAYS THE CARD.
Run against the other deck those tests do not fail meaningfully -- they raise `StopIteration` out of
a `next(... if k.startswith("x_bow"))` lookup, or `ValueError: 'rocket' is not in list`. That was
hogeq's entire 42-item "test debt": not one of the 42 described a hogeq behaviour.

The honest answer is neither to delete them (the icebow deck needs them) nor to leave them red
(a suite with known failures cannot report a regression). It is to SKIP THEM WITH A REASON, keyed
on the deck, so:

  * the file stays byte-identical in both decks -- one test, two decks, no divergence to maintain;
  * icebow keeps running every one of them;
  * hogeq reports them as skipped, each with the card that is missing;
  * and if a deck is ever changed to hold the card, the tests light up again by themselves rather
    than staying silently switched off.

Use `requires_cards` for a deck-card dependency and `requires_env_attr` for a reward term that the
deck's `SimMatchEnv` does not define at all.

    @requires_cards("x_bow", why="the X-Bow overcommit ledger")
    class XbowRewardTests(unittest.TestCase):
        ...
"""
from __future__ import annotations

import functools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.cards import CardDB       # noqa: E402
from clashrl.config import Config      # noqa: E402


@functools.lru_cache(maxsize=1)
def deck_bases() -> frozenset:
    """The BASE card keys this deck plays, evolution suffix stripped ('tesla_evo' -> 'tesla').

    Read through `CardDB.deck_names()` -- the same accessor `SimMatchEnv` builds `deck_keys` from --
    rather than by re-parsing cards.yaml, so a deck change cannot leave this predicate stale.
    """
    db = CardDB(Config.load())
    out = set()
    for k in db.deck_names():
        k = str(k or "").strip()
        if k:
            out.add(k[:-4] if k.endswith("_evo") else k)
    return frozenset(out)


def deck_has(*cards: str) -> bool:
    return all(c in deck_bases() for c in cards)


def requires_cards(*cards: str, why: str = ""):
    """Skip unless THIS deck holds every named card."""
    missing = [c for c in cards if c not in deck_bases()]
    reason = "deck-specific: %s needs %s, and this deck plays %s" % (
        why or "this test", ", ".join(sorted(missing)) or ", ".join(cards),
        ", ".join(sorted(deck_bases())))
    return unittest.skipIf(bool(missing), reason)


def requires_env_attr(*attrs: str, why: str = ""):
    """Skip unless this deck's SimMatchEnv defines every named attribute.

    For reward machinery that was REMOVED for a deck rather than merely left inert -- the X-Bow /
    Rocket / Tornado terms stripped from hogeq in I10. Checked against the class, so it costs no
    environment construction.
    """
    from clashrl.sim.env import SimMatchEnv

    # instance attributes are set in __init__, so the class check has to be a source check
    import inspect
    src = inspect.getsource(SimMatchEnv)
    missing = [a for a in attrs if ("self.%s" % a) not in src]
    reason = "deck-specific: %s needs SimMatchEnv.%s, which this deck does not define" % (
        why or "this test", ", ".join(missing) or ", ".join(attrs))
    return unittest.skipIf(bool(missing), reason)


# --- deck-agnostic card pickers ------------------------------------------------------------------
# For tests whose SUBJECT is an engine or reward rule rather than a card: "a damage spell is not a
# misread", "a ground-only troop against air is". Those are true of both decks and were only ever
# written against icebow's card names. Picking the card by ROLE instead of by name lets the one
# test assert the same rule in both decks -- and asserts it about a card the deck actually plays.

def _playable(env):
    """Deck-card indices, excluding the champion-ability pseudo-identity."""
    return [i for i in range(len(env.deck_keys)) if i < getattr(env, "n_cards", len(env.deck_keys))]


def a_damage_spell(env) -> int:
    """A plain DAMAGE spell: not a roller, not a pull. icebow -> rocket, hogeq -> earthquake."""
    for i in _playable(env):
        sp = env.specs[i]
        if (sp.kind == "spell" and float(getattr(sp, "spell_dmg", 0.0) or 0.0) > 0.0
                and not getattr(sp, "rolls", False) and not getattr(sp, "pulls", False)):
            return i
    raise unittest.SkipTest("this deck holds no plain damage spell")


def a_ground_only_troop(env) -> int:
    """A TROOP that cannot hit air. icebow -> knight, hogeq -> hog_rider."""
    for i in _playable(env):
        p = env._deck_profiles[i]
        if getattr(p, "kind", None) == "troop" and not getattr(p, "attacks_air", False):
            return i
    raise unittest.SkipTest("this deck holds no ground-only troop")


def a_counter_for(env, threat_id) -> int:
    """A deck card whose profile COUNTERS the given threat identity vector.

    The card that answers an enemy Knight is `knight` in icebow and `mighty_miner` in hogeq; what
    the test means is "a legitimate counter", so ask the counter table rather than naming a card.
    """
    from clashrl import card_threat
    # EXCLUDE THE WIN CONDITION. icebow's original pick was the Knight -- a defensive troop -- and
    # `_threat_response` scores a win-condition card down a different path (`_wincon_exec` owns it),
    # so picking hogeq's Hog Rider here reads 0.0 on the second credit and looks like a budget bug.
    # What the test means by "a counter" is a DEFENDER.
    wincon = set(getattr(env, "wincon_ids", ()) or ())
    for i in _playable(env):
        if i in wincon:
            continue
        if card_threat.counters(env._deck_profiles[i], threat_id):
            return i
    raise unittest.SkipTest("this deck holds no counter for that threat")
