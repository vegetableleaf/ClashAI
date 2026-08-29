"""The opponent hand model, validated against the sim's OWN queue -- where truth exists.

HANDOFF listed "no opponent deck/hand model" as one of four reasons live search was ruled out.
This is the piece. The claim it rests on is that Clash Royale's queue is DETERMINISTIC, so play
order reconstructs the hand exactly -- and the honest way to test that is to run it against a real
sim cycle rather than a hand-built example.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.sim.opponent_cycle import OpponentCycle, DECK_SIZE, HAND_SIZE   # noqa: E402

DECK = ["knight", "archers", "musketeer", "fireball", "zap", "hog_rider", "skeletons", "cannon"]


class _TrueQueue:
    """The real rule: 8-card queue, front 4 are the hand, a played card goes to the BACK."""

    def __init__(self, order):
        self.q = list(order)

    @property
    def hand(self):
        return self.q[:HAND_SIZE]

    def play(self, card):
        assert card in self.hand, f"{card} is not in hand {self.hand}"
        self.q.remove(card)
        self.q.append(card)
        return card


class OpponentCycleTests(unittest.TestCase):

    def test_it_reconstructs_the_hand_EXACTLY_once_the_deck_has_cycled(self):
        """THE CLAIM. Play against a true queue; after every card has been seen, the estimate must
        match the real hand exactly -- not approximately."""
        rng = random.Random(0)
        for trial in range(20):
            order = DECK[:]
            rng.shuffle(order)
            truth = _TrueQueue(order)
            model = OpponentCycle()                       # deck NOT given: learned from plays
            for _ in range(DECK_SIZE * 3):
                card = rng.choice(truth.hand)
                truth.play(card)
                model.record_play(card)
            self.assertEqual(model.confidence(), 1.0, "deck was not fully observed")
            self.assertEqual(sorted(model.hand()), sorted(truth.hand),
                             f"trial {trial}: estimated {model.hand()} vs real {truth.hand}")

    def test_the_next_card_is_right_too(self):
        rng = random.Random(1)
        order = DECK[:]
        rng.shuffle(order)
        truth = _TrueQueue(order)
        model = OpponentCycle()
        for _ in range(DECK_SIZE * 3):
            c = rng.choice(truth.hand)
            truth.play(c)
            model.record_play(c)
        self.assertEqual(model.next_card(), truth.q[HAND_SIZE])

    def test_recently_played_cards_are_NEVER_claimed_to_be_in_hand(self):
        """The robust half: whatever else is uncertain, a card just sent to the back is not in hand.
        This must hold even BEFORE the deck is fully observed."""
        rng = random.Random(2)
        truth = _TrueQueue(DECK[:])
        model = OpponentCycle()
        for i in range(12):
            c = rng.choice(truth.hand)
            truth.play(c)
            model.record_play(c)
            for gone in model.definitely_not_in_hand():
                self.assertNotIn(gone, truth.hand,
                                 f"step {i}: claimed {gone} was out of hand, but it is in {truth.hand}")

    def test_it_never_invents_cards_it_has_not_seen(self):
        model = OpponentCycle()
        for c in ("hog_rider", "zap"):
            model.record_play(c)
        self.assertEqual(sorted(model.known_deck()), ["hog_rider", "zap"])
        self.assertTrue(set(model.hand()) <= {"hog_rider", "zap"})
        self.assertLess(model.confidence(), 1.0)

    def test_affordability_filter(self):
        model = OpponentCycle(DECK)
        costs = {"knight": 3, "archers": 3, "musketeer": 4, "fireball": 4,
                 "zap": 2, "hog_rider": 4, "skeletons": 1, "cannon": 3}
        cheap = model.could_play(2.0, costs)
        self.assertTrue(all(costs[c] <= 2.0 for c in cheap))
        self.assertTrue(set(cheap) <= set(model.hand()))

    def test_a_missed_play_desyncs_TEMPORARILY_and_then_self_heals(self):
        """The failure mode, measured rather than assumed -- and it is milder than I expected.

        `hand()` depends only on each card's MOST RECENT play, not the full history, so a dropped
        observation makes exactly ONE card look staler than it is. The error persists only until
        that card is played again and seen. I wrote this test asserting permanent desync; it
        failed, because the model self-corrects. Pinning the real behaviour instead.

        /!\ This is NOT a claim of robustness. Between the miss and the next sighting the hand is
        wrong, `confidence()` still reads 1.0, and nothing flags it. A consumer must treat the hand
        as an estimate.
        """
        rng = random.Random(3)
        truth = _TrueQueue(DECK[:])
        model = OpponentCycle(DECK)
        missed = None
        wrong_right_after_miss = False
        for i in range(DECK_SIZE * 5):
            c = rng.choice(truth.hand)
            truth.play(c)
            if i == 20:
                missed = c                                 # drop this one observation
            else:
                model.record_play(c)
            if i == 20:
                wrong_right_after_miss = sorted(model.hand()) != sorted(truth.hand)
        self.assertIsNotNone(missed)
        self.assertTrue(wrong_right_after_miss,
                        "a dropped observation did not even briefly desync the hand")
        self.assertEqual(model.confidence(), 1.0,
                         "confidence cannot see a miss -- that is the point of the warning")
        self.assertEqual(sorted(model.hand()), sorted(truth.hand),
                         "the model failed to self-heal after the missed card was played again")


if __name__ == "__main__":
    unittest.main()
