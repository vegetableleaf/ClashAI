"""Which side of a frame is ours."""
from __future__ import annotations

from typing import Any, Mapping


def my_side_of(frame: Mapping[str, Any]) -> int:
    """The side whose hand is visible (the other side's hand reads -1s)."""
    vis = [int(p["side"]) for p in frame["players"] if any(i >= 0 for i in p["hand_deck_indices"])]
    if len(vis) != 1:
        raise ValueError(f"expected exactly one side with a visible hand, got {vis}")
    return vis[0]
