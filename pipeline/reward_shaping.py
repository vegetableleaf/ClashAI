"""Potential-based reward shaping for the icebow RL learner (L69 plan R2, scratchpad/gauntlet/L69/reward_plan.md).

Pure functions on the raw state ``RoyalePoolEnv.raw()`` / ``RoyaleSelfPlayEnv.raw()`` produces (``players``,
``entities``, ``episode.crown_towers`` with ``side`` / ``type`` / ``hp`` / ``max_hp`` / ``destroyed``). ``side`` is
the ABSOLUTE engine side (0 = Blue) whose point of view the potential takes; the other side's value is the negation.

    phi_tower(s, side) = (sum own tower hp/max_hp - sum foe tower hp/max_hp) / 3      each tower in [0, 1], dead = 0
    phi_crown(s, side) = (own crowns - foe crowns) / 3
    phi(s, side, w_tower, w_crown) = w_tower * phi_tower + w_crown * phi_crown
    F_t = gamma * Phi(s_{t+1}) - Phi(s_t),   Phi(s_T) = 0 at the terminal index T

Identities (tested): sum_t gamma^t F_t = -Phi(s_0) for any gamma, and the shaping part of the return-to-go from
decision t, sum_{k>=t} gamma^(k-t) F_k, is exactly -Phi(s_t). Both hold with a per-step discount gamma_t too
(``shaping_from_parts`` takes a sequence; rl_royale ``gae_gamma_unit: tick``): F_t = gamma_t Phi(s_{t+1}) - Phi(s_t)
and sum_{k>=t} (prod_{t<=i<k} gamma_i) F_k = -Phi(s_t), as long as the returns discount by the same gamma_t. So the shaping part of a per-decision return depends
only on the state decided in, never on the action taken there (Ng et al. 1999).

Crowns: ``raw()`` carries no crown count. ``crowns`` reads ``state["crowns"]`` ([side 0, side 1]) when the caller
attached the engine's own (the rshape tools do: ``env.core.state().players[s].crowns``), else derives them from the
towers: 3 if the foe king is destroyed, else the destroyed foe princess towers. A tower absent from the list counts
as destroyed (RoyaleSim may drop dead entities; a full list has 1 king + 2 princess per side).

Step 3 potentials (L74 reward/REWARD_ARCHITECTURE.md 3 A2 / A1 + A1b; rl_royale ``shaping: solvency | tower_score``),
public state only (own state, VISIBLE enemy bodies and towers, crowns, the clock; never hidden opponent info). The
actor records a small row per decision (``state_record``; e1_eval under ``record_phi`` = the mode name) and the learner
turns rows into Phi with the run's weights (``state_phi``); F, gamma and Phi = 0 at the end exactly as R2.
    solvency     row [T_left, T_right, D_left, D_right, E_own] (``solvency_record``), all in elixir:
                 Phi = -w min(cap, max(0, sum_lane max(0, k T_lane - D_lane) - E_own))     (``phi_solvency``)
    tower_score  row [own king, own princess x2, foe king, foe princess x2 (hp fractions), own / foe weakest standing
                 tower (princess units), own / foe crowns, tick] (``tower_score_record``):
                 Phi = w_own[c] mean_own h(f) - w_foe[c] mean_{standing foe princesses} f
                       + w_tb ramp(t) clip(own_tb - foe_tb, -1, 1)                        (``phi_tower_score``)
                 c = behind / even / ahead on crowns, h(f) = 1 - (1 - f)^p (concave: value mostly in standing), foe
                 king weight 0 always (also kept out of foe_tb), ramp 0 before 2x -> 1 at the end of overtime.
    trade        row [E_own, V_own, E_opp, V_opp] (``trade_record``; A3, step 5), elixir: V = ``body_value`` of that side's
                 bodies, E_opp = the PUBLIC opponent-elixir counter (the actor's ``opp_elixir: counter``), never the
                 opponent's true elixir:  Phi = w clip((E_own + V_own) - (E_opp + V_opp), -cap, cap)   (``phi_trade``)
                 A play is neutral when it lands (elixir becomes board value); a spell is worth what it removes.
    trade2       A3' (10-16, A3 failed its audit by ignoring tower hp): row = trade row + [own king, own princess x2, foe
                 king, foe princess x2 (hp fractions), tick] (``trade2_record``), Phi = w clip(b_e[ph] dE + b_t[ph] dT
                 + b_c[ph] dC, -cap, cap) in log-odds of winning (``phi_trade2``): dE = A3's margin, dT = foe princess
                 hp lost - own (princess + KING_PER_PRINCESS x king) hp lost, in princess towers (foe KING weight 0, as
                 A1), dC = foe princesses destroyed - own (the crown a finisher takes: linear-in-hp alone paid a Rocket
                 that FINISHES a 7% princess LESS than its 6 elixir), b per phase from the logistic win fit
                 (``TRADE2_B``). The crown term sits inside the clip, so |Phi| <= w cap still (0.24).
                 L74/reward/preflight_a3p.py audits it (AUDIT_A3P.txt).
|Phi| <= ``phi_bound`` on every reachable state (tests + L74/reward/preflight_a1a2.py / preflight_a3p.py).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

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


def phi_record(state: dict, side: int) -> list[float]:
    """What Phi needs of one state from ``side``'s view, the 8 floats e1_eval records per decision under
    ``cfg["record_phi"]``: own tower HP fractions (3, an absent tower = 0), the foe's (3), own crowns, foe crowns."""
    pad = (lambda xs: xs + [0.0] * (N_TOWERS - len(xs)))
    c = crowns(state)
    return pad(tower_fracs(state, side)) + pad(tower_fracs(state, 1 - side)) + [float(c[side]), float(c[1 - side])]


