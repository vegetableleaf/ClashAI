"""TARGET-OBS (owner 10-30, plan1026/target_obs/TARGET_OBS.md): which unit targets which, as per-unit-token inputs.

    rows, idx = target_rows(units, tok, mask, side)    # [len(tok), TGT_N] float32, [len(tok)] int64 (-1 = none)

``units`` = bodies in ``sim_unit_state.extract``'s schema, the ONE interface both sides already produce:
  SIM  ``sim_unit_state.extract(battle)["units"]`` (crforge: ``CfCore.acquired``, the facade's acquired target)
  LIVE ``live_unit_state.LiveCues.units(frame, prev)`` (the reader's reference after its acquired rule: a target-layer
       model gets acq_rule "engine", CfCore.acquired's formula, live_play.load_pilot; TARGET_OBS.md M1c-R)
Read per body: id (``uid`` SIM / ``generation`` live), ``team``, ``x`` / ``y`` (tiles, engine frame), tower (SIM ``kind``
princess_tower / king_tower; live ``tower``), ``attack.target`` (an id or None), ``attack.frac`` (0..1 or None).

Tokens take bodies by the cue match (``live_unit_state.align`` = ``e1_eval.sim_cue_rows``: unit tokens, same side,
nearest-first, one body per token, within CUE_MATCH_TILES). Per matched token, TGT_N floats:
  [known, target is a unit token, target is a crown tower, attack frac, dx, dy (target - unit, board frame, token
   units), unit tokens targeting me / 4, a crown tower targets me]
and ``idx`` = the token index of the target (-1: none, a tower, or a body no token took). Unmatched tokens = 0 / -1.
Path goals are NOT targets: both sources give the acquired target only (live: the far default tower is dropped).
"""
from __future__ import annotations

import numpy as np

TGT_N = 8
TOWER_KINDS = ("princess_tower", "king_tower")
MATCH_TILES = 3.0      # = e1_eval.CUE_MATCH_TILES (test_target_obs pins it; not imported: e1_eval imports royalegym)


def _uid(u):
    return u["uid"] if "uid" in u else u["generation"]


def _tower(u):
    return bool(u.get("tower")) or u.get("kind") in TOWER_KINDS


def _board(x, y, side):
    """Engine tiles -> this side's token frame (obs_contract._engine_xy: side 1 sees the board mirrored)."""
    bx, by = x / 18.0, 1.0 - y / 32.0
    return (1.0 - bx, 1.0 - by) if side == 1 else (bx, by)


def token_match(tok: np.ndarray, mask: np.ndarray, side: int, bodies: list) -> dict:
    """{body index: token index} by live_unit_state.align's rule, verbatim. ``bodies`` = non-tower extract units."""
    ti = np.flatnonzero(mask & (tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0)))
    out = {}
    if not len(ti) or not bodies:
        return out
    bxy = np.array([_board(b["x"], b["y"], side) for b in bodies])
    mine = np.array([b["team"] == side for b in bodies])
    d = np.hypot((tok[ti, 4:5] - bxy[:, 0]) * 18.0, (tok[ti, 5:6] - bxy[:, 1]) * 32.0)
    d[(tok[ti, 1:2] > 0) != mine] = np.inf
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if not d[i, j] <= MATCH_TILES:
            return out
        out[int(j)] = int(ti[i])
        d[i, :] = np.inf
        d[:, j] = np.inf


def target_rows(units, tok: np.ndarray, mask: np.ndarray, side: int):
    """-> (rows [len(tok), TGT_N] float32, idx [len(tok)] int64). ``units`` None (a degraded live frame) -> all 0 / -1."""
    rows = np.zeros((len(tok), TGT_N), np.float32)
    idx = np.full(len(tok), -1, np.int64)
    if not units:
        return rows, idx
    by_id = {_uid(u): u for u in units}
    bodies = [u for u in units if not _tower(u)]
    tok_of = {_uid(bodies[j]): t for j, t in token_match(tok, mask, side, bodies).items()}
    for u in units:                                   # incoming: who targets each matched token
        t = tok_of.get(u["attack"]["target"])
        if t is None:
            continue
        if _tower(u):
            rows[t, 7] = 1.0
        elif _uid(u) in tok_of:
            rows[t, 6] += 0.25
    for b in bodies:
        t = tok_of.get(_uid(b))
        if t is None:
            continue
        a = b["attack"]
        rows[t, 0] = 1.0
        rows[t, 3] = float(a.get("frac") or 0.0)
        tu = by_id.get(a["target"]) if a["target"] is not None else None
        if tu is None:
            continue
        if _tower(tu):
            rows[t, 2] = 1.0
        elif _uid(tu) in tok_of:
            rows[t, 1] = 1.0
            idx[t] = tok_of[_uid(tu)]
        (ux, uy), (vx, vy) = _board(b["x"], b["y"], side), _board(tu["x"], tu["y"], side)
        rows[t, 4], rows[t, 5] = vx - ux, vy - uy
    return rows, idx


def sim_target_rows(match):
    """SIM side: the battle's units at the decision tick (sim_cue_rows' extract call and memo) -> target_rows on the
    prepared view."""
    from pipeline.sim_unit_state import extract
    c = extract(match.env.core._battle, match.__dict__.setdefault("_cue_memo", {}), hit_window_ms=100)
    tok, mask = match._obs[0], match._obs[1]
    return target_rows(c["units"], tok, mask, match.side)


def live_target_rows(cues, frame: dict, prev, tok: np.ndarray, mask: np.ndarray, side: int):
    """LIVE side (live_gen.GenPilot.row for a target-layer checkpoint): ``cues`` = the pilot's LiveCues. A malformed
    block reads as no targets (all 0 / -1), never stops a match."""
    try:
        us = cues.units(frame, prev)
    except (KeyError, TypeError, ValueError, AttributeError):
        us = None
    return target_rows(us, tok, mask, side)
