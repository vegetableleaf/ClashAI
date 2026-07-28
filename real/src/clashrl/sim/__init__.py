"""Headless sim training environment. See engine.py + real/DECK_SWITCH.md."""
from __future__ import annotations

from .engine import SimEngine, build_spec
from .env import SimMatchEnv
from .opponents import ScriptedBot, make_opponent

__all__ = ["SimEngine", "build_spec", "SimMatchEnv", "ScriptedBot", "make_opponent"]