def phi_parts(rec) -> tuple:
    """(phi_tower, phi_crown) of ``phi_record`` rows (one row or [n, 8]): the same values as the state functions."""
    r = np.asarray(rec, dtype=np.float64)
    tower = ((r[..., 0] + r[..., 1] + r[..., 2]) - (r[..., 3] + r[..., 4] + r[..., 5])) / N_TOWERS
    return tower, (r[..., 6] - r[..., 7]) / N_TOWERS


def shaping_terms(states: Sequence[dict], side: int, gamma: float, weights: tuple[float, float],
                  terminal_index: Optional[int] = None) -> dict:
    """Per-decision shaping over one match. ``states`` = the states at decisions 0..n-1 (optionally followed by the
    final state); ``terminal_index`` T (default ``len(states)``) is the terminal state's index: Phi(s_T) = 0 whatever
    the state there holds, and states past T are ignored. Returns F (length T: F_t = gamma * Phi(s_{t+1}) - Phi(s_t))
    and the same per term (``tower``, ``crown``, each already weighted, summing to F), plus ``phi`` (length T+1, the
    last 0)."""
    T = len(states) if terminal_index is None else int(terminal_index)
    if not 0 < T <= len(states):
        raise ValueError(f"terminal_index {T} outside (0, {len(states)}]")
    return shaping_from_parts([phi_tower(s, side) for s in states[:T]], [phi_crown(s, side) for s in states[:T]],
                              gamma, weights)


def shaping_from_parts(tower: Sequence[float], crown: Sequence[float], gamma: float,
                       weights: tuple[float, float]) -> dict:
    """``shaping_terms`` on the UNWEIGHTED potentials of decisions 0..T-1 (``phi_tower`` / ``phi_crown`` values, or
    ``phi_parts`` of recorded rows); the state after the last one is terminal (Phi = 0). ``gamma``: one float, or a
    per-step sequence of length T (gamma[t] discounts step t -> t+1; the last one multiplies Phi = 0)."""
    w_tower, w_crown = float(weights[0]), float(weights[1])
    T = len(tower)
    scalar = np.ndim(gamma) == 0
    g = [float(gamma)] * T if scalar else [float(x) for x in gamma]
    if len(g) != T:
        raise ValueError(f"per-step gamma has {len(g)} entries for {T} steps")
    pt = [w_tower * float(x) for x in tower] + [0.0]
    pc = [w_crown * float(x) for x in crown] + [0.0]
    ft = [g[t] * pt[t + 1] - pt[t] for t in range(T)]
    fc = [g[t] * pc[t + 1] - pc[t] for t in range(T)]
    return {"F": [a + b for a, b in zip(ft, fc)], "tower": ft, "crown": fc,
            "phi": [a + b for a, b in zip(pt, pc)], "gamma": float(gamma) if scalar else g,
            "weights": (w_tower, w_crown)}


