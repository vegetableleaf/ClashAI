"""Headless sim training environment. See engine.py + icebow/DECK_SWITCH.md."""
from __future__ import annotations

from .engine import SimEngine, build_spec
from .env import SimMatchEnv
from .meta_decks import classify_style, load_meta_decks
from .opponents import ScriptedBot, make_opponent

__all__ = ["SimEngine", "build_spec", "SimMatchEnv", "ScriptedBot", "make_opponent",
           "load_meta_decks", "classify_style"]
