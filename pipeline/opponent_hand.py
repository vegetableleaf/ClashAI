"""Opponent hand *beliefs* from public card-play events, never hidden state.

Eight distinct deck cards, four held cards, FIFO draw queue (modern standard
rules). ``in_hand``/``out_of_hand`` are logical deductions CONDITIONAL on the
event stream being complete and identifying the played slot correctly. The board
detector cannot guarantee that; its adapter always sets ``certified=False``.
"""
from __future__ import annotations

from collections import Counter
from itertools import groupby

STANDARD_RULES = "standard_8_card_fifo_4_hand"


class HandBelief:
    """Feed normalized, publicly observed deck identities in chronological batches.

    Equal-tick plays are unordered, so they are processed together. Mirror is
    ``mirror``, regardless of the copied unit/spell. Abilities are not plays.
    Card IDs are opaque strings here: normalize forms before calling this API.
    ``complete_events=True`` is a caller-supplied evidence contract, not something
    a board detector can establish by seeing no obvious errors.
    """

    def __init__(self, *, rules=STANDARD_RULES, complete_events=False):
        self.rules = rules
        self.complete_events = bool(complete_events)
        self.reset()

    def reset(self):
        self.revealed = set()
        self.last = {}  # card -> (epoch play count after batch, batch size)
        self.count = 0
        self.tick = None
        self.event_ids = {}
        self.issues = Counter()
        self.invalid_deck = False

    def gap(self, reason="observation_gap"):
        """Forget rotation, preserve only cards actually revealed so far."""
        self.last.clear()
        self.count = 0
        self.issues[reason] += 1

    def observe(self, cards, *, tick, event_ids=None):
        """One unordered batch of actual played identities; None means unknown.

        Stable event IDs deduplicate retransmission. Without them repeated
        identities are not silently deduplicated: impossible rotation invalidates
        prior cycle deductions. A new match requires reset(), never time guessing.
        """
        cards = tuple(cards)
        ids = tuple(event_ids) if event_ids is not None else (None,) * len(cards)
        if len(cards) != len(ids):
            raise ValueError("One event ID per play required")
        tick = int(tick)
        if self.tick is not None and tick < self.tick:
            raise ValueError("Non-monotonic events; reset explicitly for a new match")
        fresh = []
        for card, eid in zip(cards, ids):
            if card is not None and (not isinstance(card, str) or not card):
                raise ValueError("Expected a normalized public card identity or None")
            if eid is not None:
                identity = (tick, card)
                if eid in self.event_ids:
                    if self.event_ids[eid] != identity:
                        raise ValueError("Conflicting duplicate event ID")
                    continue
                self.event_ids[eid] = identity
            fresh.append(card)
        if not fresh:
            return
        if self.tick == tick:
            # The caller split an unordered timestamp across calls: do not invent
            # order or keep stale deductions. Prefer passing one combined batch.
            self.gap("split_same_tick_batch")
        self.tick = tick
        known = [c for c in fresh if c is not None]
        self.revealed.update(known)
        if len(self.revealed) > 8:
            self.invalid_deck = True
            self.gap("more_than_eight_identities")
            return
        if None in fresh or len(set(known)) != len(known):
            self.gap("unknown_or_duplicate_card_in_batch")
            return
        # A card cannot be replayed before four intervening plays. With ties,
        # use the most permissive possible order, not a guessed internal order.
        for card in known:
            if card in self.last:
                end, size = self.last[card]
                max_between = self.count - end + size - 1 + len(known) - 1
                if max_between < 4:
                    self.gap("impossible_early_replay")
                    break
        self.count += len(known)
        for card in known:
            self.last[card] = (self.count, len(known))

    def snapshot(self):
        supported = self.rules == STANDARD_RULES and not self.invalid_deck
        inside, outside, remaining = set(), set(), {}
        if supported:
            for card, (end, size) in self.last.items():
                low, high = self.count - end, self.count - end + size - 1
                remaining[card] = [max(0, 4 - high), max(0, 4 - low)]
                if low >= 4:
                    inside.add(card)
                elif high < 4:
                    outside.add(card)
            # Four identified queued cards determine the complement, but only
            # after ALL deck identities have actually been publicly revealed.
            if len(self.revealed) == 8 and len(outside) == 4:
                inside = self.revealed - outside
                for card in inside:
                    remaining[card] = [0, 0]
        consistent = len(inside) <= 4 and len(outside) <= 4 and not inside & outside
        if not consistent:
            inside, outside, remaining = set(), set(), {}
        full = supported and consistent and len(inside) == 4
        reasons = dict(self.issues)
        if not supported:
            reasons["unsupported_rules_or_deck"] = 1
        if not consistent:
            reasons["inconsistent_hand_size"] = 1
        return dict(
            rules=self.rules, revealed=sorted(self.revealed),
            in_hand=sorted(inside), out_of_hand=sorted(outside),
            uncertain=sorted(self.revealed - inside - outside),
            unrevealed_slots=max(0, 8 - len(self.revealed)),
            plays_to_return=remaining, full_hand=full,
            certified=bool(self.complete_events and supported and consistent and not reasons),
            conditional_on_complete_events=True, issues=reasons,
        )


def from_public_plays(plays, tick, side, *, rules=STANDARD_RULES, complete_events=False):
    """Causal query: exclude current/future events and own-side plays.

    ``card`` must identify the played deck slot. A board copy whose source is
    unknown can set ``identity_unknown=True``; it must not be called Mirror just
    """
    from .dataset_gen import card_key
    selected = [e for e in plays if int(e["side"]) != int(side)
                and int(e["tick"]) < int(tick) and e.get("accepted", True)
                and not e.get("ability", False)]
    selected.sort(key=lambda e: int(e["tick"]))
    tracker = HandBelief(rules=rules, complete_events=complete_events)
    for t, group in groupby(selected, key=lambda e: int(e["tick"])):
        batch = list(group)
        if any(e.get("gap_before") for e in batch):
            tracker.gap()
        tracker.observe([None if e.get("identity_unknown") else card_key(e.get("card", ""))
                         for e in batch], tick=t,
                        event_ids=[e.get("event_id") for e in batch])
    return tracker.snapshot()


class PublicHandObserver:
    """Opt-in companion to PublicObserver; no changes to existing model tensors.

    Uses only regular public board snapshots. Returned beliefs remain untrusted
    because missed/overlapping spells, summons and Mirror can corrupt the detected
    event stream. Inspect replay accuracy before using them for policy learning.
    """
    def __init__(self, side, *, rules=STANDARD_RULES):
        from .public_observation import PublicObserver
        self.observer = PublicObserver(side)
        self.rules = rules

    def update(self, frame, *, source):
        return self.observer.update(frame, source=source)

    def reset(self):
        self.observer.reset()

    def hand_at(self, tick):
        return from_public_plays(self.observer.plays, tick, self.observer.side,
                                 rules=self.rules, complete_events=False)

    def features(self, tick, gid, **kwargs):
        """Existing v4 features, unchanged; hand belief is a separate API."""
        return self.observer.features(tick, gid, **kwargs)