def returns_to_go(rewards: Sequence[float], gamma: float) -> list[float]:
    """G_t = sum_{k>=t} gamma^(k-t) r_k."""
    out, g = [0.0] * len(rewards), 0.0
    for t in range(len(rewards) - 1, -1, -1):
        g = float(rewards[t]) + gamma * g
        out[t] = g
    return out


def trailing_mean(values: Sequence[float], ticks: Sequence[int], window_ticks: int) -> np.ndarray:
    """Causal trailing mean of one match's per-row ``values`` (time order, ``ticks`` non-decreasing): row t averages
    the rows with tick in [tick_t - window_ticks, tick_t] up to and including itself, never a later row (``shaping:
    value_phi``; the L73 phi_eval smooth.py rule). ``window_ticks`` 0 = the values unchanged."""
    v = np.asarray(values, dtype=np.float64)
    t = np.asarray(ticks, dtype=np.int64)
    if len(v) != len(t):
        raise ValueError(f"{len(v)} values for {len(t)} ticks")
    if (np.diff(t) < 0).any():
        raise ValueError("ticks must be non-decreasing")
    c = np.r_[0.0, np.cumsum(v)]
    hi = np.arange(1, len(v) + 1)
    lo = np.searchsorted(t, t - int(window_ticks), side="left")
    return (c[hi] - c[lo]) / (hi - lo)


# ---- step 3 potentials: A2 solvency, A1 + A1b tower_score (module docstring) ------------------------------------
# Defaults (L74 REWARD_ARCHITECTURE.md 7 lesson 7: |Phi| <= 0.5 x the terminal reward on EVERY reachable state, by
# ``phi_bound``): solvency 0.04 x 10 = 0.40; tower_score max(w_own, w_foe) 0.30 + w_tb 0.15 = 0.45. Crown-state lists
# are [behind, even, ahead]: ahead -> protect own towers, little for the last foe princess (S16 "defend out");
# behind -> foe princesses weigh more. Even weights equal -> Phi = 0 at the start.
STATE_PHI_DEFAULTS = {"shaping_solv_w": 0.04, "shaping_solv_k": 1.0, "shaping_solv_cap": 10.0,
                      "shaping_ts_w_own": [0.15, 0.2, 0.3], "shaping_ts_w_foe": [0.3, 0.2, 0.1],
                      "shaping_ts_w_tb": 0.15, "shaping_ts_h_power": 3.0,
                      "shaping_tr_w": 0.03, "shaping_tr_cap": 8.0,      # trade: 0.03 x 8 = 0.24 (A3 "kept small")
                      "shaping_t2_w": 0.04, "shaping_t2_cap": 6.0}      # trade2: 0.04 x 6 log-odds = 0.24; 1 princess
