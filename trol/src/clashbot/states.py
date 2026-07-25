"""Game states the bot recognizes."""
from __future__ import annotations

from enum import Enum, auto


class GameState(Enum):
    UNKNOWN = auto()    # nothing recognized (loading, transitions)
    HOME = auto()       # home page (has the Battle button)
    PARTY = auto()      # 2v2 / party menu (has the quick-match button)
    QUEUING = auto()    # searching for a match (treated like UNKNOWN by logic)
    IN_MATCH = auto()   # actively in a battle
    MATCH_END = auto()  # end-of-battle results overlay
