"""E1 option B: the observation the LIVE student is fed, simulated from an engine ``BoardState``.

    live_view(bs, rng, deck) = obs_contract.degrade(bs, rng)  (all defaults)
                               + the three live rules degrade() does not apply:
      1. every unit (and spell) token carries hp_frac 1.0 (hp_known 1) -- live sends
         ``from_live(..., unit_hp_default=1.0)`` (icebow/src/clashrl/student_live.py:62,141-142);
      2. an ALIVE king tower carries hp_frac 1.0 -- live ``live_reads(fill_king_hp=True)`` (student_live.py:486-490);
         a destroyed king keeps degrade's 0.0 / alive False, as ``from_live`` writes it (obs_contract.py:468-470);
      3. a token with side -1 whose class my deck cannot produce (``obs_contract.mine_classes``) is resolved to
         ENEMY (side 1) -- ``from_live`` (obs_contract.py:459-461).
    ``opp_elixir`` stays None (live default ``play.student_opp_elixir: false``); ``source`` stays ``"degraded"`` so a
    caller can count degraded observations. Design: scratchpad/gauntlet/L67/e1_engine_rl_design.md section 3.1.

Everything random comes from ``rng`` (a ``numpy.random.Generator``), consumed ONLY by degrade(); the three rules
are deterministic, so the same seed on the same board gives identical tokens.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from . import vocab
from .obs_contract import BoardState, Deck, Unit, degrade, mine_classes

KING_HP_LIVE = 1.0          # student_live.live_reads fill_king_hp -> 1.0
UNIT_HP_LIVE = 1.0          # student_live.StudentPolicy fill_missing -> unit_hp_default 1.0


def _live_unit(u: Unit, allowed: frozenset) -> Unit:
    side = u.side
    if side < 0 and vocab.base_key(vocab.UNIT_VOCAB[int(u.cls)]) not in allowed:
        side = 1
    return replace(u, hp_frac=UNIT_HP_LIVE, side=side)


def live_view(bs: BoardState, rng: np.random.Generator, deck: Deck) -> BoardState:
    """``degrade(bs, rng)`` with its defaults, then the live fill rules (module docstring)."""
    d = degrade(bs, rng)
    allowed = mine_classes(deck)
    units = tuple(_live_unit(u, allowed) for u in d.units)
    spells = tuple(_live_unit(u, allowed) for u in d.spells)
    towers = tuple(replace(t, hp_frac=KING_HP_LIVE) if (t.kind == "king" and t.alive) else t for t in d.towers)
    return replace(d, units=units, spells=spells, towers=towers)
