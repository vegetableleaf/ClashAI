"""Perspective helpers shared by the sim env (team 0 = you) and the self-play opponent (team 1).

The engine is asymmetric on screen -- team 0 defends the BOTTOM, team 1 the TOP -- but the policy was
only ever trained from team 0's point of view (you at the bottom/blue, enemy at the top/red, deploy in
the lower half, attack up). To let a FROZEN copy of that same policy pilot team 1 (self-play), we show
it a MIRRORED board: a 180-degree rotation `(x, y) -> (1 - x, 1 - y)` puts team 1 at the bottom so the
policy sees itself exactly as it was trained. The chosen placement cell is transformed back the same way
before it hits the engine. `to_local(..., team=0)` is the identity, so team 0's render/threat are byte
-for-byte what the env produced before -- these helpers just generalise the existing code to either team.
"""
from __future__ import annotations

import numpy as np

_GRASS = (25, 80, 25)      # BGR
_RIVER = (120, 90, 30)
_YOU = (230, 90, 60)       # the viewing team = blue
_ENEMY = (60, 60, 230)     # the other team = red


def to_local(x: float, y: float, team: int) -> "tuple[float, float]":
    """Map an engine coordinate into ``team``'s local frame (team at the bottom, attacking up)."""
    return (x, y) if team == 0 else (1.0 - x, 1.0 - y)


