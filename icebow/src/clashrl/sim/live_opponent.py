"""The opponent a LIVE search rollout plays against.

Third of the four blockers HANDOFF listed against live search. `opponent_cycle` says WHAT they
hold; this decides what they DO with it. Without it a rollout assumes an idle enemy, and search
happily walks a Giant into a Sparky it never simulated.

DESIGN: WRAP `ScriptedBot`, DO NOT MODIFY IT
--------------------------------------------
Two reasons, and the second is the load-bearing one:

1. ScriptedBot already encodes the doctrine the POLICY WAS TRAINED AGAINST -- defend, punish,
   pump openings, ability use, the split-lane and beatdown styles. A bespoke live opponent would
   be a second thing to keep in sync, and search would be planning against an enemy the policy has
   never met.
2. `opponents.py` is on the SIM TRAINING PATH. Editing it to serve live search would change what
   every future sim run trains against, for the benefit of a live feature. This module touches only
   `bot.cycle` -- a list of spec indices whose first four are the hand -- from the outside.

WHAT IS REAL AND WHAT IS INVENTED
---------------------------------
real       which cards they hold (opponent_cycle, exact once the deck has been observed)
real       their elixir, as estimated by `opponent_elixir`
INVENTED   their STYLE. control / beatdown / cycle / siege is unobservable; we infer it from the
           detected deck and fall back to "control". A beatdown opponent modelled as control will
           be simulated as too reactive.
INVENTED   the unseen half of a partial deck, padded so ScriptedBot has eight cards to cycle.
           Padding is drawn from the deck's own archetype, not at random, but it is still a guess.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from .opponents import ScriptedBot

# Cheap, common filler used only to pad a deck we have not fully observed. These are the cards a
# ladder deck is most likely to be holding that we have not seen yet -- not a claim about THIS
# opponent, just a less-wrong prior than random.
_PAD = ["knight", "archers", "musketeer", "fireball", "zap", "skeletons", "minions", "cannon"]

# Deck signatures -> style. Deliberately small: a wrong style is better than a wrong-and-confident
# taxonomy, and every unmatched deck falls through to "control".
_STYLE_HINTS = (
    ("beatdown", {"golem", "lava_hound", "giant", "electro_giant", "goblin_giant", "pekka"}),
    ("siege", {"x_bow", "mortar"}),
    ("cycle", {"hog_rider", "miner", "wall_breakers", "skeletons", "ice_spirit"}),
)


def infer_style(deck: Sequence[str]) -> str:
    """Best guess at the opponent's archetype from the cards we have seen them play."""
    s = {str(c) for c in deck}
    for style, marks in _STYLE_HINTS:
        if s & marks:
            return style
    return "control"


def pad_deck(db, seen: Sequence[str], size: int = 8) -> List[str]:
    """Fill an incompletely-observed deck out to `size` so ScriptedBot has a queue to cycle."""
    out = list(dict.fromkeys(str(c) for c in seen))
    for c in _PAD:
        if len(out) >= size:
            break
        if c not in out and c in db.cards:
            out.append(c)
    return out[:size]


class LiveOpponent:
    """A ScriptedBot whose hand is kept in step with what we believe the opponent holds."""

    def __init__(self, cfg, db, rng, deck: Sequence[str], style: Optional[str] = None,
                 levels=None):
        self.deck = pad_deck(db, deck)
        self.style = style or infer_style(self.deck)
        self.bot = ScriptedBot(cfg, db, rng, self.deck, self.style, levels=levels)
        self._keys = [getattr(s, "base", None) for s in self.bot.specs]

    # ------------------------------------------------------------------ hand sync
    def sync_hand(self, hand: Sequence[str]) -> int:
        """Reorder the bot's queue so its HAND is the four cards we believe they hold.

        Returns how many of the requested cards were actually placed -- a caller that gets back
        fewer than it asked for is looking at a deck estimate that disagrees with the bot's, and
        should treat the rollout opponent as a guess rather than a model.
        """
        want: List[int] = []
        for key in hand:
            try:
                i = self._keys.index(str(key))
            except ValueError:
                continue
            if i not in want:
                want.append(i)
        if not want:
            return 0
        rest = [i for i in self.bot.cycle if i not in want]
        self.bot.cycle = want + rest
        return len(want)

    def sync(self, opp_cycle, elixir: Optional[float] = None, eng=None) -> int:
        """Sync hand from an `OpponentCycle`, and elixir onto the engine if given."""
        placed = self.sync_hand(opp_cycle.hand())
        if eng is not None and elixir is not None:
            try:
                eng.elixir[1] = float(elixir)
            except Exception:                                  # noqa: BLE001
                pass
        return placed

    # ------------------------------------------------------------------ passthrough
    def act(self, eng) -> None:
        self.bot.act(eng)

    @property
    def hand_keys(self) -> List[str]:
        return [self._keys[i] for i in self.bot.cycle[:4]]
