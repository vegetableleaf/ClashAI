"""Recognized game states for the scripted navigation layer (reused from trol)."""
from enum import Enum, auto


class GameState(Enum):
    UNKNOWN = auto()
    HOME = auto()
    PARTY = auto()
    QUEUING = auto()
    IN_MATCH = auto()
    MATCH_END = auto()