#                                         tower destroyed in 2x = 0.04 x (2.754 + 2.115) = 0.195; 2 in 2x hit the clip
STATE_PHI_MODES = ("solvency", "tower_score", "trade", "trade2", "tower_phat")
# A3' coefficients (log-odds of winning per elixir of trade margin, per princess tower of hp margin, per princess tower
# DESTROYED margin) by phase [1x < T_2X, 2x < 3600, OT]: scratchpad/gauntlet/L74/reward/CROWN_FIT_R1.txt = fit_crown.py
# on pod_backup_weekend/pod1015_s5/ROWS_R1 (r1 vs gen_v1, 1000 SIM matches, 983 decisive, 398k rows; match-bootstrap CIs):
#   1x b_e 0.066 [0.023, 0.126] b_t 2.752 [2.13, 3.55] b_c 0.738 [-0.40, 2.07] (crown margin on 1.9% of rows; n.s.)
#   2x b_e 0.134 [0.098, 0.169] b_t 2.754 [2.37, 3.37] b_c 2.115 [1.33, 4.31] (8.9% of rows)
#   OT b_e 0.145 [0.108, 0.182] b_t 3.570 [3.04, 4.30] b_c 0 (no OT row has a crown margin: the first tower taken in
#      overtime ends the match, so the terminal reward pays it and dC = 0 on every OT decision; pinned 0, never used)
#   (associational, not causal; the elixir margin is the weak predictor)
TRADE2_B = ((0.066, 2.752, 0.738), (0.134, 2.754, 2.115), (0.145, 3.570, 0.0))
TRADE2_PHASE_TICKS = (2400, 3600)
# tower_phat (LOOP-LRN, plan1026 fast loop): Phi = P_hat(win | tower losses, elapsed time) - 0.5, |Phi| < 0.5, from
# ``tower_phat_record`` rows; P_hat = sigmoid(sum_k hat_k(t) c_k . x), x = foe - own (princess hp lost, king hp lost, king
# activated, crowns conceded), hat = continuous piecewise-linear in elapsed seconds on these knots (RX-X23's basis).
TOWER_PHAT_KNOTS_S = (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300)
# c = [princess x 11 knots, king x 11, king_on x 11, crowns x 11]: pilot/lrn/fit_phi.py on RX-X23's hfE.npz (33308
# /workspace/rx23, sha256 3ed632bfced9f5f4..., 14,845 decisive HF matches re-driven on crforge; train = SPLIT_HF dates 0-3,
# 11,867 matches, 835k rows every 3 s; ridge 1e-2, no intercept). Held-out (2,978 matches, both views; pilot/lrn/phi_fit.json):
# AUC .662 / .812 / .915, ECE .016 / .012 / .011 at 60 / 120 / 180 s. king_on < 0: activating the foe king costs us.
TOWER_PHAT_C = (1.613108, 0.970422, 1.755037, 2.262009, 2.366333, 2.221121, 2.750722, 3.074324, 3.473824, 4.102967,
                6.059022, 10.979707, 1.009929, 0.963392, 0.677698, 0.807111, 0.868943, 1.366414, 1.55039, 1.8114,
                1.956755, 3.240376, -2.564953, -0.977802, -0.871203, -0.827373, -0.78292, -0.706881, -0.714791,
                -0.648527, -0.674389, -0.664067, -0.794527, 7.036961, 0.853916, 1.00853, 1.381672, 1.649909, 1.91317,
                4.375724, 24.118843, 8.304652, 8.95221, 10.466201)
HALF_Y = 16000                  # own-frame y of the river centre (raw units, 1000 per tile; side 0 = Blue at low y)
LANE_X = 9000                   # own-frame x < 9000 = left lane, else right
CENTRE_BAND = 2500              # an own body within 2.5 tiles of the centre line can engage either lane
MOVE_EPS = 50                   # an enemy body on its own half counts once its own-frame y fell > 0.05 tile
KING_PER_PRINCESS = 4824 / 3052  # RoyaleSim level-11 king / princess max hp: the tiebreak drain compares ABSOLUTE hp
T_2X, T_OT_END = 2400, 6000     # ticks: double elixir starts / overtime ends (REGULAR_TIME_S 180, OVERTIME_S 120)
TROOP, DEPLOYING = 0, 12        # raw() entity kind (12 = still deploying: troop or building from the catalogue)


def card_table(cards) -> dict:
    """RoyaleSim ``core.cards()`` -> {card_id: (elixir, count, hitpoints, card_kind)}."""
    return {int(c.card_id): (float(c.elixir), int(c.count), float(c.hitpoints), str(c.card_kind)) for c in cards}


def own_xy(e: dict, side: int) -> tuple:
    """A raw() body's (x, y) in ``side``'s own frame (own king at low y)."""
    return (18000 - e["x"], 32000 - e["y"]) if int(side) == 1 else (e["x"], e["y"])


def body_value(e: dict, cards: dict):
    """Elixir value of one visible body, hp-scaled and level-free: elixir x hp / max_hp x min(1, max_hp / catalogue
    hitpoints) / count (a spawned body -- Witch skeleton, golemite -- carries its spawner's card and a smaller max_hp,
    so it is worth its share). None for an unknown card and for a SPELL card's bodies (Goblin Barrel goblins,
    Graveyard skeletons): spells never count."""
    c = cards.get(int(e["card_id"]))
    if c is None or c[3] == "SPELL" or c[2] <= 0:
        return None
    mx = max(float(e["max_hp"]), 1.0)
    return c[0] * max(0.0, float(e["hp"])) / mx * min(1.0, mx / c[2]) / max(1, c[1])


