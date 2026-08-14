"""Helpers for shaping X-Bow and rocket win-condition rewards.

These helpers are shared by live and simulator envs so reward behavior stays
consistent and import paths remain stable.
"""

from __future__ import annotations


def xbow_reward(
    *,
    in_range: bool,
    central: bool,
    in_band: bool,
    behind: bool,
    defensive: bool,
    punish_window: bool,
    base_reward: float,
    punish_mult: float,
    deep_frac: float,
    sensible_frac: float,
    miss_penalty: float,
) -> float:
    """Return a shaped reward for X-Bow placements."""
    if punish_window:
        return base_reward * punish_mult

    if defensive:
        if in_band:
            return base_reward
        if behind:
            return base_reward * deep_frac
        if central:
            return base_reward * sensible_frac
        return miss_penalty

    if in_range:
        return base_reward
    if behind:
        return base_reward * deep_frac
    if central:
        return base_reward * sensible_frac
    return miss_penalty


def rocket_reward(
    *,
    aimed_at_tower: bool,
    combo: bool,
    pump: bool,
    defensive: bool,
    base_reward: float,
    combo_mult: float,
    tower_frac: float,
    defensive_frac: float,
    miss_penalty: float,
) -> float:
    """Return a shaped reward for rocket placements."""
    if combo:
        return base_reward * combo_mult
    if pump:
        return base_reward
    if aimed_at_tower:
        return base_reward * defensive_frac if defensive else base_reward * tower_frac
    return miss_penalty
