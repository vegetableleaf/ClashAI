"""

Pure functions on the raw state ``RoyalePoolEnv.raw()`` / ``RoyaleSelfPlayEnv.raw()`` produces (``players``,
``entities``, ``episode.crown_towers`` with ``side`` / ``type`` / ``hp`` / ``max_hp`` / ``destroyed``). ``side`` is
the ABSOLUTE engine side (0 = Blue) whose point of view the potential takes; the other side's value is the negation.

    phi_tower(s, side) = (sum own tower hp/max_hp - sum foe tower hp/max_hp) / 3      each tower in [0, 1], dead = 0
    phi_crown(s, side) = (own crowns - foe crowns) / 3
    phi(s, side, w_tower, w_crown) = w_tower * phi_tower + w_crown * phi_crown
    F_t = gamma * Phi(s_{t+1}) - Phi(s_t),   Phi(s_T) = 0 at the terminal index T

Identities (tested): sum_t gamma^t F_t = -Phi(s_0) for any gamma, and the shaping part of the return-to-go from
decision t, sum_{k>=t} gamma^(k-t) F_k, is exactly -Phi(s_t). So the shaping part of a per-decision return depends
only on the state decided in, never on the action taken there (Ng et al. 1999).

Crowns: ``raw()`` carries no crown count. ``crowns`` reads ``state["crowns"]`` ([side 0, side 1]) when the caller
attached the engine's own (the rshape tools do: ``env.core.state().players[s].crowns``), else derives them from the
towers: 3 if the foe king is destroyed, else the destroyed foe princess towers. A tower absent from the list counts
as destroyed (RoyaleSim may drop dead entities; a full list has 1 king + 2 princess per side).
"""
from __future__ import annotations

from typing import Optional, Sequence

N_TOWERS = 3                    # 1 king + 2 princess per side


def _towers(state: dict) -> list[dict]:
    return list((state.get("episode") or {}).get("crown_towers") or [])


def tower_fracs(state: dict, side: int) -> list[float]:
    """HP fraction of each of ``side``'s standing crown towers (max_hp from the state; hp <= 0 or destroyed -> 0)."""
    out = []
    for t in _towers(state):
        if int(t["side"]) != int(side):
            continue
        dead = bool(t.get("destroyed")) or float(t["hp"]) <= 0
        out.append(0.0 if dead else min(1.0, float(t["hp"]) / float(t["max_hp"])))
    if len(out) > N_TOWERS:
        raise ValueError(f"side {side} has {len(out)} crown towers (> {N_TOWERS})")
    return out


def crowns(state: dict) -> tuple[int, int]:
    """(side 0 crowns, side 1 crowns): the attached engine count, else derived from the towers (module docstring)."""
    if state.get("crowns") is not None:
        c = state["crowns"]
        return int(c[0]), int(c[1])
    lost = {0: {"king": 1, "princess": 2}, 1: {"king": 1, "princess": 2}}   # towers of each type NOT standing
    for t in _towers(state):
        if not (bool(t.get("destroyed")) or float(t["hp"]) <= 0):
            lost[int(t["side"])][t["type"]] -= 1
    return tuple(3 if lost[1 - s]["king"] else min(2, lost[1 - s]["princess"]) for s in (0, 1))


def phi_tower(state: dict, side: int) -> float:
    return (sum(tower_fracs(state, side)) - sum(tower_fracs(state, 1 - side))) / N_TOWERS


def phi_crown(state: dict, side: int) -> float:
    c = crowns(state)
    return (c[side] - c[1 - side]) / N_TOWERS


def phi(state: dict, side: int, w_tower: float, w_crown: float) -> float:
    return w_tower * phi_tower(state, side) + w_crown * phi_crown(state, side)


def shaping_terms(states: Sequence[dict], side: int, gamma: float, weights: tuple[float, float],
                  terminal_index: Optional[int] = None) -> dict:
    """Per-decision shaping over one match. ``states`` = the states at decisions 0..n-1 (optionally followed by the
    final state); ``terminal_index`` T (default ``len(states)``) is the terminal state's index: Phi(s_T) = 0 whatever
    the state there holds, and states past T are ignored. Returns F (length T: F_t = gamma * Phi(s_{t+1}) - Phi(s_t))
    and the same per term (``tower``, ``crown``, each already weighted, summing to F), plus ``phi`` (length T+1, the
    last 0)."""
    w_tower, w_crown = float(weights[0]), float(weights[1])
    T = len(states) if terminal_index is None else int(terminal_index)
    if not 0 < T <= len(states):
        raise ValueError(f"terminal_index {T} outside (0, {len(states)}]")
    pt = [w_tower * phi_tower(s, side) for s in states[:T]] + [0.0]
    pc = [w_crown * phi_crown(s, side) for s in states[:T]] + [0.0]
    ft = [gamma * pt[t + 1] - pt[t] for t in range(T)]
    fc = [gamma * pc[t + 1] - pc[t] for t in range(T)]
    return {"F": [a + b for a, b in zip(ft, fc)], "tower": ft, "crown": fc,
            "phi": [a + b for a, b in zip(pt, pc)], "gamma": float(gamma), "weights": (w_tower, w_crown)}


def returns_to_go(rewards: Sequence[float], gamma: float) -> list[float]:
    """G_t = sum_{k>=t} gamma^(k-t) r_k."""
    out, g = [0.0] * len(rewards), 0.0
    for t in range(len(rewards) - 1, -1, -1):
        g = float(rewards[t]) + gamma * g
        out[t] = g
    return out