def solvency_record(state: dict, side: int, cards: dict, prev_y: dict) -> list:
    """A2's row from ``side``'s view: [T_left, T_right, D_left, D_right, E_own] (elixir). T_lane = ``body_value`` of
    enemy TROOP bodies in that lane (own-frame x) that are on my half (own-frame y <= HALF_Y) or on their half and
    walking toward mine (own-frame y fell > MOVE_EPS since this side's previous record; ``prev_y`` = {entity_id: own y},
    one dict per match, replaced here). Enemy buildings, spell effects and SPELL cards' bodies never count. D_lane =
    value of my bodies (troops, buildings, deploying) on my half in that lane, or within CENTRE_BAND of the centre
    (counted in both lanes). E_own = my exact elixir. Only positions, hp bars and my own elixir are read."""
    T, D, seen = [0.0, 0.0], [0.0, 0.0], {}
    for e in state.get("entities") or ():
        v = body_value(e, cards)
        if v is None:
            continue
        x, y = own_xy(e, side)
        if int(e["side"]) == int(side):
            if y <= HALF_Y:
                for lane in ((0, 1) if abs(x - LANE_X) <= CENTRE_BAND else (int(x >= LANE_X),)):
                    D[lane] += v
            continue
        kind = int(e.get("kind", -1))
        if not (kind == TROOP or (kind == DEPLOYING and cards[int(e["card_id"])][3] == "TROOP")):
            continue
        eid = e.get("entity_id")
        if eid is not None:
            seen[eid] = y
        if y <= HALF_Y or (eid in prev_y and y < prev_y[eid] - MOVE_EPS):
            T[int(x >= LANE_X)] += v
    prev_y.clear()
    prev_y.update(seen)
    me = next(p for p in state["players"] if int(p["side"]) == int(side))
    return T + D + [float(me["elixir_exact"])]


def phi_solvency(rows, p: dict) -> np.ndarray:
    """Phi per ``solvency_record`` row: -w min(cap, max(0, sum_lane max(0, k T - D) - E)); 0 when no push is committed
    (T = 0), so quiet play gets no hoarding incentive."""
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    need = np.maximum(0.0, float(p["shaping_solv_k"]) * r[:, 0:2] - r[:, 2:4]).sum(axis=1)
    return -float(p["shaping_solv_w"]) * np.minimum(float(p["shaping_solv_cap"]), np.maximum(0.0, need - r[:, 4]))


def tower_score_record(state: dict, side: int) -> list:
    """A1 + A1b's row from ``side``'s view (11 floats): own king, own princess x2, foe king, foe princess x2 (hp / max_hp,
    dead or absent = 0), own / foe weakest STANDING tower in princess units (a king x KING_PER_PRINCESS; the foe KING is
    never counted, king weight 0; none standing = 0), own / foe crowns (``crowns``), tick."""
    fr = []
    for s in (side, 1 - side):
        king, pr = 0.0, []
        for t in _towers(state):
            if int(t["side"]) != int(s):
                continue
            dead = bool(t.get("destroyed")) or float(t["hp"]) <= 0
            f = 0.0 if dead else min(1.0, float(t["hp"]) / float(t["max_hp"]))
            if t["type"] == "king":
                king = f
            else:
                pr.append(f)
        if len(pr) > 2:
            raise ValueError(f"side {s} has {len(pr)} princess towers")
        fr.append((king, pr + [0.0] * (2 - len(pr))))
    tb = [min([f for f in pr if f > 0] + ([k * KING_PER_PRINCESS] if i == 0 and k > 0 else []), default=0.0)
          for i, (k, pr) in enumerate(fr)]
    c = crowns(state)
    return [fr[0][0], *fr[0][1], fr[1][0], *fr[1][1], tb[0], tb[1], float(c[side]), float(c[1 - side]),
            float(state.get("tick", 0))]


