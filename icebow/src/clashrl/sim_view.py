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

from .sim.engine import _BRIDGES, _RIVER, _ROCKET_RADIUS, _TORNADO_RADIUS
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

_HUD_TOP = 54
_HUD_BOT = 58
_ASPECT = 0.56          # board width / height (CR portrait arena is ~18 x 32 tiles)


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

    ``acts`` (an ActionSpace) overlays the PLACEMENT GRID -- the discrete cells the policy actually
    chooses among, drawn over `action.arena_box`, with the deploy line (`action.deploy_top`) marked.
    Placement in this engine is otherwise CONTINUOUS: the grid is what discretises the agent, but the
    scripted opponents deploy at raw continuous coordinates, and nothing snaps a deploy to a tile.
    """
    W = int(width)
    BH = int(W / _ASPECT)
    H = BH + _HUD_TOP + _HUD_BOT
    img = np.zeros((H, W, 3), np.uint8)

    def px(nx: float, ny: float):
        return int(nx * W), _HUD_TOP + int(ny * BH)

    # --- board -------------------------------------------------------------------------------
    cv2.rectangle(img, (0, _HUD_TOP), (W, _HUD_TOP + BH), _GRASS, -1)
    ry0, ry1 = px(0, _RIVER - 0.012)[1], px(0, _RIVER + 0.012)[1]
    cv2.rectangle(img, (0, ry0), (W, ry1), _RIVER_C, -1)
    for bx in _BRIDGES:                                   # the two crossings
        x0, x1 = int((bx - 0.045) * W), int((bx + 0.045) * W)
        cv2.rectangle(img, (x0, ry0), (x1, ry1), _BRIDGE, -1)

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
        cv2.putText(img, f"grid {acts.gw}x{acts.gh}", (px(bx0, by1)[0] + 3, px(bx0, by1)[1] - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _GRID_EDGE, 1)
    cv2.line(img, (int(0.5 * W), _HUD_TOP), (int(0.5 * W), _HUD_TOP + BH), _LINE, 1)

    # --- vortices (under everything: they are a ground effect) ---------------------------------
    # NB radii are drawn as ELLIPSES, not circles. The engine measures distance isotropically in
    # NORMALIZED space (hypot on x,y in 0..1), but this canvas is ~0.56 as wide as it is tall, so a
    # circle here would claim a pull/blast area the engine never uses. The ellipse is what the engine
    # actually tests against. (That the engine's normalized space is isotropic AT ALL while the real
    # arena is 18x32 tiles is a separate fidelity question -- see the note in the docstring.)
    for v in getattr(eng, "vortices", []):
        c = px(v.x, v.y)
        cv2.ellipse(img, c, (int(_TORNADO_RADIUS * W), int(_TORNADO_RADIUS * BH)),
                    0, 0, 360, _VORTEX, 1)
        cv2.circle(img, c, 3, _VORTEX, -1)
        cv2.putText(img, f"pull {v.left:.1f}s", (c[0] - 22, c[1] - int(_TORNADO_RADIUS * BH) - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _VORTEX, 1)

    # --- towers ------------------------------------------------------------------------------
    for team in (1, 0):
        for tw in eng.towers[team]:
            hw, hh = (0.055, 0.040) if tw.king else (0.040, 0.033)
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
    for s in getattr(eng, "spells", []):
        c = px(s.x, s.y)
        cv2.drawMarker(img, c, _SPELL, cv2.MARKER_CROSS, 13, 1)
        if "rocket" in s.spec.key:                        # show the blast it WILL make
            cv2.ellipse(img, c, (int(_ROCKET_RADIUS * W), int(_ROCKET_RADIUS * BH)),
                        0, 0, 360, _SPELL, 1)
        cv2.putText(img, f"{_short(s.spec.key)} {s.t:.1f}s", (c[0] + 8, c[1] - 6),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _SPELL, 1)

    # --- units -------------------------------------------------------------------------------
    for u in eng.units:
        if u.hp <= 0:
            continue
        c = px(u.x, u.y)
        r = max(4, int(u.spec.radius * W * 1.7))
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
        cv2.putText(img, _short(u.spec.key), (c[0] - r - 2, c[1] + r + 10),
                    cv2.FONT_HERSHEY_PLAIN, 0.7, _TXT, 1)

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
    oh, ow, _ = env.obs_shape
    net = PolicyNet(3, int(ck["n_cards"]), int(ck["n_cells"]), int(ck["threat_dim"]))
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
            z = net.features_vec(x,
                                 torch.from_numpy(e.hand_vec).unsqueeze(0),
                                 torch.from_numpy(e.next_vec).unsqueeze(0),
                                 torch.from_numpy(e.elixir_vec).unsqueeze(0),
                                 torch.from_numpy(e.threat_vec).unsqueeze(0))
            cq, ceq, gq = net.card_head(z)[0], net.cell_head(z)[0], gate(z)[0]
            ok = torch.tensor([bool(v >= 0.5 and e.specs[i].elixir <= e.eng.elixir[0])
                               for i, v in enumerate(e.hand_vec)])
            if not bool(ok.any()):
                return (0, 0, 0)
            card = int(cq.masked_fill(~ok, -1e9).argmax())
            cm = torch.tensor(e.actions.deployable_mask(card in e.anywhere_ids))
            ceqm = ceq.masked_fill(~cm, -1e9)
            cell = int(ceqm.argmax())
            play = (gq[1] > gq[0]) if is_ppo else (gq[1] + cq.max() + ceqm.max() > gq[0])
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
            sink(env, f"match {_m}/{matches}")
            steps = 0
            while not state["quit"]:
                out_t = env.step(agent(env))
                steps += 1
                if bool(out_t[2]):
                    break
            for _ in range(int(fps)):       # hold the final frame ~1s so the result is readable
                if state["quit"]:
                    break
                sink(env, f"match {_m}/{matches}")
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
