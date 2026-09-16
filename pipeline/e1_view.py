"""

    live_view(bs, rng, deck) = obs_contract.degrade(bs, rng)  (all defaults)
         a destroyed king keeps degrade's 0.0 / alive False, as ``from_live`` writes it (obs_contract.py:468-470);
      3. a token with side -1 whose class my deck cannot produce (``obs_contract.mine_classes``) is resolved to
         ENEMY (side 1) -- ``from_live`` (obs_contract.py:459-461).

Everything random comes from ``rng`` (a ``numpy.random.Generator``), consumed ONLY by degrade(); the three rules
are deterministic, so the same seed on the same board gives identical tokens.

a per-component on/off switch over the same noise this module applies -- degrade()'s recall / false positives /
+ elixir/opp-elixir, the side -1 -> enemy resolution never needs a switch of its own, see below). Every field
defaults True = today's live_view. See ``_degrade_switchable`` for the RNG discipline that keeps every arm's
random draws identical regardless of which switches are off (needed for a paired comparison across arms).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

import numpy as np

from . import vocab
from .obs_contract import (
    DEGRADE_PRECISION, DEGRADE_RECALL, TILES_X, TILES_Y, UNKNOWN_TEAM_RATE, WRONG_TEAM_RATE,
    BoardState, Deck, Unit, _draw_conf, _FP_JITTER_TILES, _TP_SIGMA_TILES, mine_classes,
)

KING_HP_LIVE = 1.0
UNIT_HP_LIVE = 1.0


# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Noise:
    """

    ``recall``    False -> no unit/spell is dropped (recall treated as 1.0).
    ``false_pos`` False -> no false-positive units are added (precision treated as 1.0).
    ``position``  False -> no Gaussian position noise, and a false positive sits exactly on its source
                  unit (no jitter offset either) -- both are the same ``dx, dy`` draw in degrade().
    ``team``      False -> no side -> unknown(-1) and no wrong-team flip; a unit keeps its true engine side.
    ``unit_hp``   False -> units/spells keep their true engine ``hp_frac`` (``hp_known`` 1 in the tokens)
                  instead of degrade() dropping it and live_view re-filling it to 1.0.
    ``my_elixir``  False -> exact (unfloored) my_elixir and ``my_elixir_exact`` unchanged, instead of
                  degrade()'s floor + ``my_elixir_exact=False``. (O5 split of the old ``scalars`` switch.)
    ``opp_elixir`` False -> the true opp_elixir (known) instead of degrade()'s None. (O5 split of ``scalars``.)
    ``king_hp``    False -> the true king hp_frac throughout, instead of degrade() dropping it to None and
                  live_view re-filling it to 1.0. (O5 split of ``scalars``.)
    ``deploying`` False -> keep whatever ``deploying`` the BoardState already carries, instead of dropping
                  it to None. NOTE: e1_eval's engine rows go through ``policy_io.compact_raw``, which
                  strips ``kind`` from every entity before ``from_engine`` -- so ``deploying`` is already
                  None on the input BoardState there and this switch is a documented no-op for E1 (both
                  settings degrade to the same None). It is real for any other BoardState source.
    ``conf``      False -> detection confidence stays the input's true value (1.0 for engine truth, as in
                  ``--obs clean``) instead of a redrawn detector-shaped value.
    """
    recall: bool = True
    false_pos: bool = True
    position: bool = True
    team: bool = True
    unit_hp: bool = True
    my_elixir: bool = True
    opp_elixir: bool = True
    king_hp: bool = True
    deploying: bool = True
    conf: bool = True


ALL_NOISE_OFF = Noise(recall=False, false_pos=False, position=False, team=False, unit_hp=False,
                      my_elixir=False, opp_elixir=False, king_hp=False, deploying=False, conf=False)


# ------------------------------------------------------------------------------------------------------
# a component-switchable copy of obs_contract.degrade -- READ-ONLY on obs_contract.py itself
# ------------------------------------------------------------------------------------------------------
def _degrade_switchable(bs: BoardState, rng: np.random.Generator, noise: Noise) -> BoardState:
    """``obs_contract.degrade(bs, rng)`` with each noise component individually switchable.

    Pinned to ``degrade()`` by test_e1_noise_arms: with every ``Noise`` field True this must be
    bit-identical to ``degrade(bs, rng)`` for the same seed (same BoardState, same RNG state in).

    RNG discipline (so turning one component off never re-randomises the others, which would defeat a
    paired before/after comparison): every draw ``degrade()`` would make for a KEPT unit or spell --
    position dx/dy, the team roll, the conf redraw -- is made HERE TOO, in the same order, unconditionally;
    only whether the drawn value is APPLIED to the unit depends on ``noise``. False positives are decided
    with the real (fixed) precision every time, and false_pos only decides whether the resulting unit is
    appended -- so the draws it costs (kind index + its own dx/dy/team/conf) happen exactly when degrade()
    would have spent them, on or off.

    ``recall`` OFF is the one component that changes what a unit's noise LOOKS like, not just whether it is
    applied: a unit/spell degrade()'s (always-drawn) recall roll would have dropped is RESCUED -- kept in the
    output -- but it must be noised exactly like a normally-kept unit under the same switches (owner review:
    appending it clean would silently hand the recall arm perfect information on the ~14.5% of units that
    would otherwise be dropped, overstating what fixing recall alone buys). That noise cannot come from the
    main ``rng``, or it would consume draws ``degrade()``/the ON arm never spends there and desync every
    later unit's stream from the default path (breaking the "same draws, same order" guarantee above) --
    so rescued units draw from ``side_rng``, an INDEPENDENT stream split off of ``rng`` before any draw is
    made (``Generator(rng.bit_generator.jumped())``; ``jumped()`` returns a new bit generator and never
    advances the original -- see test_side_rng_creation_does_not_advance_main_rng). Degrade() never spawns a
    false positive from a dropped unit, so a rescued unit never does either.
    """
    fp_rate = (1.0 - DEGRADE_PRECISION) / DEGRADE_PRECISION
    kinds: dict[str, list[int]] = {"troop": [], "building": [], "spell": []}
    for i in range(vocab.N_DETECTOR):
        kinds[vocab.kind_of(i)].append(i)
    side_rng = np.random.Generator(rng.bit_generator.jumped())   # rescued-unit noise only; see docstring

    def rolled(u: Unit, cls: Optional[int], jitter: float, gen: Optional[np.random.Generator] = None) -> Unit:
        """The fully-noised unit degrade()'s ``noisy()`` would build -- draws dx/dy, the team roll and a
        fresh conf UNCONDITIONALLY from ``gen`` (default: the main ``rng``); ``noise`` only picks which of
        those the returned Unit carries."""
        g = rng if gen is None else gen
        dx = g.normal(0.0, jitter) / TILES_X if jitter > 0 else 0.0
        dy = g.normal(0.0, jitter) / TILES_Y if jitter > 0 else 0.0
        r = g.random()
        wrong = WRONG_TEAM_RATE.get(vocab.kind_of(u.cls), 0.0)
        if UNKNOWN_TEAM_RATE and r < UNKNOWN_TEAM_RATE:
            rolled_side = -1
        elif wrong and r < (UNKNOWN_TEAM_RATE or 0.0) + wrong and u.side in (0, 1):
            rolled_side = 1 - u.side
        else:
            rolled_side = u.side
        conf = _draw_conf(g)
        side = rolled_side if noise.team else u.side
        x = float(np.clip(u.x + (dx if noise.position else 0.0), 0.0, 1.0))
        y = float(np.clip(u.y + (dy if noise.position else 0.0), 0.0, 1.0))
        hp = None if noise.unit_hp else u.hp_frac
        dep = None if noise.deploying else u.deploying
        return Unit(u.cls if cls is None else cls, side, x, y, hp, dep, None, conf if noise.conf else u.conf)

    def pass_(seq: Sequence[Unit], *, with_fp: bool) -> list[Unit]:
        out: list[Unit] = []
        for u in seq:
            kept = rng.random() < DEGRADE_RECALL                     # always drawn -- degrade()'s own roll
            if not kept:
                if not noise.recall:                                  # rescued: noised on the SIDE stream,
                    out.append(rolled(u, None, _TP_SIGMA_TILES, gen=side_rng))  # never an FP source
                continue                                              # recall ON: matches degrade() exactly
            out.append(rolled(u, None, _TP_SIGMA_TILES))
            if with_fp:
                add = rng.random() < fp_rate                          # always drawn for a kept unit
                if add:                                                # draws below ALWAYS spent when add
                    pool = kinds[vocab.kind_of(u.cls)]
                    fp_cls = int(pool[rng.integers(len(pool))])
                    fp_unit = rolled(u, fp_cls, max(_TP_SIGMA_TILES, _FP_JITTER_TILES))
                    if noise.false_pos:                                # false_pos only gates the append
                        out.append(fp_unit)
        return out

    units = pass_(bs.units, with_fp=True)
    spells = pass_(bs.spells, with_fp=False)
    towers = tuple((replace(t, hp_frac=None) if noise.king_hp else t) if (t.kind == "king" and t.alive) else t
                   for t in bs.towers)
    return replace(bs, source="degraded", t_source="clock",
                   my_elixir=float(int(bs.my_elixir)) if noise.my_elixir else bs.my_elixir,
                   my_elixir_exact=bs.my_elixir_exact and not noise.my_elixir,
                   opp_elixir=bs.opp_elixir if not noise.opp_elixir else None,
                   towers=towers, units=tuple(units), spells=tuple(spells))


def _live_unit(u: Unit, allowed: frozenset, noise: Noise) -> Unit:
    side = u.side
    if side < 0 and vocab.base_key(vocab.UNIT_VOCAB[int(u.cls)]) not in allowed:
        side = 1                          # unconditional: only fires on side -1, which noise.team=False never makes
    hp = UNIT_HP_LIVE if noise.unit_hp else u.hp_frac
    return replace(u, hp_frac=hp, side=side)


def live_view(bs: BoardState, rng: np.random.Generator, deck: Deck, noise: Optional[Noise] = None) -> BoardState:
    """
    ``noise`` switches some of that off (default ``None`` = ``Noise()`` = every switch on = unchanged)."""
    noise = noise or Noise()
    d = _degrade_switchable(bs, rng, noise)
    allowed = mine_classes(deck)
    units = tuple(_live_unit(u, allowed, noise) for u in d.units)
    spells = tuple(_live_unit(u, allowed, noise) for u in d.spells)
    towers = tuple(replace(t, hp_frac=KING_HP_LIVE) if (noise.king_hp and t.kind == "king" and t.alive) else t
                   for t in d.towers)
    return replace(d, units=units, spells=spells, towers=towers)