def phi_tower_score(rows, p: dict) -> np.ndarray:
    """Phi per ``tower_score_record`` row (module docstring)."""
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    c = (np.sign(r[:, 8] - r[:, 9]) + 1).astype(int)                      # 0 behind, 1 even, 2 ahead
    w_own = np.asarray(p["shaping_ts_w_own"], dtype=np.float64)[c]
    w_foe = np.asarray(p["shaping_ts_w_foe"], dtype=np.float64)[c]
    own = w_own * (1.0 - (1.0 - r[:, 0:3]) ** float(p["shaping_ts_h_power"])).mean(axis=1)
    n = (r[:, 4:6] > 0).sum(axis=1)
    foe = w_foe * r[:, 4:6].sum(axis=1) / np.maximum(n, 1)                 # dead = 0: the standing princesses' mean
    ramp = np.clip((r[:, 10] - T_2X) / (T_OT_END - T_2X), 0.0, 1.0)
    return own - foe + float(p["shaping_ts_w_tb"]) * ramp * np.clip(r[:, 6] - r[:, 7], -1.0, 1.0)


def trade_record(state: dict, side: int, cards: dict, opp_est) -> list:
    """A3's row from ``side``'s view: [E_own, V_own, E_opp, V_opp] (elixir). V = ``body_value`` summed over that side's
    bodies (troops, buildings, deploying; a SPELL card's bodies and unknown cards never count), E_own = my exact elixir,
    E_opp = ``opp_est``, the public counter's estimate (ValueError when None: no hidden opponent elixir, ever)."""
    if opp_est is None:
        raise ValueError("shaping trade needs the public opponent-elixir counter (config opp_elixir: counter)")
    V = [0.0, 0.0]
    for e in state.get("entities") or ():
        v = body_value(e, cards)
        if v is not None:
            V[int(int(e["side"]) != int(side))] += v
    me = next(p for p in state["players"] if int(p["side"]) == int(side))
    return [float(me["elixir_exact"]), V[0], float(opp_est), V[1]]


def phi_trade(rows, p: dict) -> np.ndarray:
    """Phi per ``trade_record`` row: w clip((E_own + V_own) - (E_opp + V_opp), -cap, cap)."""
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    cap = float(p["shaping_tr_cap"])
    return float(p["shaping_tr_w"]) * np.clip(r[:, 0] + r[:, 1] - r[:, 2] - r[:, 3], -cap, cap)


def trade2_record(state: dict, side: int, cards: dict, opp_est) -> list:
    """A3''s row from ``side``'s view (11 floats): ``trade_record`` + ``tower_score_record``'s six hp fractions + tick."""
    ts = tower_score_record(state, side)
    return trade_record(state, side, cards, opp_est) + ts[:6] + [ts[10]]


def trade2_parts(rows) -> tuple:
    """(dE, dT, dC, phase index) per ``trade2_record`` row (module docstring)."""
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    dE = r[:, 0] + r[:, 1] - r[:, 2] - r[:, 3]
    own_lost = (1.0 - r[:, 5]) + (1.0 - r[:, 6]) + KING_PER_PRINCESS * (1.0 - r[:, 4])
    dT = (1.0 - r[:, 8]) + (1.0 - r[:, 9]) - own_lost                      # r[:, 7] = foe king: weight 0
    dC = (r[:, 8:10] <= 0).sum(axis=1) - (r[:, 5:7] <= 0).sum(axis=1)      # princesses destroyed: foe - own
    return dE, dT, dC, np.searchsorted(TRADE2_PHASE_TICKS, r[:, 10], side="right")


def phi_trade2(rows, p: dict) -> np.ndarray:
    """Phi per ``trade2_record`` row: w clip(b_e[phase] dE + b_t[phase] dT + b_c[phase] dC, -cap, cap)."""
    dE, dT, dC, ph = trade2_parts(rows)
    b = np.asarray(TRADE2_B)[ph]
    cap = float(p["shaping_t2_cap"])
    return float(p["shaping_t2_w"]) * np.clip(b[:, 0] * dE + b[:, 1] * dT + b[:, 2] * dC, -cap, cap)


def tower_phat_record(state: dict, side: int) -> list:
    """tower_phat's row from ``side``'s view (9 floats): per side (own, then foe) its LOSSES as r_exchange.running_losses
    counts them -- princess hp lost (sum of 1 - hp/max_hp over its 2 princess towers; destroyed or absent = 1), king hp
    lost (1 - hp/max_hp), king activated (king damaged or a princess destroyed; 0/1), crowns conceded -- then the tick."""
    ts = tower_score_record(state, side)                  # own king, own princess x2, foe king, foe princess x2, ..crowns
    out = []
    for king, prs, conceded in ((ts[0], ts[1:3], ts[9]), (ts[3], ts[4:6], ts[8])):
        p_lost, k_lost = (1.0 - prs[0]) + (1.0 - prs[1]), 1.0 - king
        out += [p_lost, k_lost, float(k_lost > 0 or min(prs) <= 0), float(conceded)]
    return out + [ts[10]]


