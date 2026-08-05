"""STRUCTURAL board raster -- the sim/real-identical replacement for the RGB observation.

Commit 5cdf867 added DOMAIN RANDOMIZATION because the conv trunk was blind on real frames (measured:
2 distinct argmax cells on real input vs 11 on sim obs, same net). DR only randomizes STYLE -- palette,
gain, noise -- so it can teach the trunk to ignore a *palette*, but the sim canvas and a real screenshot
still differ STRUCTURALLY: the synthetic render draws one pixel per unit on flat grass, the real frame
carries sprites, animations, HUD, particle effects, arena art. No amount of colour jitter closes that.

This module removes the appearance channel from the problem entirely. Instead of asking the CNN to infer
"what is where" from pixels that only exist in one of the two worlds, both worlds RASTERIZE THE SAME
SEMANTIC FACTS into the same tensor:

    channel 0  my_troop        1  enemy_troop
    channel 2  my_building     3  enemy_building
    channel 4  my_tower        5  enemy_tower

The pixel VALUES are unit MASS (troops/buildings) or remaining HP FRACTION (towers) -- see `mass()` /
the tower branch of `sim_entities` / `LiveRaster.entities`. Sim renders it from engine ground truth;
live renders it from the detector's tagged read. There is no appearance gap left to randomize, because
appearance is no longer part of the observation.

IDENTICAL BY CONSTRUCTION -- what that phrase buys, precisely:

* One rasterizer. `Rasterizer.render()` is the ONLY code that turns entities into pixels, and both
  worlds call it. The sim/live adapters differ only in where the entity list comes from.
* One coordinate space. The sim engine already works in the same normalized frame coordinates the live
  detector reports (`env.my_towers` / `env.enemy_towers` seed BOTH `SimEngine._anchors` and the live
  `reward._anchors`), so an (x, y) means the same board position on both sides with no transform.
* One KB. Footprint radius and mass come from `CardDB` keyed on the BASE CARD, never from anything
  world-specific -- not the sim's `CardSpec.radius`, not the detector's box size. A Musketeer stamps the
  same ellipse with the same value in both worlds.
* Level-independent. Mass uses the KB's base (level-11) hitpoints, not the per-match scaled HP, because
  live we only recover the card's IDENTITY -- never its level or current HP. Encoding sim-only knowledge
  here would quietly re-open the very gap this module exists to close.

WHAT THE VALUES CAN AND CANNOT BE. The prompt asked for "HP or mass"; live those are not equally
available, so each channel takes the strongest signal BOTH worlds can actually produce:

* troops / buildings -> KB mass (hitpoints x count, normalized). A detection yields a class name, a box
  and a confidence -- never a health bar -- so per-unit CURRENT hp is not observable live at all. The sim
  has it and deliberately does not use it.
* towers -> true remaining HP fraction. This one IS observable on both sides (engine `hp/max_hp`;
  live `TowerHpTracker`'s OCR), so the tower channels carry real HP.

DETECTOR REALISM (`observation.semantic.detector_realism`, default on). The live raster can only contain
what the detector actually named: whitelisted cards, subject to its recall and precision. Rendering the
sim raster from perfect ground truth would hand the policy a DENSE map in training and a SPARSE one live
-- a fresh structural gap in place of the one just closed. So the sim raster is filtered through the same
`observation.sim_detector_*` model every other Stage-3 block already uses. Set it false to see the
unfiltered ground-truth raster (useful for an ablation; not recommended for a transfer run).

The filter draws from a PRIVATE rng (like `view.DomainRand`) and never touches `env.rng`, so the
777-seeded eval deck stream stays bit-identical whether the raster is on, off, or hybrid.

SPELLS are not rastered. They are sub-second events sampled at a ~1s agent cadence, so a spell channel
would be almost always empty and fire on an arbitrary subset of casts -- noise, not signal. Spell
awareness stays where it already works: the reward terms and the interaction block.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np

from . import card_threat

# Semantic channels fed to the policy -- the ORDER is the channel index, and it is baked into every
# checkpoint trained on this raster. Append only; never reorder.
CHANNELS = ("my_troop", "enemy_troop", "my_building", "enemy_building", "my_tower", "enemy_tower")
N_CHANNELS = len(CHANNELS)
CH_MY_TROOP, CH_ENEMY_TROOP, CH_MY_BUILDING, CH_ENEMY_BUILDING, CH_MY_TOWER, CH_ENEMY_TOWER = range(6)

RGB_CHANNELS = 3
MODES = ("rgb", "semantic", "hybrid")

# The real board is an 18 x 32 tile lattice (see actions.ActionSpace). Footprints are specified in TILES
# and converted through the arena box, so they stay correct if `action.grid` is coarsened -- the grid is
# the ACTION resolution, unrelated to the physical tile size.
_TILES_W, _TILES_H = 18, 32

# channel -> BGR colour for the human-readable preview only (never fed to the net)
_VIZ = {CH_MY_TROOP: (255, 140, 40), CH_ENEMY_TROOP: (40, 40, 255),
        CH_MY_BUILDING: (200, 90, 0), CH_ENEMY_BUILDING: (0, 0, 150),
        CH_MY_TOWER: (255, 220, 120), CH_ENEMY_TOWER: (120, 200, 255)}


# --- config -------------------------------------------------------------------------------------
def obs_mode(cfg) -> str:
    """`observation.obs_mode`: 'rgb' (the pre-semantic behaviour), 'semantic' (this raster alone) or
    'hybrid' (RGB channels THEN semantic channels, for an A/B that holds everything else fixed)."""
    m = str(cfg.get("observation", "obs_mode", default="semantic") or "semantic").strip().lower()
    if m not in MODES:
        raise ValueError(f"observation.obs_mode must be one of {MODES}, got {m!r}")
    return m


def obs_channels(cfg) -> int:
    """Channel count of the observation tensor -- the policy's conv `in_ch`. Stored in every checkpoint
    and checked on load, because a net trained on one channel layout cannot read another."""
    m = obs_mode(cfg)
    return RGB_CHANNELS if m == "rgb" else (N_CHANNELS if m == "semantic" else RGB_CHANNELS + N_CHANNELS)


def raster_whitelist(cfg, db) -> set:
    """Cards the raster may contain = `observation.detector_cards` UNION YOUR OWN DECK.

    `detector_cards` is documented as the ENEMY cards the detector reliably NAMES, and it is tuned on
    enemy-recall measurements -- your own X-Bow and Tesla are not on it. Using it alone as the raster
    filter left `my_building` permanently zero, i.e. the policy could never see the win condition it is
    supposed to be placing. Your own cards are a different recognition problem and a much easier one:
    the detector is trained hardest on your deck (it is in every frame of every recording), and live you
    also KNOW what you played and where -- `TeamTracker.record_play` already tags those spawns 'mine'.

    Own-deck cards absent from `detector_cards` still pay the global recall in the sim, so they are not
    modelled as perfectly visible -- just as visible at all.
    """
    wl = set(cfg.get("observation", "detector_cards", default=[]) or [])
    sem = cfg.get("observation", "semantic", default={}) or {}
    if bool(sem.get("include_own_deck", True)):
        wl |= {card_threat.base_key(k) for k in db.deck_identities()}
    return wl


def wants_detector(cfg) -> bool:
    """True when the LIVE observation needs a detector pass to be non-empty. In semantic/hybrid mode the
    semantic channels come from detections, so a missing detector means an all-zero board read."""
    return obs_mode(cfg) != "rgb"


# --- the shared rasterizer ----------------------------------------------------------------------
class Rasterizer:
    """Entities -> `[oh, ow, N_CHANNELS]` uint8. The ONE painting path both worlds go through.

    An entity is `(channel, x, y, value)` with x/y normalized frame coordinates and value in [0, 1];
    the footprint is looked up from the KB by base card, so callers never choose their own geometry.
    Output is uint8 0-255 so the existing `torch.from_numpy(obs).float() / 255.0` in train_sim /
    train_rl / play recovers the intended [0, 1] with no change to the training code.
    """

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        sem = cfg.get("observation", "semantic", default={}) or {}
        bx = cfg.get("action", "arena_box", default=None) or \
            cfg.get("env", "arena_region", default=[0.03, 0.10, 0.97, 0.86])
        self.bx0, self.by0, self.bx1, self.by1 = (float(bx[0]), float(bx[1]), float(bx[2]), float(bx[3]))
        self.tile_w = (self.bx1 - self.bx0) / _TILES_W
        self.tile_h = (self.by1 - self.by0) / _TILES_H
        # footprint radii in TILES, by coarse KB role (a Skeleton is not a Golem is not an X-Bow)
        self.r_troop = float(sem.get("troop_radius_tiles", 1.0))
        self.r_swarm = float(sem.get("swarm_radius_tiles", 0.6))
        self.r_tank = float(sem.get("tank_radius_tiles", 1.6))
        self.r_building = float(sem.get("building_radius_tiles", 1.5))
        self.r_princess = float(sem.get("princess_tower_radius_tiles", 3.0))
        self.r_king = float(sem.get("king_tower_radius_tiles", 4.0))
        # mass normaliser: hitpoints x count / this, clipped to [floor, 1]. 3000 ~ a Golem saturates,
        # a Musketeer reads ~0.2, Skeletons ~0.08 -- so the channel encodes "how much is there".
        self.mass_norm = float(sem.get("mass_norm", 3000.0))
        self.mass_floor = float(sem.get("mass_floor", 0.05))   # any present unit must be visible
        self.default_hp = float(sem.get("default_hitpoints", 300.0))  # KB gap -> same fallback build_spec uses
        self._kernels: dict = {}
        self._geom: dict = {}      # base card -> (channel_troop_or_building, rx, ry, mass)

    # -- KB-derived, world-independent geometry ---------------------------------------------------
    def _profile_geom(self, base: str) -> Tuple[bool, float, float, float]:
        """`(is_building, rx, ry, mass)` for a base card, cached. Everything here comes from the KB, so
        the sim and the live detector resolve a given card to exactly the same stamp."""
        hit = self._geom.get(base)
        if hit is not None:
            return hit
        prof = card_threat.profile(self.db, base)
        c = self.db.get(base) or {}
        building = bool(prof.building or prof.siege)
        if building:
            r = self.r_building
        elif prof.swarm:
            r = self.r_swarm
        elif prof.tank:
            r = self.r_tank
        else:
            r = self.r_troop
        hp = float(c.get("hitpoints") or self.default_hp)
        count = max(1, int(c.get("count") or 1))
        mass = float(np.clip(hp * count / self.mass_norm, self.mass_floor, 1.0))
        out = (building, r * self.tile_w, r * self.tile_h, mass)
        self._geom[base] = out
        return out

    def unit_entity(self, base: str, mine: bool, x: float, y: float):
        """A troop/building detection or sim unit -> `(entity, (rx, ry))`, or None for a spell (not
        rastered). The single place team + KB role become a channel AND a footprint, so both worlds
        agree by construction. The radius is returned alongside rather than folded into the entity so
        `render` handles units and towers through one code path."""
        prof = card_threat.profile(self.db, base)
        if prof.spell:
            return None
        building, rx, ry, mass = self._profile_geom(base)
        if building:
            ch = CH_MY_BUILDING if mine else CH_ENEMY_BUILDING
        else:
            ch = CH_MY_TROOP if mine else CH_ENEMY_TROOP
        return ((ch, x, y, mass), (rx, ry))

    def tower_entity(self, mine: bool, x: float, y: float, hp_frac: float, king: bool = False):
        """A crown tower -> `(entity, (rx, ry))` valued by REMAINING HP FRACTION -- the one quantity both
        the engine and the live HP tracker genuinely observe. A dead tower is simply not passed in.
        Tower footprints are fixed (a king is bigger than a princess) rather than KB-derived."""
        ch = CH_MY_TOWER if mine else CH_ENEMY_TOWER
        r = self.r_king if king else self.r_princess
        return ((ch, x, y, float(np.clip(hp_frac, 0.0, 1.0))), (r * self.tile_w, r * self.tile_h))

    # -- painting -------------------------------------------------------------------------------
    def _kernel(self, rx_px: int, ry_px: int) -> np.ndarray:
        """Filled-ellipse mask of half-extents (rx_px, ry_px), cached. Pure numpy: the sim steps this
        thousands of times per second across K envs, and pulling cv2 into the headless engine loop for
        one ellipse per unit would cost more than it buys."""
        key = (rx_px, ry_px)
        k = self._kernels.get(key)
        if k is None:
            yy, xx = np.ogrid[-ry_px:ry_px + 1, -rx_px:rx_px + 1]
            k = ((xx / max(rx_px, 1)) ** 2 + (yy / max(ry_px, 1)) ** 2) <= 1.0
            self._kernels[key] = k
        return k

    def render(self, entities: Sequence[Tuple[int, float, float, float]], oh: int, ow: int,
               radii: Sequence[Tuple[float, float]]) -> np.ndarray:
        """Rasterize entities into `[oh, ow, N_CHANNELS]` uint8. Overlaps take the MAX (a blob is 'the
        heaviest thing here', not a sum -- summing would make a clumped swarm outweigh a Golem).

        `radii` is the parallel per-entity footprint list produced by `unit_entity` / `tower_entity`;
        a None entry falls back to one board tile."""
        canvas = np.zeros((N_CHANNELS, int(oh), int(ow)), np.float32)
        for i, (ch, x, y, value) in enumerate(entities):
            if value <= 0.0:
                continue
            r = radii[i] if i < len(radii) else None
            rx_n, ry_n = r if r is not None else (self.tile_w, self.tile_h)
            cx, cy = int(x * ow), int(y * oh)
            rx_px = max(0, int(round(rx_n * ow)))
            ry_px = max(0, int(round(ry_n * oh)))
            k = self._kernel(rx_px, ry_px)
            # clip the stamp to the canvas (units near the edge / off-board detections)
            x0, x1 = cx - rx_px, cx + rx_px + 1
            y0, y1 = cy - ry_px, cy + ry_px + 1
            kx0, ky0 = max(0, -x0), max(0, -y0)
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(int(ow), x1), min(int(oh), y1)
            if x1 <= x0 or y1 <= y0:
                continue
            sub = k[ky0:ky0 + (y1 - y0), kx0:kx0 + (x1 - x0)]
            tgt = canvas[ch, y0:y1, x0:x1]
            np.maximum(tgt, sub * float(value), out=tgt)
        return np.clip(canvas * 255.0, 0, 255).astype(np.uint8).transpose(1, 2, 0)


def render_entities(rz: Rasterizer, ents_and_radii, oh: int, ow: int) -> np.ndarray:
    """Convenience: split a `[(entity, radius_or_None), ...]` list and rasterize it."""
    if not ents_and_radii:
        return np.zeros((int(oh), int(ow), N_CHANNELS), np.uint8)
    ents = [e for e, _r in ents_and_radii]
    radii = [r for _e, r in ents_and_radii]
    return rz.render(ents, oh, ow, radii)


# --- SIM side: entities from engine ground truth ---------------------------------------------------
class SimRaster:
    """Engine ground truth -> semantic entities, from ``team``'s point of view (mirrored for team 1 via
    `view.to_local`, exactly like the RGB render, so the self-play opponent sees itself as team 0 does).

    Ground-truth units are filtered through the LIVE DETECTOR MODEL (whitelist / recall / precision) so
    the sim raster has live-like sparsity -- see the module docstring. The filter's rng is PRIVATE: it
    never consumes `env.rng`, so seeded eval deck streams are unchanged by this module.
    """

    def __init__(self, cfg, db, rng):
        sem = cfg.get("observation", "semantic", default={}) or {}
        self.rz = Rasterizer(cfg, db)
        self.realism = bool(sem.get("detector_realism", True))
        self.whitelist = raster_whitelist(cfg, db)
        self.recall = float(cfg.get("observation", "sim_detector_recall", default=1.0))
        self.precision = float(cfg.get("observation", "sim_detector_precision", default=1.0))
        self.recall_by_card = dict(cfg.get("observation", "sim_detector_recall_by_card", default=None) or {})
        self.rng = rng

    def _seen(self, base: str) -> Optional[str]:
        """Apply the detector model to one ground-truth unit: None = the detector would have MISSED it,
        otherwise the name it would have REPORTED (possibly a misclassification)."""
        if not self.realism:
            return base
        if self.whitelist and base not in self.whitelist:
            return None                                   # the detector cannot name this card at all
        r = self.recall_by_card.get(base, self.recall)
        if r < 1.0 and self.rng.random() > r:
            return None                                   # missed detection
        if self.precision < 1.0 and self.whitelist and self.rng.random() > self.precision:
            return self.rng.choice(sorted(self.whitelist))  # misclassified as another whitelisted card
        return base

    def render(self, engine, oh: int, ow: int, team: int = 0) -> np.ndarray:
        from .sim import view

        out = []
        for u in engine.units:
            if u.hp <= 0:
                continue
            base = getattr(u.spec, "base", None)
            if base is None:
                continue
            name = self._seen(base)
            if name is None:
                continue
            lx, ly = view.to_local(u.x, u.y, team)
            ent = self.rz.unit_entity(name, mine=(u.team == team), x=lx, y=ly)
            if ent is not None:
                out.append(ent)
        # TOWERS: always visible to both worlds (no detector needed), valued by remaining HP fraction.
        for t in (team, 1 - team):
            for tw in engine.towers[t]:
                if not tw.alive or tw.max_hp <= 0:
                    continue
                lx, ly = view.to_local(tw.x, tw.y, team)
                out.append(self.rz.tower_entity(mine=(t == team), x=lx, y=ly,
                                                hp_frac=tw.hp / tw.max_hp, king=bool(tw.king)))
        return render_entities(self.rz, out, oh, ow)


# --- LIVE side: entities from the detector's tagged read -------------------------------------------
class LiveRaster:
    """Detector output + the live tower trackers -> the SAME semantic entities the sim produces.

    Detections are used for IDENTITY and POSITION only: the class name resolves footprint + mass through
    the KB (never the detector's own box size, which varies with sprite animation and would not exist in
    the sim), and `d.gy` is the shadow-corrected GROUND position so a flyer rasters on its true tile.
    """

    def __init__(self, cfg, db):
        self.rz = Rasterizer(cfg, db)
        self.whitelist = raster_whitelist(cfg, db)
        from .reward import _anchors
        mine, enemy, _thr = _anchors(cfg)
        self.my_anchors = [tuple(a) for a in mine[:3]]
        self.enemy_anchors = [tuple(a) for a in enemy[:3]]

    def entities(self, dets, my_hp: Sequence[float], my_full: float, my_alive: Sequence[bool],
                 enemy_hp: Sequence[float], enemy_full: float, enemy_alive: Sequence[bool]):
        """Build the entity list. `dets` = TAGGED detections (team 'mine'/'enemy'; 'unknown' is dropped
        rather than guessed -- a mis-teamed unit is worse than an absent one). Tower HP comes from the
        OCR tracker; a tower with no reading falls back to full, matching the tracker's own default."""
        out = []
        for d in dets:
            if d.team not in ("mine", "enemy"):
                continue
            base = d.base
            if self.whitelist and base not in self.whitelist:
                continue
            ent = self.rz.unit_entity(base, mine=(d.team == "mine"), x=float(d.cx), y=float(d.gy))
            if ent is not None:
                out.append(ent)
        for mine_side, anchors, hps, full, alives in (
                (True, self.my_anchors, my_hp, my_full, my_alive),
                (False, self.enemy_anchors, enemy_hp, enemy_full, enemy_alive)):
            for i, (ax, ay) in enumerate(anchors):
                if i < len(alives) and not alives[i]:
                    continue
                king = i == 2                     # anchors are [L princess, R princess, KING]
                hp = float(hps[i]) if i < len(hps) else float(full)
                frac = hp / full if full > 0 else 1.0
                out.append(self.rz.tower_entity(mine=mine_side, x=ax, y=ay, hp_frac=frac, king=king))
        return out

    def render(self, dets, my_hp, my_full, my_alive, enemy_hp, enemy_full, enemy_alive,
               oh: int, ow: int) -> np.ndarray:
        return render_entities(self.rz, self.entities(dets, my_hp, my_full, my_alive,
                                                      enemy_hp, enemy_full, enemy_alive), oh, ow)


# --- composition + preview -------------------------------------------------------------------------
def compose(mode: str, rgb: Optional[np.ndarray], sem: Optional[np.ndarray]) -> np.ndarray:
    """Assemble the observation tensor for `mode`. Hybrid puts RGB FIRST so channels 0-2 keep the
    meaning they had before this change -- an RGB-trained trunk's first three input planes still line up,
    which is what makes the A/B a controlled comparison."""
    if mode == "rgb":
        return rgb
    if mode == "semantic":
        return sem
    return np.concatenate([rgb, sem], axis=2)


def channels_to_bgr(channels: np.ndarray) -> np.ndarray:
    """Composite the semantic channels into one BGR image for a human preview."""
    oh, ow = channels.shape[:2]
    out = np.zeros((oh, ow, 3), np.float32)
    for k, col in _VIZ.items():
        if k >= channels.shape[2]:
            continue
        out = np.maximum(out, (channels[:, :, k].astype(np.float32) / 255.0)[:, :, None]
                         * np.array(col, np.float32))
    return out.astype(np.uint8)
