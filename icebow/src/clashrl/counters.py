"""The COUNTER TABLE: what this deck plays against what, when, and where.

WHY A TABLE AND NOT A PROMPT (user, 2026-08-20: "the advisor is suggesting unrealistic counters,
like placing knight on a balloon... or rocketing wall breakers"). Three tiers already sat above
this one and none of them could say what to PLAY:

  * ``threat_value``  -- is this worth a card at all (triage; the tier above every counter).
  * ``threat_value.pick_invalid`` -- CAN this card touch that threat, and is the trade sane
    (the hard KB veto; it rejects a wrong answer but never proposes a right one).
  * ``card_threat.counters`` -- role-based matching (air-defence vs air, splash vs swarm), which
    is right in shape but blind to specifics: it cannot know that Wall Breakers want Skeletons
    placed so the tower helps, or that a Balloon wants a Tornado into an activated King.

This module is the specifics, researched from counter guides and then adversarially audited
against the card database. Every row is (threat -> ordered responses), each response carrying
WHEN it goes down and WHERE, because in this game a right card at the wrong moment is a lost
tower: a building placed ``last_moment`` cannot pull a Hog that has already locked on.

The table is DATA (``config/counters.yaml``), not code, so it can be corrected without touching
the pipeline -- and it is consumed identically by the sim's doctrine prior and the live advisor
path, so both sides answer a push the same way.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

# Placement vocabulary. These are the only legal `where` values; each maps to a geometry the
# live wheels and the sim's cell prior already know how to produce.
WHERE_VALUES = frozenset({
    "on_top",            # directly onto the threat (skeletons on a sparky)
    "in_front",          # between the threat and our tower -- the body-block
    "behind_threat",     # deeper than it, so it walks past and gets shot in the back
    "center_kite",       # centre of our half: drags the push where BOTH towers reach it
    "at_tower",          # tight to our own tower (tower assists the defence -- wall breakers)
    "opposite_lane",     # pull/answer in the other lane entirely
    "king_activation",   # into our own king's range, to wake it
    "surround",          # ring the threat (swarm placement)
})

# Timing vocabulary, in ascending "how late" order -- used to sort competing responses.
WHEN_VALUES = ("pre_place", "on_place", "at_bridge", "in_our_half", "last_moment")


class CounterTable:
    """Threat -> ordered responses, with combos taking precedence over single cards."""

    def __init__(self, rows: Optional[List[dict]] = None):
        self.rows: List[dict] = []
        self._by_key: Dict[frozenset, dict] = {}
        for r in (rows or []):
            self.add(r)

    def add(self, row: dict) -> None:
        cards = [str(c) for c in (row.get("threat_cards") or []) if c]
        if not cards or not (row.get("respond") or []):
            return
        key = frozenset(cards)
        # A more specific row (more threat cards) or a first sighting wins; identical keys keep
        # the first, so a hand-written override placed earlier in the file survives a regenerate.
        if key not in self._by_key:
            self._by_key[key] = row
            self.rows.append(row)

    def lookup(self, threat_bases) -> Optional[dict]:
        """Best row for the threat group on the board.

        Exact combo first (a Lavaloon is not a Lava Hound plus a Balloon -- the answer is "ignore
        the hound, kill the balloon", which neither single row says), then the largest matching
        subset, then any single card present. Returns None when the table has nothing, which the
        callers read as "no doctrine opinion", never as "do nothing".
        """
        bases = {str(b) for b in (threat_bases or ()) if b}
        if not bases:
            return None
        exact = self._by_key.get(frozenset(bases))
        if exact is not None:
            return exact
        best, best_n = None, 0
        for key, row in self._by_key.items():
            if key <= bases and len(key) > best_n:
                best, best_n = row, len(key)
        return best

    def responses(self, threat_bases, hand_bases=()) -> List[dict]:
        """Doctrine responses for this threat, filtered to what is actually in hand (when a hand
        is given) and kept in the table's priority order."""
        row = self.lookup(threat_bases)
        if row is None:
            return []
        out = list(row.get("respond") or [])
        if hand_bases:
            hand = {str(c) for c in hand_bases}
            out = [r for r in out if str(r.get("card")) in hand]
        return out

    def best_card(self, threat_bases, hand_bases=()) -> Optional[str]:
        got = self.responses(threat_bases, hand_bases)
        return str(got[0]["card"]) if got else None

    def __len__(self) -> int:
        return len(self.rows)


def load(cfg=None, path: Optional[str] = None) -> CounterTable:
    """Read config/counters.yaml. A missing file is not an error -- it means this deck has no
    researched table yet and every consumer falls back to the behaviour it had before."""
    import yaml
    p = path
    if p is None:
        if cfg is not None:
            p = str(cfg.path(cfg.get("train", "counter_table", default="config/counters.yaml")))
        else:
            p = "config/counters.yaml"
    if not os.path.exists(p):
        return CounterTable([])
    with open(p, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return CounterTable(list(data.get("counters") or []))