def tower_phat_design(rows) -> np.ndarray:
    """[n, 4 K] design of ``tower_phat_record`` rows: x = foe loss - own loss (princess, king, king_on, crowns; our gain
    minus theirs), each times the K hat weights of the row's elapsed time (``TOWER_PHAT_KNOTS_S``, clipped to the last
    knot). No intercept: z(-x) = -z(x), so P(win) of one side = 1 - the other's and Phi = 0 at any even state."""
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    x = r[:, 4:8] - r[:, 0:4]
    kn = np.asarray(TOWER_PHAT_KNOTS_S, dtype=np.float64)
    s = np.clip(r[:, 8] / 20.0, kn[0], kn[-1])            # 20 ticks per second
    j = np.clip(np.searchsorted(kn, s, side="right") - 1, 0, len(kn) - 2)
    w = (s - kn[j]) / (kn[j + 1] - kn[j])
    H = np.zeros((len(s), len(kn)))
    H[np.arange(len(s)), j] = 1.0 - w
    H[np.arange(len(s)), j + 1] = w
    return np.concatenate([H * x[:, [k]] for k in range(x.shape[1])], axis=1)


def phi_tower_phat(rows, p: dict) -> np.ndarray:
    """Phi per ``tower_phat_record`` row: P_hat(win) - 0.5 = sigmoid(design . TOWER_PHAT_C) - 0.5, in (-0.5, 0.5)."""
    z = tower_phat_design(rows) @ np.asarray(TOWER_PHAT_C, dtype=np.float64)
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0))) - 0.5


def phi_bound(mode: str, p: dict) -> float:
    """max |Phi| over every reachable state: solvency w cap; tower_score max_c max(w_own[c], w_foe[c]) + w_tb (the
    own term is in [0, w_own], the foe term in [0, w_foe], the tiebreak term in [-w_tb, w_tb])."""
    if mode == "tower_phat":
        return 0.5
    if mode == "solvency":
        return float(p["shaping_solv_w"]) * float(p["shaping_solv_cap"])
    if mode == "trade":
        return float(p["shaping_tr_w"]) * float(p["shaping_tr_cap"])
    if mode == "trade2":
        return float(p["shaping_t2_w"]) * float(p["shaping_t2_cap"])
    if mode == "tower_score":
        return max(max(float(a), float(b)) for a, b in zip(p["shaping_ts_w_own"], p["shaping_ts_w_foe"])) \
            + float(p["shaping_ts_w_tb"])
    raise ValueError(f"no state potential {mode!r}")


def state_phi(mode: str, rows, p: dict) -> np.ndarray:
    return {"solvency": phi_solvency, "tower_score": phi_tower_score, "trade": phi_trade,
            "trade2": phi_trade2, "tower_phat": phi_tower_phat}[mode](rows, p)


def state_record(mode: str, state: dict, side: int, env, mem: dict) -> list:
    """The actor's per-decision row for ``mode`` (e1_eval ``record_phi``); ``mem`` = one dict per match and side
    (solvency: the RoyaleSim card catalogue of ``env`` and the previous enemy positions; trade: the catalogue and
    ``mem["opp_est"]``, the public counter's estimate the actor put there for this decision)."""
    if mode == "tower_score":
        return tower_score_record(state, side)
    if mode == "tower_phat":
        return tower_phat_record(state, side)
    if mode in ("trade", "trade2"):
        if "cards" not in mem:
            mem["cards"] = card_table(env.core.cards())
        return (trade_record if mode == "trade" else trade2_record)(state, side, mem["cards"], mem.get("opp_est"))
    if mode == "solvency":
        if "cards" not in mem:
            mem["cards"] = card_table(env.core.cards())
        return solvency_record(state, side, mem["cards"], mem.setdefault("prev_y", {}))
    raise ValueError(f"no state potential {mode!r}")
