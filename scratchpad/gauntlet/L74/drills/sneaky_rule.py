"""COPY of pipeline/sneaky_lock.py lines 23-216 (the pure rule: sneaky_situation / sneaky_lock_plan) from branch
worktree-agent-a666a874abb1e7c25 @ af50e7f (sneaky-lock worker, not merged to main at 2026-10-09). Copied, not imported, so the
drill selector D8 uses the SAME trigger as the mechanic_fork harness (MECH=sneaky). Do not edit; re-copy if the rule changes."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np

TILE = 18000                         # RoyaleSim subtiles per tile (royale_env.SCALE x the pool's 1000)
W_T, H_T = 18, 32                    # arena in tiles
ICEBOW_DECK = ("Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons")
XBOW_REACH_TOWER = 13.04             # tiles, X-Bow -> princess centre (calibrated modal offensive reach)
TORNADO_R = 5.5


# ------------------------------------------------------------------------------------------------------
# the rule (--sneaky-lock on): public BoardState in, (slot, cell, plan) out
# ------------------------------------------------------------------------------------------------------
BOARD_W, BOARD_H = 18.0, 32.0        # BoardState x, y in [0, 1] -> tiles; me at the bottom, forward = DECREASING y
XBOW_REACH_BASE = 12.1               # X-Bow centre -> a ground body's centre: 12.1 + its radius (11.5 range + 0.6 X-Bow radius)
BUILDING_RADIUS = 0.8                # a building in reach is a blocker the Tornado cannot move: generous footprint radius
PULL_PCT = 360.0                     # Tornado AttractPercentage 360: every tick a body in radius steps speed * 3.6 toward the centre
PULL_TICKS = 21                      # Tornado life 1050 ms
KING_BOX = (7.0, 1.0, 11.0, 5.0)     # enemy king footprint, board tiles
ENEMY_PRINCESS = ((3.5, 6.5), (14.5, 6.5))        # BoardState.towers[4], [5]
XBOW_KEEP_EXTRA = 0.35               # a LOCKED target is dropped only beyond reach + this (RoyaleSim: Knight 12.6 acquired, ~12.95 dropped)
SNEAKY_TICKS = 3                     # ... and only after this many ticks in a row (the retarget lags a tick or two)
SNEAKY_MARGIN = 0.3                  # tiles beyond that drop distance the forward model must reach (slack for the landing / walk error)
SNEAKY_SAT = 0.7                     # margins above this tie: the cell nearest the blocker wins (least collateral)
DEFAULT_UNIT = ("troop", 60.0, 0.5)
AIR_FALLBACK = frozenset({"lava_pups"})
NO_ROW = frozenset({"golemite", "elixir_blob", "elixir_golemite", "royal_recruit", "mother_witch_hog", "dark_elixir_bottle"})

_UNIT_CACHE: dict = {}


def unit_params(cls_id: int):
    """(kind, speed in milli-tiles per tick, radius in tiles) of a vocab class; kind troop | air | building | spell.  The catalogue
    row is extrapolate.catalog() (the table own_effects already uses live); a class it lacks is a 60-speed 0.5-radius ground troop."""
    got = _UNIT_CACHE.get(int(cls_id))
    if got is not None:
        return got
    from pipeline import vocab
    kind = vocab.kind_of(int(cls_id))
    key = vocab.UNIT_VOCAB[int(cls_id)]
    if kind == "troop":
        row = None
        if key not in NO_ROW:
            try:
                from pipeline.dataset_gen import card_key
                from pipeline.extrapolate import catalog
                cat = catalog()
                row = cat.get(card_key(key)) or cat.get(card_key(vocab.base_key(key)))
            except Exception:           # no catalogue on this machine: every body is the default troop (still pulled out the same way)
                row = None
        if row is not None:
            got = ("air" if float(row.get("flying_height") or 0) > 0 else "troop", float(row.get("speed") or 0.0),
                   float(row.get("collision_radius_milli") or 500) / 1000.0)
        else:
            got = ("air" if key in AIR_FALLBACK else DEFAULT_UNIT[0], DEFAULT_UNIT[1], DEFAULT_UNIT[2])
    else:
        got = (kind, 0.0, BUILDING_RADIUS)
    _UNIT_CACHE[int(cls_id)] = got
    return got


def box_distance(x, y, box=KING_BOX):
    """Distance from a point (or arrays of points) to an axis-aligned box (0 inside)."""
    return np.hypot(np.maximum(np.maximum(box[0] - x, 0.0), x - box[2]), np.maximum(np.maximum(box[1] - y, 0.0), y - box[3]))


def sneaky_situation(bs):
    """The blocked-X-Bow situation of a BoardState, or None.  -> dict(xbow, dmin, blockers[(cls, x, y, d, R)], others[(cls, x, y, R, kind,
    speed, radius)], towers): xbow (x, y) tiles = a X-Bow of mine that reaches an alive enemy princess; blockers = every enemy body it would
    target instead of that tower (ground, within 12.1 + radius, nearer than the tower); others = the other enemy ground bodies."""
    from pipeline import vocab
    xid = vocab.unit_id("x_bow")
    towers = bs.towers
    alive = [bool(towers[4 + j].alive) for j in (0, 1)]
    for xb in (u for u in bs.units if int(u.side) == 0 and int(u.cls) == xid):
        bx, by = float(xb.x) * BOARD_W, float(xb.y) * BOARD_H
        dt = [math.hypot(bx - tx, by - ty) for (tx, ty) in ENEMY_PRINCESS]
        reach = [d for d, a in zip(dt, alive) if a and d <= XBOW_REACH_TOWER]
        if not reach:
            continue
        dmin = min(reach)
        blockers, others = [], []
        for u in bs.units:
            if int(u.side) == 0:
                continue
            kind, speed, rad = unit_params(int(u.cls))
            if kind in ("air", "spell"):
                continue
            ux, uy = float(u.x) * BOARD_W, float(u.y) * BOARD_H
            d, reach_u = math.hypot(ux - bx, uy - by), XBOW_REACH_BASE + rad
            row = (int(u.cls), ux, uy, d, reach_u, kind, speed, rad)
            (blockers if d <= reach_u and d < dmin else others).append(row)
        return dict(xbow=(bx, by), dmin=dmin, blockers=blockers, others=others)
    return None


def _pull(p0, speed, rad, centres, xb, ticks=PULL_TICKS):
    """Forward model (the law of extrapolate.retrack, never overshooting the centre): a ground body at p0 (tiles) that walks toward my
    side at its catalogue speed while a Tornado centred on each of ``centres`` [N, 2] steps it speed * 3.6 per tick toward the
    centre (only while within 5.5 + radius of it).  -> its distance from ``xb`` after each tick, [ticks, N]."""
    c = np.asarray(centres, dtype=float)
    p = np.tile(np.asarray(p0, dtype=float), (len(c), 1))
    step, walk = speed * PULL_PCT / 100.0 / 1000.0, speed / 1000.0
    out = np.empty((ticks, len(c)))
    for k in range(ticks):
        d = c - p
        dist = np.hypot(d[:, 0], d[:, 1])
        inside = (dist > 1e-9) & (dist <= TORNADO_R + rad)
        move = np.where(inside, np.minimum(step, dist), 0.0) / np.where(dist > 1e-9, dist, 1.0)
        p = p + d * move[:, None]
        p[:, 1] += walk
        out[k] = np.hypot(p[:, 0] - xb[0], p[:, 1] - xb[1])
    return out


def _others_after(sit, centre, kmax):
    """Do the other ground bodies the Tornado drags stand in the X-Bow's reach, nearer than the tower, at tick ``kmax`` (the blocker's
    first tick out of reach)?  True = one would take the lock."""
    xb = np.asarray(sit["xbow"])
    for (_, ox, oy, _, _, kind, speed, rad) in sit["others"]:
        d = _pull((ox, oy), speed, rad, [centre], xb, kmax + 1)[kmax, 0]
        if d <= XBOW_REACH_BASE + rad and d < sit["dmin"]:
            return True
    return False


_GRID_TILES: dict = {}


def grid_tiles(grid):
    """-> (cell ids, [N, 2] board tiles) of every cell centre of the model's cell grid (model_v3.cell_xy), cached per grid kind."""
    if grid not in _GRID_TILES:
        from pipeline.model_v3 import cell_xy, GRID_X, GRID_Y
        cells = np.arange(GRID_X * GRID_Y)
        _GRID_TILES[grid] = (cells, np.array([cell_xy(int(c), grid) for c in cells]) * (BOARD_W, BOARD_H))
    return _GRID_TILES[grid]


