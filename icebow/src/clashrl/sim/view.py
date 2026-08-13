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


class DomainRand:
    """Per-match VISUAL randomization for the synthetic render (sim2real for the CNN branch).

    The policy's conv trunk only ever sees this synthetic canvas, so live it meets real pixels
    (and every new ARENA repaints them) fully out-of-distribution -- measured live: the cell
    argmax collapsed to one corner regardless of the board. Randomizing the rendering per match
    (a stable 'arena look' within a match, a different one each match) forces the CNN to key on
    STRUCTURE (blob positions/colours relative to each other) instead of one fixed palette.

    Parameters are sampled at reset() from ``observation.domain_rand`` config: background/river
    palette jitter, global brightness/contrast, additive pixel noise. Team blob hues are jittered
    only mildly -- blue-vs-red identity is signal, not style."""

    def __init__(self, cfg, rng):
        dr = cfg.get("observation", "domain_rand", default={}) or {}
        self.enabled = bool(dr.get("enabled", True))
        self.bg_jitter = float(dr.get("bg_jitter", 55))        # +- per BGR channel on grass/river
        self.team_jitter = float(dr.get("team_jitter", 25))    # +- on unit/tower colours (mild)
        self.gain_range = dr.get("gain", [0.7, 1.25])          # global contrast multiplier
        self.bias_range = dr.get("bias", [-25, 25])            # global brightness offset
        self.noise_max = float(dr.get("noise", 6.0))           # additive uniform pixel noise amplitude
        self.rng = rng
        self.resample()

    def _jit(self, base, amt):
        return tuple(int(min(255, max(0, c + self.rng.uniform(-amt, amt)))) for c in base)

    def resample(self) -> None:
        """New visual 'arena' for a new match."""
        if not self.enabled:
            self.grass, self.river, self.you, self.enemy = _GRASS, _RIVER, _YOU, _ENEMY
            self.gain, self.bias, self.noise = 1.0, 0.0, 0.0
            self._np = None
            return
        self.grass = self._jit(_GRASS, self.bg_jitter)
        self.river = self._jit(_RIVER, self.bg_jitter)
        self.you = self._jit(_YOU, self.team_jitter)
        self.enemy = self._jit(_ENEMY, self.team_jitter)
        self.gain = self.rng.uniform(float(self.gain_range[0]), float(self.gain_range[1]))
        self.bias = self.rng.uniform(float(self.bias_range[0]), float(self.bias_range[1]))
        self.noise = self.rng.uniform(0.0, self.noise_max)
        self._np = np.random.default_rng(self.rng.randrange(2 ** 31))

    def finish(self, img: np.ndarray) -> np.ndarray:
        """Apply the match's global gain/bias/noise to a rendered frame."""
        if not self.enabled or (self.gain == 1.0 and self.bias == 0.0 and self.noise == 0.0):
            return img
        out = img.astype(np.float32) * self.gain + self.bias
        if self.noise > 0.0 and self._np is not None:
            out += self._np.uniform(-self.noise, self.noise, img.shape).astype(np.float32)
        return np.clip(out, 0, 255).astype(np.uint8)


def to_local(x: float, y: float, team: int) -> "tuple[float, float]":
    """Map an engine coordinate into ``team``'s local frame (team at the bottom, attacking up)."""
    return (x, y) if team == 0 else (1.0 - x, 1.0 - y)