def render_obs(engine, oh: int, ow: int, team: int = 0) -> np.ndarray:
    """Synthetic top-down arena from ``team``'s perspective (viewing team blue, other red). For
    team 0 this reproduces the env's original render exactly."""
    img = np.zeros((oh, ow, 3), np.uint8)
    img[:, :] = _GRASS
    img[oh // 2, :] = _RIVER
    for t in (team, 1 - team):
        col = _YOU if t == team else _ENEMY
        for tw in engine.towers[t]:
            if not tw.alive:
                continue
            lx, ly = to_local(tw.x, tw.y, team)
            cxp, cyp = int(lx * ow), int(ly * oh)
            hw = 3 if tw.king else 2
            img[max(0, cyp - hw):cyp + hw + 1, max(0, cxp - hw):cxp + hw + 1] = col
    for u in engine.units:
        if u.hp <= 0:
            continue
        lx, ly = to_local(u.x, u.y, team)
        cxp, cyp = int(lx * ow), int(ly * oh)
        if 0 <= cyp < oh and 0 <= cxp < ow:
            img[cyp, cxp] = _YOU if u.team == team else _ENEMY
    return img


def threat_vector(engine, threat_dim: int, team: int = 0) -> np.ndarray:
    """Compact enemy-threat approximation from ``team``'s perspective: the OTHER team's units that have
    crossed onto ``team``'s half (local y >= 0.5). For team 0 this matches the env's original vector."""
    v = np.zeros(threat_dim, np.float32)
    foe = 1 - team
    locals_ = [to_local(u.x, u.y, team) for u in engine.units if u.team == foe]
    hps = [u.hp for u in engine.units if u.team == foe]
    foes = [(lx, ly, hp) for (lx, ly), hp in zip(locals_, hps) if ly >= 0.5]
    if not foes:
        return v
    mass = sum(min(1.0, hp / 800.0) for _, _, hp in foes)
    biggest = max(hp for _, _, hp in foes) / 3000.0
    cx = sum(lx for lx, _, _ in foes) / len(foes)
    depth = (max(ly for _, ly, _ in foes) - 0.5) / 0.5
    v[0] = min(1.0, mass)
    v[1] = min(1.0, len(foes) / 6.0)
    v[2] = min(1.0, biggest)
    v[3] = 1.0 if cx < 0.4 else 0.0
    v[4] = 1.0 if cx > 0.6 else 0.0
    v[5] = min(1.0, max(0.0, depth))
    return v


def identity_items(engine, team: int, whitelist) -> "list[tuple[str, float]]":
    """``(base_card, depth_frac)`` for the OTHER team's units that have crossed onto ``team``'s half
    (local y >= 0.5), filtered to the RECOGNISED ``whitelist`` -- the ground-truth input to
    :func:`clashrl.card_threat.identity_threat_vector` (the sim's stand-in for the live detector).
    depth_frac in [0,1] is how far past the river the unit has advanced toward ``team``'s king."""
    if not whitelist:
        return []
    foe = 1 - team
    items: "list[tuple[str, float]]" = []
    for u in engine.units:
        if u.team != foe or u.hp <= 0:
            continue
        base = getattr(u.spec, "base", None)
        if base is None or base not in whitelist:
            continue
        _lx, ly = to_local(u.x, u.y, team)
        if ly >= 0.5:
            items.append((base, (ly - 0.5) / 0.5))
    return items


def opponent_memory_items(engine, team: int, whitelist) -> "list[tuple[str, float]]":
    """``(base_card, local_y)`` for ALL of the OTHER team's recognised (whitelisted) units, on EITHER
    half (local_y in [0,1]; >=0.5 = crossed onto ``team``'s half / attacking, <0.5 = on their own half
    / staging a push at the back). The ground-truth input to :class:`clashrl.card_threat.OpponentMemory`
    (the sim's stand-in for the live detector's whole-match read)."""
    if not whitelist:
        return []
    foe = 1 - team
    items: "list[tuple[str, float]]" = []
    for u in engine.units:
        if u.team != foe or u.hp <= 0:
            continue
        base = getattr(u.spec, "base", None)
        if base is None or base not in whitelist:
            continue
        _lx, ly = to_local(u.x, u.y, team)
        items.append((base, ly))
    return items


def interaction_state(engine, team: int, whitelist, rng=None, recall: float = 1.0,
                      recall_by_card=None):
    """Ground-truth inputs for :mod:`clashrl.interactions` from ``team``'s point of view, in its LOCAL
    frame (mirrored for team 1): (units, my_towers, enemy_towers). Units = BOTH sides' recognisable
    (whitelisted) troops/buildings tagged 'mine'/'enemy'; optional detector-noise RECALL drops mimic
    live coverage (the live block is built from detections, which miss units)."""
    units = []
    for u in engine.units:
        if u.hp <= 0:
            continue
        base = getattr(u.spec, "base", None)
        if base is None or (whitelist and base not in whitelist):
            continue
        if rng is not None:
            r = recall_by_card.get(base, recall) if recall_by_card else recall
            if r < 1.0 and rng.random() > r:
                continue                              # detector would have MISSED this unit
        lx, ly = to_local(u.x, u.y, team)
        units.append(("mine" if u.team == team else "enemy", base, lx, ly))
    def _side(tws):
        out = []
        for t in tws[:3]:
            lx, ly = to_local(t.x, t.y, team)
            out.append((lx, ly, bool(t.alive)))
        return out
    return units, _side(engine.towers[team]), _side(engine.towers[1 - team])


def apply_detector_noise(items, recall: float, precision: float, rng, whitelist, recall_by_card=None):
    """Simulate the LIVE YOLO detector's imperfect RECALL (missed units) + PRECISION (misclassifications)
    on the sim's ground-truth ``items`` = ``[(base_card, depth/local_y), ...]``, so a sim-trained prior
    learns to act on a SPARSE, live-like identity signal instead of perfect info (narrows the sim-to-real
    gap). ``recall`` = per-detection chance the unit is seen; ``precision`` = chance a seen detection keeps
    its true identity (else it's relabelled as another whitelisted card). ``recall_by_card`` (optional) is a
    base-card -> recall dict that OVERRIDES the scalar per card -- the detector names some cards far more
    reliably than others -- and any card absent from it falls back to the scalar ``recall``. 1.0/1.0 with no
    per-card table -> ``items`` unchanged."""
    if recall >= 1.0 and precision >= 1.0 and not recall_by_card:
        return items
    cards = tuple(whitelist) if whitelist else ()
    out = []
    for name, d in items:
        r = recall_by_card.get(name, recall) if recall_by_card else recall
        if r < 1.0 and rng.random() > r:
            continue                                   # detector MISSED this unit (per-card recall)
        if precision < 1.0 and cards and rng.random() > precision:
            name = rng.choice(cards)                   # MISCLASSIFIED as another whitelisted card (precision)
        out.append((name, d))
    return out