def sneaky_lock_plan(bs, grid="floor", margin=None):
    """The Tornado cast of the rule, or None.  -> dict(cell, cx, cy, king_touch, margin, blocker, d_xbow, n_cands, n_free) with cx, cy in
    board tiles.  Public BoardState only.  Exactly one blocker (a ground troop; a building or a second body in reach = no attempt)."""
    margin = SNEAKY_MARGIN if margin is None else margin
    sit = sneaky_situation(bs)
    if sit is None or len(sit["blockers"]) != 1:
        return None
    cls, bx, by, d0, reach_u, kind, speed, rad = sit["blockers"][0]
    if kind != "troop":
        return None
    cells, xy = grid_tiles(grid)
    near = np.hypot(xy[:, 0] - bx, xy[:, 1] - by) <= TORNADO_R + rad - 0.25
    cells, xy = cells[near], xy[near]
    if not len(cells):
        return None
    xb = np.asarray(sit["xbow"])
    dist = _pull((bx, by), speed, rad, xy, xb)                                 # [ticks, N]
    drop = reach_u + XBOW_KEEP_EXTRA
    held = np.min([dist[k:len(dist) - SNEAKY_TICKS + 1 + k] for k in range(SNEAKY_TICKS)], axis=0).max(axis=0)    # best level held SNEAKY_TICKS in a row
    margins = held - drop
    king = box_distance(xy[:, 0], xy[:, 1], KING_BOX) < TORNADO_R
    ok = margins >= margin
    for touch in (False, True):                                                 # king-free cells first
        idx = np.flatnonzero(ok & (king == touch))
        if not len(idx):
            continue
        near_b = np.hypot(xy[idx, 0] - bx, xy[idx, 1] - by)
        order = idx[np.lexsort((cells[idx], near_b, -np.minimum(margins[idx], SNEAKY_SAT)))]
        for i in order[:40]:
            k = int(np.argmax(dist[:, i] > drop))
            if _others_after(sit, xy[i], k):
                continue
            return dict(cell=int(cells[i]), cx=float(xy[i, 0]), cy=float(xy[i, 1]), king_touch=bool(touch), margin=float(margins[i]),
                        blocker=int(cls), d_xbow=float(d0), n_cands=int(ok.sum()), n_free=int((ok & ~king).sum()))
    return None


def sneaky_lock_choice(options, bs, names, allowed, grid, pending=False):
    """-> (slot, cell, plan) when the rule fires, else None: ``--sneaky-lock on``, nothing pending, a Tornado in hand and affordable
    (``allowed``), and ``sneaky_lock_plan`` finds a cast.  The caller applies it over the gate / card / cell and after the lethal rules."""
    if getattr(options, "sneaky_lock", "off") != "on" or pending:
        return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).split("@")[0].lower() == "tornado" and allowed[i]]
    if not slots:
        return None
    plan = sneaky_lock_plan(bs, grid)
    return None if plan is None else (slots[0], plan["cell"], plan)


# ------------------------------------------------------------------------------------------------------
