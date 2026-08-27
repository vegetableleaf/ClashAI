"""Visual debugger for the headless sim (`run.py sim-view`).

WHY THIS EXISTS
---------------
The sim is a stat-driven engine with no picture, so every mechanics bug has to be found by reading
code or by inferring it from a win-rate. That has already cost real time: the ROCKET resolved as a
Log-style rolling CORRIDOR for weeks (a `knockback` flag matched both), the tornado had no pull at
all until it was added, and the Miner's king-dig was "optimal" because troops hit towers for full
damage. Every one of those is obvious in one second of video and nearly invisible in a reward curve.

This renders the ENGINE STATE -- not the policy's 64x96 observation canvas -- at physics resolution
(`sim.sub_dt`, default 0.1 s), so you watch what the simulation actually does between decisions:
projectile flight, deploy delays, aggro switches and leashes, the tornado's pull, splash radii,
shields, stuns, tower target acquisition, elixir flow.

It is a DEBUGGER, not a training input. Nothing here feeds the policy; `view.render_obs` remains the
only thing the CNN ever sees.

WHAT I9 ADDED, AND WHY IT WAS NOT COSMETIC. The owner's "the electro dragon chain doesn't work"
report was partly a DRAWING bug: the chain was landing and the picture showed nothing. MEASURED --
an Electro Dragon chaining into six Barbarians for 12 s produced **zero frames** in which a
`<base>_chain` projectile was alive, because a chain hop is created and consumed inside one
`advance(dt)` call and never survives a frame boundary. Two engine records fixed that
(`arc_events`, `ability_events`, both in the `splash_events` idiom), and this file now draws:

  * CHAIN ARCS, one line per hop, dimmer for a late (reduced-damage, no-stun) bounce;
  * ABILITY ACTIVATIONS -- a flash at the press point, labelled with the `ability_kind`;
  * CASTS IN FLIGHT (`_ability_pending`) -- the ruling-7 refund window, drawn as a ring with the
    countdown, so a champion killed mid-cast is visible as a champion killed mid-cast;
  * RUNNING ABILITIES on the body (`ability_active_s`), plus stealth, airborne, taunt, souls and
    dash-chain state;
  * LINGERING ZONES (`eng.zones`) -- Poison, Void, Graveyard and the Heal Spirit's field, none of
    which were drawn at all, so a Poison was an invisible area doing invisible damage;
  * the GOBLINSTEIN LINK capsule, the Hero Goblins' BANNER and the Goblinstein ANTENNA, which are
    engine state with no body to hang a marker on.

OPEN FIDELITY QUESTION this view makes visible: the engine stores positions as x,y in 0..1 and
measures range with `hypot` -- i.e. it treats the arena as SQUARE -- while the real CR board is
~18 tiles wide by ~32 tall. So one normalized unit is a different number of tiles on each axis, and
every range (sight, reach, splash, pull) is effectively shorter across the lanes than up the board.
Radii are drawn here as ellipses so the picture matches what the engine really tests; whether the
engine itself should be anisotropic is worth measuring against real footage before changing.

    run.py sim-view                          # one match, scripted opponent, random legal agent
    run.py sim-view --policy data/policy_sim_ppo_best.pt --matches 3
    run.py sim-view --out data/sim_debug.mp4 --fps 20 --no-window

Keys while the window is focused: SPACE pause/resume, . step one frame while paused, Q/ESC quit.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from .sim.engine import (_LOG_BACK_SLOP, _RIVER, _ROCKET_RADIUS, _TILES_X, _TILES_Y,
                         _TORNADO_RADIUS)
from .sim.env import SimMatchEnv

WINDOW = "clashrl sim-view"

# BGR
_GRASS = (38, 96, 44)
_RIVER_C = (138, 104, 48)
_BRIDGE = (62, 108, 148)
_LINE = (90, 140, 95)
_TEAM = {0: (235, 132, 72), 1: (72, 72, 235)}      # 0 = you (blue), 1 = enemy (red)
_DEAD = (90, 90, 90)
_HP_OK = (90, 220, 90)
_HP_LOW = (60, 60, 235)
_TXT = (235, 235, 235)
_DIM = (150, 150, 150)
_VORTEX = (230, 200, 90)
_SPELL = (90, 210, 245)
_SHIELD = (240, 240, 240)
_STUN = (60, 220, 240)
_SLOW = (240, 200, 120)
_GRID = (58, 118, 64)          # faint cell lines
_GRID_EDGE = (80, 150, 88)     # arena_box border + the deploy line
_PLAYABLE = (60, 170, 235)     # the ACTUALLY-placeable area's border (river-ledge notches)
_TILE_G = (46, 104, 52)        # the board's REAL 18x32 tile lattice (under the action grid)
# I9 additions. BGR, like everything above -- (B, G, R), not (R, G, B).
_ARC = (70, 230, 255)          # chain hop, full damage + stun: bright amber
_ARC_LATE = (60, 150, 175)     # ...and a LATE bounce: reduced damage, no stun (ruling 12), dull
_ABIL = (255, 120, 255)        # ability activation / running ability: magenta, unused elsewhere
_ABIL_CAST = (200, 90, 200)    # ...still in its activation delay (the ruling-7 refund window)
_ZONE = (170, 90, 220)         # lingering damage field (Poison / Void / Graveyard)
_ZONE_HEAL = (120, 240, 160)   # ...and a HEALING one (Heal Spirit)
_LINK = (60, 200, 255)         # Goblinstein's electric link, and its antenna
_RAGE = (200, 0, 200)          # a rage zone; DIM while it is still arming (see below)
_RAGE_ARM = (110, 0, 110)

_HUD_TOP = 54
_HUD_BOT = 58
_ASPECT = _TILES_X / _TILES_Y   # the board's true aspect, so N tiles reads the same on both axes


def _short(key: str) -> str:
    """Compact a card key for an on-unit label: royal_recruits -> r.recruits."""
    parts = key.split("_")
    if len(parts) == 1:
        return parts[0][:9]
    return (parts[0][0] + "." + parts[-1])[:11]


def _hp_bar(img, cx: int, top: int, w: int, frac: float, h: int = 3) -> None:
    frac = max(0.0, min(1.0, frac))
    x0, x1 = cx - w // 2, cx + w // 2
    cv2.rectangle(img, (x0, top), (x1, top + h), (35, 35, 35), -1)
    if frac > 0:
        col = _HP_OK if frac > 0.35 else _HP_LOW
        cv2.rectangle(img, (x0, top), (x0 + int((x1 - x0) * frac), top + h), col, -1)


def render_frame(eng, width: int = 460, note: str = "", acts=None) -> np.ndarray:
    """Draw the engine's CURRENT state. Team 0 (you) is at the BOTTOM, matching the live screen.

    The canvas is the board's true 18:32 aspect, so a range that is N tiles in the engine is N tiles
    on both axes here. ``acts`` (an ActionSpace) overlays the PLACEMENT GRID -- the discrete cells the
    policy chooses among -- on top of the faint TILE grid; when `action.grid` is 18x32 the two
    coincide, when it is 18x24 each action cell is one tile wide and 1.33 tiles tall.
    """
    W = int(width)
    BH = int(W / _ASPECT)
    H = BH + _HUD_TOP + _HUD_BOT
    img = np.zeros((H, W, 3), np.uint8)

    def px(nx: float, ny: float):
        return int(nx * W), _HUD_TOP + int(ny * BH)

    def rad_px(tiles: float):
        """A radius in TILES -> (x, y) pixel semi-axes (the two axes have different tile scales)."""
        return int(tiles / _TILES_X * W), int(tiles / _TILES_Y * BH)

    # --- board -------------------------------------------------------------------------------
    cv2.rectangle(img, (0, _HUD_TOP), (W, _HUD_TOP + BH), _GRASS, -1)
    half = 0.5 / _TILES_Y                                 # the river is one tile deep
    ry0, ry1 = px(0, _RIVER - half)[1], px(0, _RIVER + half)[1]
    cv2.rectangle(img, (0, ry0), (W, ry1), _RIVER_C, -1)
    bw = 1.5 / _TILES_X                                   # bridges are ~3 tiles wide
    for bx in eng.lanes:                                  # the two crossings (tile-derived)
        cv2.rectangle(img, (int((bx - bw) * W), ry0), (int((bx + bw) * W), ry1), _BRIDGE, -1)

    # --- tile grid (the board's REAL lattice) --------------------------------------------------
    for tx in range(int(_TILES_X) + 1):
        x = int(tx / _TILES_X * W)
        cv2.line(img, (x, _HUD_TOP), (x, _HUD_TOP + BH), _TILE_G, 1)
    for ty in range(int(_TILES_Y) + 1):
        y = _HUD_TOP + int(ty / _TILES_Y * BH)
        cv2.line(img, (0, y), (W, y), _TILE_G, 1)

    # --- placement grid ------------------------------------------------------------------------
    if acts is not None:
        bx0, by0, bx1, by1 = acts.bx0, acts.by0, acts.bx1, acts.by1
        for gx in range(int(acts.gw) + 1):
            x = bx0 + (bx1 - bx0) * gx / acts.gw
            cv2.line(img, px(x, by0), px(x, by1), _GRID, 1)
        for gy in range(int(acts.gh) + 1):
            y = by0 + (by1 - by0) * gy / acts.gh
            cv2.line(img, px(bx0, y), px(bx1, y), _GRID, 1)
        cv2.rectangle(img, px(bx0, by0), px(bx1, by1), _GRID_EDGE, 1)
        dy = float(acts.deploy_top)                       # troops can't be placed above this
        cv2.line(img, px(bx0, dy), px(bx1, dy), _GRID_EDGE, 1)
        cv2.putText(img, f"grid {acts.gw}x{acts.gh} / tiles {int(_TILES_X)}x{int(_TILES_Y)}",
                    (px(bx0, by1)[0] + 3, px(bx0, by1)[1] - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _GRID_EDGE, 1)
    # --- PLAYABLE-AREA border (2026-08-14, user-verified shape) --------------------------------
    # The real CR field is NOT a rectangle: the outermost SINGLE column beside the water is a
    # decorative ledge, and each back row is playable only in the 1x6 strip centered behind
    # its king (actions.unplayable / engine deploy snap). The full rectangle above IS the
    # board and stays; this second border traces where cards can actually be placed.
    from .actions import (KING_STRIP_X0 as _KX0, KING_STRIP_X1 as _KX1, KING_Y0 as _KY,
                          LEDGE_X_FRAC as _LX, LEDGE_Y0 as _LY0, LEDGE_Y1 as _LY1)
    _pb = [(0, _KY), (_KX0, _KY), (_KX0, 0), (_KX1, 0), (_KX1, _KY), (1, _KY),
           (1, _LY0), (1 - _LX, _LY0), (1 - _LX, _LY1), (1, _LY1),
           (1, 1 - _KY), (_KX1, 1 - _KY), (_KX1, 1), (_KX0, 1), (_KX0, 1 - _KY), (0, 1 - _KY),
           (0, _LY1), (_LX, _LY1), (_LX, _LY0), (0, _LY0)]
    cv2.polylines(img, [np.array([px(a, b) for a, b in _pb], np.int32)], True, _PLAYABLE, 1)
    cv2.line(img, (int(0.5 * W), _HUD_TOP), (int(0.5 * W), _HUD_TOP + BH), _LINE, 1)

    # --- vortices (under everything: they are a ground effect) ---------------------------------
    for v in getattr(eng, "vortices", []):
        c = px(v.x, v.y)
        semi = rad_px(_TORNADO_RADIUS)
        cv2.ellipse(img, c, semi, 0, 0, 360, _VORTEX, 1)
        cv2.circle(img, c, 3, _VORTEX, -1)
        cv2.putText(img, f"pull {v.left:.1f}s", (c[0] - 22, c[1] - semi[1] - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _VORTEX, 1)

    # --- lingering ZONES (Poison / Void / Graveyard / the Heal Spirit's field) -------------------
    # These were not drawn at all, which made a whole class of card invisible: a Poison is an
    # 8-second area doing damage nothing on screen accounted for, and after I9 a Heal Spirit's
    # field is an area doing the opposite. Drawn under the bodies, because they are ground effects.
    for z in getattr(eng, "zones", []):
        heals = getattr(z.spec, "heal_amount", 0.0) > 0.0
        col = _ZONE_HEAL if heals else _ZONE
        c = px(z.x, z.y)
        cv2.ellipse(img, c, rad_px(z.spec.spell_radius), 0, 0, 360, col, 1)
        cv2.putText(img, "%s %.1fs" % ("heal" if heals else _short(z.spec.key), max(0.0, z.left)),
                    (c[0] - 20, c[1] + 4), cv2.FONT_HERSHEY_PLAIN, 0.7, col, 1)

    # --- splash flashes: each splash HIT draws its true AOE circle for ~0.15 s (user request:
    # a brief flash at the moment of attack, not a continuous ring) -------------------------------
    for (sx, sy, sr, st) in getattr(eng, "splash_events", []):
        age = eng.t - st
        if 0.0 <= age <= 0.15:
            c = px(sx, sy)
            cv2.ellipse(img, c, rad_px(sr), 0, 0, 360, (0, 200, 255), 1)

    # --- towers ------------------------------------------------------------------------------
    for team in (1, 0):
        for tw in eng.towers[team]:
            ht = float(getattr(tw, "radius", 1.5))        # real footprint: princess 3x3, king 4x4 tiles
            hw, hh = ht / _TILES_X, ht / _TILES_Y
            x0, y0 = px(tw.x - hw, tw.y - hh)
            x1, y1 = px(tw.x + hw, tw.y + hh)
            if not tw.alive:
                cv2.rectangle(img, (x0, y0), (x1, y1), _DEAD, 1)
                cv2.line(img, (x0, y0), (x1, y1), _DEAD, 1)
                cv2.line(img, (x0, y1), (x1, y0), _DEAD, 1)
                continue
            cv2.rectangle(img, (x0, y0), (x1, y1), _TEAM[team], 2)
            frac = tw.hp / tw.max_hp if tw.max_hp else 0.0
            _hp_bar(img, (x0 + x1) // 2, y0 - 6, x1 - x0, frac)
            cv2.putText(img, f"{int(tw.hp)}", (x0, y1 + 11), cv2.FONT_HERSHEY_PLAIN, 0.75, _TXT, 1)
            tag = getattr(tw, "troop", "") or ("king" if tw.king else "")
            if tw.king and getattr(tw, "active", False):
                tag += " AWAKE"
            if tag:
                cv2.putText(img, tag[:14], (x0, y0 - 9), cv2.FONT_HERSHEY_PLAIN, 0.7,
                            (60, 200, 255) if "AWAKE" in tag else _DIM, 1)

    # --- spells in flight --------------------------------------------------------------------
    # Draw the AREA a pending spell will affect, not just its cast point. A rolling Log is a forward
    # ground CORRIDOR (what `_resolve_roll` actually tests), so without its rectangle it reads as a
    # point blast localized to the cast tile -- the exact confusion this debugger exists to prevent.
    for s in getattr(eng, "spells", []):
        c = px(s.x, s.y)
        if getattr(s.spec, "rolls", False):               # The Log: forward corridor toward the enemy
            fdir = -1.0 if s.team == 0 else 1.0           # forward = up for you (team 0), down for them
            halfw = s.spec.spell_radius                   # corridor half-width (tiles)
            y_front = s.y + fdir * s.spec.roll_len / _TILES_Y     # reaches roll_len tiles ahead...
            y_back = s.y - fdir * _LOG_BACK_SLOP / _TILES_Y       # ...and a little behind the cast tile
            cv2.rectangle(img, px(s.x - halfw / _TILES_X, y_back),
                          px(s.x + halfw / _TILES_X, y_front), _SPELL, 1)
        cv2.drawMarker(img, c, _SPELL, cv2.MARKER_CROSS, 13, 1)
        if "rocket" in s.spec.key:                        # show the blast it WILL make
            cv2.ellipse(img, c, rad_px(_ROCKET_RADIUS), 0, 0, 360, _SPELL, 1)
        cv2.putText(img, f"{_short(s.spec.key)} {s.t:.1f}s", (c[0] + 8, c[1] - 6),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _SPELL, 1)

    # --- rolling spells MID-SWEEP (ruling 21) ------------------------------------------------
    # A roll is no longer instantaneous: `SimEngine.rolls` holds the live `_Roll` objects and the
    # corridor GROWS. Drawing only the pending-spell rectangle above would show the full 9.6 tiles
    # at cast and then nothing at all for the 2.88 s the roll is actually working -- the debugger
    # would say the Log had already finished while it was still halfway up the lane. Two shapes:
    # the SWEPT part (solid, what has been damaged) and the LEADING EDGE (a bar at r.dist).
    for r in getattr(eng, "rolls", []):
        fdir = -1.0 if r.team == 0 else 1.0
        halfw = r.spec.spell_radius
        y_back = r.y - fdir * _LOG_BACK_SLOP / _TILES_Y
        y_edge = r.y + fdir * r.dist / _TILES_Y
        y_full = r.y + fdir * r.spec.roll_len / _TILES_Y
        cv2.rectangle(img, px(r.x - halfw / _TILES_X, y_back),        # what it has SWEPT so far
                      px(r.x + halfw / _TILES_X, y_edge), _SPELL, 1)
        cv2.rectangle(img, px(r.x - halfw / _TILES_X, y_edge),        # what is still to come
                      px(r.x + halfw / _TILES_X, y_full), _DIM, 1)
        cv2.line(img, px(r.x - halfw / _TILES_X, y_edge),             # the leading EDGE itself
                 px(r.x + halfw / _TILES_X, y_edge), _SPELL, 2)
        cv2.putText(img, f"{_short(r.spec.key)} {r.dist:.1f}/{r.spec.roll_len:.1f}t",
                    px(r.x + halfw / _TILES_X, y_edge), cv2.FONT_HERSHEY_PLAIN, 0.7, _SPELL, 1)

    # --- units -------------------------------------------------------------------------------
    for u in eng.units:
        if u.hp <= 0:
            continue
        c = px(u.x, u.y)
        r = max(3, rad_px(u.spec.radius)[0])          # true collision size (tiles), not a fudge factor
        col = _TEAM[u.team]
        if u.deploy_left > 0:                             # still spawning -> cannot act
            cv2.circle(img, c, r, col, 1)
            cv2.putText(img, "..", (c[0] - 5, c[1] + 4), cv2.FONT_HERSHEY_PLAIN, 0.8, col, 1)
        else:
            cv2.circle(img, c, r, col, -1)
            if u.spec.flying:                             # air units get a ring so they read at a glance
                cv2.circle(img, c, r + 3, col, 1)
        if u.shield_left > 0:
            cv2.circle(img, c, r + 2, _SHIELD, 1)
        if u.stun_left > 0:
            cv2.circle(img, c, r + 5, _STUN, 1)
        elif u.slow_left > 0:
            cv2.circle(img, c, r + 5, _SLOW, 1)
        if getattr(u, "attacking", False):
            cv2.drawMarker(img, (c[0], c[1] - r - 7), (60, 220, 255), cv2.MARKER_TRIANGLE_DOWN, 7, 1)
        _hp_bar(img, c[0], c[1] - r - 6, max(12, 2 * r), u.hp / max(1.0, u.spec.hp), 2)
        label = _short(u.spec.key)
        if getattr(u, "cloned", False):
            label += "'"                              # a 1-hp Clone, worth no elixir (I9)
        cv2.putText(img, label, (c[0] - r - 2, c[1] + r + 10),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _TXT, 1)
        # --- ABILITY STATE ON THE BODY (I9). An I7/I8 ability leaves no mark of its own: the
        # handler fires, timers run, and the picture is identical to a body doing nothing. Every
        # flag below is engine state the handlers actually read, so what is drawn is what runs.
        tags = []
        if getattr(u, "ability_active_s", 0.0) > 0.0:
            tags.append("%s %.1fs" % (u.spec.ability_kind or "abil", u.ability_active_s))
        if getattr(u, "invis_left", 0.0) > 0.0:
            tags.append("cloak %.1f" % u.invis_left)   # Archer Queen / Boss Bandit: untargetable
        if getattr(u, "flying_left", 0.0) > 0.0:
            tags.append("air %.1f" % u.flying_left)    # thrown by the Hero Giant, or Fiery Flight
        if getattr(u, "dash_left", 0) > 0:
            tags.append("dash x%d" % u.dash_left)      # Golden Knight's chain, dashes remaining
        if getattr(u, "souls", 0) > 0:
            tags.append("souls %d" % u.souls)          # Skeleton King's bank
        if getattr(u, "taunt_ref", None) is not None:
            tags.append("taunted")                     # locked onto the Hero Knight until he dies
        if u.spec.ability_kind and getattr(u, "ability_left", -1) > 0 \
                and not getattr(u, "cloned", False):
            tags.append("[ABIL]")                      # a use is still available on this body
        if tags:
            cv2.putText(img, " ".join(tags)[:26], (c[0] - r - 2, c[1] + r + 20),
                        cv2.FONT_HERSHEY_PLAIN, 0.6, _ABIL, 1)
        if getattr(u, "ability_active_s", 0.0) > 0.0:
            cv2.circle(img, c, r + 8, _ABIL, 1)
        # GOBLINSTEIN'S LINK: the capsule its zone tick actually damages along (conflicts.md I7-11),
        # from the Doctor to the living Monster or, once that is dead, to the antenna it dropped.
        if u.spec.ability_kind == "zone" and getattr(u, "ability_active_s", 0.0) > 0.0:
            far = next((e for e in eng.units
                        if e.team == u.team and e.hp > 0 and e is not u
                        and e.spec.base == u.spec.base and e.spec.building_only), None)
            end = (far.x, far.y) if far is not None \
                else getattr(eng, "_antenna", {}).get(u.team, (u.x, u.y))
            cv2.line(img, c, px(end[0], end[1]), _LINK, 2)

    # --- CHAIN ARCS (I9), OVER the bodies ------------------------------------------------------
    # A chain hop lives for less than one physics frame, so without this record the Electro Dragon
    # family had NOTHING on screen while it worked. Drawn AFTER the units and not before them,
    # which is not a style choice: an arc joins two body CENTRES, so under the bodies it is
    # entirely covered by them -- MEASURED as 0 changed pixels in the first version of this. A
    # late bounce (reduced damage, no stun -- decisions.md ruling 12) is dimmer and carries no
    # stun ring, so the two halves of an evolved chain read apart at a glance.
    for (ax, ay, bx, by, at, ast, kind) in getattr(eng, "arc_events", []):
        age = eng.t - ast
        if not (0.0 <= age <= 0.25):
            continue
        late = kind == "chain_late"
        col = _ARC_LATE if late else _ARC
        p0, p1 = px(ax, ay), px(bx, by)
        cv2.line(img, p0, p1, col, 1)
        cv2.circle(img, p1, 3, col, -1)
        if not late:
            cv2.circle(img, p1, 6, col, 1)          # the stun rides the FULL hits only

    # --- projectiles in flight ---------------------------------------------------------------
    # Shots are real entities with real travel time, so they are drawn: a Mortar shell crawling at
    # 5 tiles/s next to a Musketeer bullet at 16.7 is the clearest way to see that. AREA shots
    # (radius > 0) also show the blast they will make, so you can watch a push walk out of one --
    # and a hollow marker means the shot cannot touch air.
    # RAGE ZONES: the Lumberjack's dropped bottle AND, since I9, the Rage SPELL. Both feed the
    # same list. Drawn DIM while the zone is still arming -- the Rage spell publishes a 0.5 s
    # deploy timer of its own, and a debugger that shows nothing for that half-second is exactly
    # the "it did not work" trap this file exists to close.
    for (zx, zy, zr, zt, t0, t1, boost) in getattr(eng, "rage_zones", []):
        if eng.t >= t1:
            continue
        armed = t0 <= eng.t
        col = _RAGE if armed else _RAGE_ARM
        c = px(zx, zy)
        cv2.ellipse(img, c, rad_px(zr), 0, 0, 360, col, 1)
        cv2.putText(img, "rage +%d%% %.1fs" % (round(boost * 100), max(0.0, t1 - eng.t))
                    if armed else "rage arms %.1fs" % max(0.0, t0 - eng.t),
                    (c[0] - 26, c[1] - 4), cv2.FONT_HERSHEY_PLAIN, 0.7, col, 1)

    # Evo Firecracker's lingering sparks: small orange rings while the patch burns
    for z in getattr(eng, "spark_zones", []):
        cv2.ellipse(img, px(z[0], z[1]), rad_px(z[2]), 0, 0, 360, (0, 140, 255), 1)

    for p in getattr(eng, "projectiles", []):
        c = px(p.x, p.y)
        col = _TEAM[p.team]
        if p.label.endswith("_spark"):                    # Firecracker shrapnel: 5 per volley --
            w = getattr(p, "width", 0.0) or 0.4           # tiny corridor circle, no label spam
            cv2.ellipse(img, c, rad_px(w), 0, 0, 360, col, 1)
            continue
        # ABILITY / MECHANIC SHOTS. Each of these is emitted under its own label precisely so the
        # debugger can tell them from an ordinary attack (`_multi_hit`'s docstring says so), and
        # every one of them is a LINE between two bodies rather than a lobbed shot -- so draw the
        # line. Without it a Monk reflecting a Musketeer bullet and a Musketeer firing one are the
        # same two pixels.
        _kind = next((k for k in ("_chain_late", "_chain", "_reflect", "_snipe", "_javelin",
                                  "_bounce") if p.label.endswith(k)), "")
        if _kind:
            kc = _ARC_LATE if _kind == "_chain_late" else (_ARC if "_chain" in _kind else _ABIL)
            cv2.line(img, c, px(p.tx, p.ty), kc, 1)
            cv2.circle(img, c, 3, kc, -1)
            cv2.putText(img, _kind[1:], (c[0] + 5, c[1] - 4), cv2.FONT_HERSHEY_PLAIN, 0.6, kc, 1)
            continue
        if p.radius > 0:
            cv2.ellipse(img, c, rad_px(p.radius), 0, 0, 360, col, 1)
        if p.pierce:                                      # keeps going past its target
            cv2.drawMarker(img, c, col, cv2.MARKER_TILTED_CROSS, 7, 1)
        elif p.ground_only:                               # cannot hit air
            cv2.circle(img, c, 3, col, 1)
        else:
            cv2.circle(img, c, 2, col, -1)
        cv2.putText(img, _short(p.label.removesuffix("_projectile")) + "*", (c[0] + 5, c[1] - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.6, col, 1)

    # --- ABILITY ACTIVATIONS, CASTS IN FLIGHT, and the two bodiless pieces of engine state -------
    # A press used to leave nothing on screen at all, which is the same invisibility the chain had.
    for (ax, ay, at, ast, kind, base) in getattr(eng, "ability_events", []):
        age = eng.t - ast
        if not (0.0 <= age <= 0.6):
            continue
        c = px(ax, ay)
        rr = 8 + int(age * 34)                        # an expanding ring, so the press reads as an event
        cv2.circle(img, c, rr, _ABIL, 1)
        cv2.putText(img, "%s:%s" % (_short(base), kind or "?"), (c[0] + 10, c[1] - 10),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _ABIL, 1)
    # THE ACTIVATION DELAY (ruling 7): the elixir is spent, the effect has not landed, and a body
    # killed in this window gets it refunded. Drawing it is how "he died mid-cast" becomes visible.
    for rec in getattr(eng, "_ability_pending", []):
        try:
            _tm, body, _cost, left, kind = rec
        except (TypeError, ValueError):                # noqa: PERF203 -- a debugger never crashes
            continue
        if getattr(body, "hp", 0.0) <= 0.0:
            continue
        c = px(body.x, body.y)
        cv2.circle(img, c, 11, _ABIL_CAST, 1)
        cv2.putText(img, "cast %.2fs" % max(0.0, float(left)), (c[0] + 12, c[1] + 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _ABIL_CAST, 1)
    # THE HERO GOBLINS' BANNER: engine state, not a body -- the one ability pressed with every
    # body dead, so there is nothing else on the board to hang it on.
    for team, rec in getattr(eng, "_banner", {}).items():
        try:
            expiry, bx, by, _bs = rec
        except (TypeError, ValueError):                # noqa: PERF203
            continue
        if expiry <= eng.t:
            continue
        c = px(bx, by)
        cv2.drawMarker(img, c, _TEAM[team], cv2.MARKER_DIAMOND, 11, 2)
        cv2.putText(img, "banner %.1fs" % (expiry - eng.t), (c[0] + 9, c[1] - 8),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _TEAM[team], 1)
    # GOBLINSTEIN'S ANTENNA: where the Monster fell. Permanent, untargetable, and the far end of
    # the link once the Monster is gone.
    for team, (ax, ay) in getattr(eng, "_antenna", {}).items():
        cv2.drawMarker(img, px(ax, ay), _LINK, cv2.MARKER_TRIANGLE_UP, 9, 1)

    # --- HUD ---------------------------------------------------------------------------------
    reg, ot = eng.regulation, eng.overtime
    phase = "3x" if eng.t >= reg else ("2x" if eng.t >= reg - 60.0 else "1x")
    clock = f"t={eng.t:5.1f}s / {reg + ot:.0f}   elixir {phase}"
    cv2.putText(img, clock, (8, 20), cv2.FONT_HERSHEY_PLAIN, 1.0, _TXT, 1)
    cv2.putText(img, f"crowns  you {eng.crowns(0)} - {eng.crowns(1)} enemy",
                (8, 38), cv2.FONT_HERSHEY_PLAIN, 1.0, _TXT, 1)
    if note:
        cv2.putText(img, note[:46], (W - 8 - 7 * min(46, len(note)), 20),
                    cv2.FONT_HERSHEY_PLAIN, 1.0, (90, 220, 255), 1)
    if getattr(eng, "done", False):
        cv2.putText(img, str(getattr(eng, "outcome", "done")).upper(), (W // 2 - 40, 38),
                    cv2.FONT_HERSHEY_PLAIN, 1.3, (90, 220, 255), 2)

    for i, team in enumerate((1, 0)):                     # enemy bar on top, yours below
        y = _HUD_TOP + BH + 16 + i * 22
        cv2.putText(img, "enemy" if team else "you", (8, y + 4), cv2.FONT_HERSHEY_PLAIN, 0.9, _DIM, 1)
        e = eng.elixir[team]
        for p in range(10):
            x0 = 56 + p * ((W - 70) // 10)
            x1 = x0 + (W - 70) // 10 - 3
            filled = e >= p + 1
            part = max(0.0, min(1.0, e - p))
            cv2.rectangle(img, (x0, y - 7), (x1, y + 5), (40, 40, 40), -1)
            if part > 0:
                cv2.rectangle(img, (x0, y - 7), (x0 + int((x1 - x0) * part), y + 5),
                              (190, 70, 190) if filled else (120, 50, 120), -1)
        cv2.putText(img, f"{e:4.1f}", (W - 34, y + 4), cv2.FONT_HERSHEY_PLAIN, 0.9, _TXT, 1)
    return img


# --------------------------------------------------------------------------------------------
# agents
# --------------------------------------------------------------------------------------------
def _random_agent(env):
    """A legal random action -- exercises every mechanic without needing a checkpoint."""
    hand = [i for i, v in enumerate(env.hand_vec) if v >= 0.5
            and env.specs[i].elixir <= env.eng.elixir[0]]
    if not hand or env.rng.random() < 0.35:
        return (0, 0, 0)
    card = env.rng.choice(hand)
    cells = [c for c, ok in enumerate(env.actions.deployable_mask(card in env.anywhere_ids)) if ok]
    return (1, card, env.rng.choice(cells))


def _policy_agent(env, path: str):
    """Greedy action from a trained checkpoint, using the SAME masks + gate rule as the trainers."""
    import torch
    from .model import PolicyNet

    ck = torch.load(path, map_location="cpu", weights_only=False)
    is_ppo = ck.get("algo") == "ppo"
    # PPO gates on a PROBABILITY, not a raw logit compare. `gq[1] > gq[0]` is tau=0.5, which the
    # b9ff324 A/B measured as costing 33pp of winrate vs the calibrated 0.25 -- a card play is rare
    # per tick, so a calibrated gate sits far below 0.5. train_sim_ppo.choose_greedy and play.py were
    # both fixed then; this debugger was missed, so it rendered a policy that under-deploys relative
    # to the one that actually plays.
    gate_tau = float(env.cfg.get("sim", "ppo_gate_threshold", default=0.25))
    oh, ow, _ = env.obs_shape
    net = PolicyNet(int(ck.get("in_ch", 3)), int(ck["n_cards"]), int(ck["n_cells"]), int(ck["threat_dim"]))
    net.load_state_dict(ck["model"])
    net.eval()
    gate = torch.nn.Linear(net.embed_dim, 2)
    if "gate" in ck:
        gate.load_state_dict(ck["gate"])
    gate.eval()
    print(f"[sim-view] policy {Path(path).name} (algo={ck.get('algo') or 'ddqn'}, "
          f"n_cells={ck['n_cells']}, threat_dim={ck['threat_dim']})")

    def choose(e):
        with torch.no_grad():
            x = torch.from_numpy(e._last_obs).float().div(255).permute(2, 0, 1).unsqueeze(0)
            z, cq_b, ceq_b = net.forward_parts(x,
                                               torch.from_numpy(e.hand_vec).unsqueeze(0),
                                               torch.from_numpy(e.next_vec).unsqueeze(0),
                                               torch.from_numpy(e.elixir_vec).unsqueeze(0),
                                               torch.from_numpy(e.threat_vec).unsqueeze(0))
            cq, ceq, gq = cq_b[0], ceq_b[0], gate(z)[0]
            ok = torch.tensor([bool(v >= 0.5 and e.specs[i].elixir <= e.eng.elixir[0])
                               for i, v in enumerate(e.hand_vec)])
            if not bool(ok.any()):
                return (0, 0, 0)
            card = int(cq.masked_fill(~ok, -1e9).argmax())
            cm = torch.tensor(e.actions.deployable_mask(card in e.anywhere_ids))
            ceqm = ceq[card].masked_fill(~cm, -1e9)     # PER-CARD placement map
            cell = int(ceqm.argmax())
            play = (float(torch.sigmoid(gq[1] - gq[0])) > gate_tau) if is_ppo \
                else (gq[1] + cq.max() + ceqm.max() > gq[0])
            return (int(bool(play)), card, cell)
    return choose


# --------------------------------------------------------------------------------------------
def sim_view(cfg, matches: int = 1, width: int = 460, fps: int = 20, seed: int = 0,
             policy: "str | None" = None, out: "str | None" = None, window: bool = True,
             grid: bool = True) -> None:
    env = SimMatchEnv(cfg, seed=seed)
    acts = env.actions if grid else None
    agent = _policy_agent(env, policy) if policy else _random_agent
    writer, frames = None, {"n": 0}
    delay = max(1, int(1000 / max(1, fps)))
    state = {"paused": False, "quit": False}

    if out:
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        h = int(width / _ASPECT) + _HUD_TOP + _HUD_BOT
        writer = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, h))
        if not writer.isOpened():
            print(f"[sim-view] WARNING: could not open {p} for writing (codec) -- window only")
            writer = None

    def sink(e, note=""):
        if state["quit"]:
            return
        img = render_frame(e.eng, width, note, acts)
        frames["n"] += 1
        if writer is not None:
            writer.write(img)
        if not window:
            return
        cv2.imshow(WINDOW, img)
        while True:
            k = cv2.waitKey(0 if state["paused"] else delay) & 0xFF
            if k in (ord("q"), 27):
                state["quit"] = True
                return
            if k == ord(" "):
                state["paused"] = not state["paused"]
                if not state["paused"]:
                    return
                continue
            if state["paused"] and k == ord("."):
                return                      # single-step
            if not state["paused"]:
                return

    try:
        for m in range(1, int(matches) + 1):
            if state["quit"]:
                break
            env.reset()
            env.on_tick = lambda e, _m=m: sink(e, f"match {_m}/{matches}")
            sink(env, f"match {m}/{matches}")
            steps = 0
            while not state["quit"]:
                out_t = env.step(agent(env))
                steps += 1
                if bool(out_t[2]):
                    break
            for _ in range(int(fps)):       # hold the final frame ~1s so the result is readable
                if state["quit"]:
                    break
                sink(env, f"match {m}/{matches}")
            print(f"[sim-view] match {m}: {env.eng.outcome} in {env.eng.t:.0f}s "
                  f"({steps} decisions, crowns {env.eng.crowns(0)}-{env.eng.crowns(1)})")
            env.on_tick = None
    finally:
        env.on_tick = None
        if writer is not None:
            writer.release()
            print(f"[sim-view] wrote {out} ({frames['n']} frames @ {fps} fps)")
        if window:
            cv2.destroyAllWindows()
