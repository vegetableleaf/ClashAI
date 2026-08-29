"""What is in the OPPONENT'S hand right now -- inferred from the cards they have played.

HANDOFF listed "there is no opponent deck/hand model" as one of the four reasons live search was
ruled out. Rollouts need someone to play against: a searcher that assumes the enemy does nothing
will happily walk a Giant into a Sparky it cannot see coming.

THE KEY FACT, and it is the same one `cycle.py` uses for our own side: Clash Royale's queue is
DETERMINISTIC. Eight cards; the front four are the hand; playing one sends it to the BACK and
slides everything forward. So the play ORDER *is* the queue order -- we do not have to guess a
distribution, we can reconstruct it.

    after every card has been seen once, queue front->back = the 8 plays in chronological order
    => HAND = the four cards played LONGEST AGO
    => NEXT = the fifth

Before all eight are known the estimate is partial, and the partial knowledge is still worth
having, because it is one-sided in a useful way: a card played in the last three plays is
CERTAINLY NOT in hand, whatever else we do not know.

/!\\ WHAT BREAKS IT
  * A MISSED PLAY desyncs the hand TEMPORARILY -- measured, not assumed. `hand()` keys on each
    card's MOST RECENT play, so one dropped observation makes exactly one card look staler than it
    is, and the error clears the next time that card is played and seen. I first wrote this as
    "every later hand is wrong"; the test disproved it.
    /!\ That is not robustness. Between the miss and the next sighting the hand IS wrong,
    `confidence()` still reads 1.0, and nothing flags it. Consume it as an estimate.
  * Spells are the likeliest misses (small, fast, no lingering body).
  * Mirror and any card that changes the queue would break the assumption. Neither is modelled.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

DECK_SIZE = 8
HAND_SIZE = 4


class OpponentCycle:
    """Track the opponent's queue from their observed plays.

    Deliberately keyed on CARD KEYS (strings) rather than ids: live gets its identities from the
    detector's class names, and the deck is not known up-front the way the sim's is.
    """

    def __init__(self, deck: Optional[Sequence[str]] = None):
        self.deck: List[str] = list(dict.fromkeys(deck or []))[:DECK_SIZE]
        self.plays: List[str] = []          # chronological, most recent LAST

    # ------------------------------------------------------------------ observation
    def record_play(self, card: str) -> None:
        """Note that the opponent just played `card`. Unknown cards join the deck as they appear."""
        if not card:
            return
        card = str(card)
        if card not in self.deck and len(self.deck) < DECK_SIZE:
            self.deck.append(card)
        if card in self.deck:
            self.plays.append(card)

    def reset(self) -> None:
        self.plays.clear()

    # ------------------------------------------------------------------ inference
    def known_deck(self) -> List[str]:
        return list(self.deck)

    def confidence(self) -> float:
        """0..1 -- how much of the deck we have actually seen. NOT a probability the hand is right;
        a single missed play makes a fully-observed deck's hand wrong while this still reads 1.0."""
        return len(self.deck) / float(DECK_SIZE)

    def definitely_not_in_hand(self) -> List[str]:
        """The cards most recently played. This is the ROBUST half of the inference: whatever else
        is uncertain, a card sent to the back of the queue is not back in hand yet."""
        recent = []
        for c in reversed(self.plays):
            if c not in recent:
                recent.append(c)
            if len(recent) >= DECK_SIZE - HAND_SIZE:
                break
        return recent

    def hand(self) -> List[str]:
        """Best estimate of the four cards currently in the opponent's hand.

        Cards that were played longest ago have had the most time to cycle forward, so they sit
        nearest the front. Deck members never seen played are treated as never-cycled, i.e. still
        near the front -- which is right: at match start nothing has been played and the hand is
        drawn from the un-played eight.
        """
        if not self.deck:
            return []
        last_played: Dict[str, int] = {}
        for i, c in enumerate(self.plays):
            last_played[c] = i
        # never played -> -1, so it sorts ahead of everything that has been
        order = sorted(self.deck, key=lambda c: last_played.get(c, -1))
        return order[:HAND_SIZE]

    def next_card(self) -> Optional[str]:
        if not self.deck:
            return None
        last_played: Dict[str, int] = {}
        for i, c in enumerate(self.plays):
            last_played[c] = i
        order = sorted(self.deck, key=lambda c: last_played.get(c, -1))
        return order[HAND_SIZE] if len(order) > HAND_SIZE else None

    def could_play(self, elixir: float, costs: Dict[str, float]) -> List[str]:
        """Which of the estimated hand they can currently afford -- what a rollout actually needs."""
        return [c for c in self.hand() if costs.get(c, 99.0) <= elixir + 1e-6]
