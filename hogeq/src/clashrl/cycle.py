"""Deterministic 4-card cycle tracker + a graded 'upcoming order' obs encoding.

Clash Royale draws from an 8-card queue: the front 4 are your HAND, the 5th is the
``Next`` preview, and the 3 behind it are HIDDEN. Playing a card sends it to the BACK
of the queue and slides everything forward, so the order is fully DETERMINISTIC once
observed -- and, crucially, YOU influence it (which hand card you play decides what
reaches the back). This module reconstructs the queue live (from hand/next recognition
plus the plays the bot makes) and encodes each deck card's ``soonness`` -- how many
plays until it reaches the hand -- into a length-``n_cards`` vector, so the policy can
PLAN which cards to cycle toward when the counter it needs isn't in hand yet.

The sim already holds the TRUE ordered queue (``SimMatchEnv.cycle``); it calls
:func:`cycle_vector` directly. Live uses :class:`CycleTracker` to estimate the queue,
then the same :func:`cycle_vector`, so the observation is identical on both sides. The
encoding is a strict SUPERSET of the old ``next`` one-hot (the Next card is the single
entry at value ``1.0``), so the policy network is unchanged -- only the semantics are
richer, which is why a from-scratch retrain picks the new signal up.
"""
from __future__ import annotations

import numpy as np

# next card grades to 1.0; each card deeper in the undrawn queue loses this much 'soonness'
# per step, floored so the deepest card still reads as "coming" rather than absent.
_DEPTH_DECAY = 0.75


def cycle_vector(queue, n_cards: int) -> np.ndarray:
    """Encode a queue's UPCOMING order as a length-``n_cards`` graded 'soonness' vector.

    ``queue`` is the ordered deck ids front(hand)->back; positions ``[0:4]`` are the hand,
    ``[4]`` is Next, ``[5:]`` are the hidden upcoming cards. Unknown entries may be ``-1``.
    The returned vector marks Next at ``1.0`` and grades later cards down toward a small
    floor; cards in hand (already available) and unknown slots stay ``0``. This is a strict
    superset of the old next one-hot -- ``argmax`` still recovers the Next card.
    """
    v = np.zeros(max(1, int(n_cards)), np.float32)
    if not queue:
        return v
    undrawn = list(queue)[4:]                 # Next + the hidden upcoming cards, front->back
    span = max(1, len(undrawn) - 1)           # so the deepest upcoming card lands on the floor
    for depth, cid in enumerate(undrawn):
        if 0 <= cid < n_cards:
            soon = 1.0 - _DEPTH_DECAY * (depth / span)   # Next=1.0 ... deepest~1-_DEPTH_DECAY
            if soon > v[cid]:
                v[cid] = soon
    return v


class CycleTracker:
    """Live estimate of the 8-card queue order from hand/next recognition + the bot's plays.

    The hand SET (4) and the Next card (1) are read every frame; the 3 cards behind Next are
    hidden, but their IDENTITIES are always known (they are exactly ``deck - hand - {next}``).
    Their ORDER is inferred from play RECENCY: the card you most recently played sits at the
    very back of the queue (farthest away), the one before it next, and so on -- which is
    exactly how the real queue rotates. Cards not seen played recently are assumed shallow
    (just behind Next). This is robust to missed frames: it never needs perfect play
    detection, only the running set of recent plays plus the current hand/next read.

    Usage per match: :meth:`reset` at the start, :meth:`record_play` right after the bot taps
    a card, and :meth:`observe` each decision tick (returns the graded cycle vector).
    """

    def __init__(self, n_cards: int):
        self.n = int(n_cards)
        self.reset()

    def reset(self) -> None:
        self._queue: list[int] = []           # best current estimate, front(hand)->back
        self._play_seq: list[int] = []         # ids in the order played (most recent last)

    def record_play(self, card_id: int) -> None:
        """Note that ``card_id`` was just played -> it rotates to the BACK of the queue."""
        if 0 <= card_id < self.n:
            self._play_seq.append(int(card_id))
            if len(self._play_seq) > 4 * self.n:
                self._play_seq = self._play_seq[-4 * self.n:]   # bound the history

    def observe(self, hand_ids, next_id: int) -> np.ndarray:
        """Reconcile with the current hand SET + Next read; return the graded cycle vector.

        ``hand_ids`` = the recognised hand deck ids (order irrelevant; -1 = unrecognised);
        ``next_id`` = the Next preview deck id (-1 if unknown). Rebuilds the queue estimate
        as ``hand + [next] + hidden`` with the hidden 3 ordered by play recency.
        """
        hand = [c for c in hand_ids if 0 <= c < self.n]
        if len(set(hand)) < 4:
            return self.cycle_vec()            # partial/again-mid-animation frame -> keep last estimate
        hset = set(hand)
        nxt = next_id if (0 <= next_id < self.n and next_id not in hset) else -1
        drawn = set(hset)
        if nxt >= 0:
            drawn.add(nxt)
        hidden = [c for c in range(self.n) if c not in drawn]   # identities of the cards behind Next
        # ORDER the hidden cards by how recently each was played: most-recent = deepest (last).
        def _recency(cid: int) -> int:
            for i in range(len(self._play_seq) - 1, -1, -1):
                if self._play_seq[i] == cid:
                    return i
            return -1                          # never seen played -> shallow (just behind Next)
        hidden.sort(key=_recency)              # ascending recency -> shallow first, deepest last
        self._queue = list(hand) + ([nxt] if nxt >= 0 else []) + hidden
        return self.cycle_vec()

    def cycle_vec(self) -> np.ndarray:
        """The graded 'soonness' vector for the current queue estimate (see :func:`cycle_vector`)."""
        return cycle_vector(self._queue, self.n)