def render_obs(engine, oh: int, ow: int, team: int = 0, dr: "DomainRand | None" = None) -> np.ndarray:
    """Synthetic top-down arena from ``team``'s perspective (viewing team blue, other red). For
    team 0 this reproduces the env's original render exactly. ``dr`` (a DomainRand) restyles the
    canvas per match -- both teams' views use the SAME match style, like a real arena."""
    grass = dr.grass if dr is not None else _GRASS
    river = dr.river if dr is not None else _RIVER
    you = dr.you if dr is not None else _YOU
    enemy = dr.enemy if dr is not None else _ENEMY
    img = np.zeros((oh, ow, 3), np.uint8)
    img[:, :] = grass
    img[oh // 2, :] = river
    for t in (team, 1 - team):
        col = you if t == team else enemy
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
            img[cyp, cxp] = you if u.team == team else enemy
    return img if dr is None else dr.finish(img)


# --- SEMANTIC CANVAS (the obs-canvas flip) ------------------------------------------------------
# Ground-truth twin of clashrl.detect_obs's detector-rendered channels. The channel INDICES must
# match detect_obs.CHANNELS exactly, or the sim prior trains one layout and live play feeds another.
CANVAS_DIM = 6                # enemy ground/air/building, my ground/building, spell


def _canvas_channel(u, team: int) -> int:
    """Semantic channel for a sim unit, mirroring detect_obs._channel_of's role mapping."""
    mine = u.team == team
    if u.spec.kind == "spell":
        return 5                                     # spell / AOE (team-agnostic)
    if u.spec.kind == "building" or u.spec.siege:
        return 4 if mine else 2                      # building / siege
    if mine:
        return 3                                     # my troop (air or ground)
    return 1 if u.spec.flying else 0                 # enemy air vs ground


def semantic_channels(engine, oh: int, ow: int, team: int = 0, rng=None,
                      presence_recall: float = 1.0) -> np.ndarray:
    """The sim's stand-in for the live detector's semantic CANVAS, in ``team``'s local frame.

    Rendered from GROUND TRUTH but degraded by ``presence_recall`` -- the class-agnostic presence
    recall `detect-eval` gates on -- because live the canvas is built from detections and a missed
    unit is simply absent from it. Deliberately NOT whitelist-filtered and NOT hit by the identity
    PRECISION knob: the canvas carries position + team + coarse role, so naming a Knight a Valkyrie
    lands in the same channel, and the detector boxes units it cannot confidently name.

    Returns uint8 [oh, ow, CANVAS_DIM] on the same 0..255 scale as the arena image.
    """
    from . import engine as _engine        # imported here to keep view importable from engine
    ch = np.zeros((oh, ow, CANVAS_DIM), np.uint8)
    tx, ty = float(_engine._TILES_X), float(_engine._TILES_Y)
    for u in engine.units:
        if u.hp <= 0 or u.deploy_left > 0:
            continue                                  # still spawning = not on screen yet
        if presence_recall < 1.0 and rng is not None and rng.random() > presence_recall:
            continue                                  # the detector would have MISSED this unit
        lx, ly = to_local(u.x, u.y, team)
        cxp, cyp = int(lx * ow), int(ly * oh)
        rx = max(1, int(round(float(u.spec.radius) / tx * ow)))
        ry = max(1, int(round(float(u.spec.radius) / ty * oh)))
        x0, x1 = max(0, cxp - rx), min(ow, cxp + rx + 1)
        y0, y1 = max(0, cyp - ry), min(oh, cyp + ry + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        k = _canvas_channel(u, team)
        ch[y0:y1, x0:x1, k] = 255
    return ch


TOWER_DIM = 6                 # (L princess, R princess, king) x (mine, theirs)


def tower_vector(engine, team: int = 0) -> np.ndarray:
    """HP FRACTION of every crown tower: (L, R, king) for ``team``, then the same for its OPPONENT.
    0.0 means destroyed, so crown counts are implied and no separate alive flag is needed.

    Mirrored by construction and used by BOTH the agent (team 0) and the self-play opponent (team 1)
    -- the two used to build their observation blocks from separate code, and that is exactly how the
    self-play mirror silently drifted out of sync before (b9ff324).

    Not degraded by sim_detector_recall: a crown tower's HP is PRINTED on the HUD, so live this is a
    READ (TowerHpTracker's digit CNN, already running in env.py for the reward terms) rather than a
    detection.
    """
    v = np.zeros(TOWER_DIM, np.float32)
    for side, off in ((team, 0), (1 - team, 3)):
        for i, t in enumerate(engine.towers[side][:3]):
            v[off + i] = (max(0.0, float(t.hp)) / t.max_hp) if t.max_hp > 0 else 0.0
    return v


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
