"""L62: the LIVE ENGINE VISUALIZER -- the sim debugger wired to `EngineMatchEnv` DECISIONS.

`engine_view.py` renders a RECORDING (a replay of a human match driven through the engine).
This module renders a POLICY DRIVING THE ENGINE: one `view_engine_from_frame` + `sim_view.render_frame`
call per RL decision, with the decision itself drawn on top -- the chosen cell, whether the engine
ACCEPTED or REFUSED the play (`result_code`), the ghost opponent's plays, elixir, tick, and the gate's
own probability p(play).

THREE ENTRY POINTS, one renderer:
  1. `LiveEngineView(...).attach(env)` -- a passive wrapper around an EXISTING `EngineMatchEnv`
     instance. It wraps `env._render` (which already receives the raw engine observe on every step)
     and `env.step`; `engine_env.py` is NOT edited and NO extra observe RPC is issued.
  2. CLI `live` -- builds its own `EngineMatchEnv` on --port and drives it with a checkpoint.
  3. CLI `replay` / `export` -- a `ReplayEngineEnv` presenting the SAME surface, fed from a recording
     on disk, so the whole wire (policy -> decision -> view -> mp4/JSON) runs with NO engine contact.
     This is how everything here was tested while both engine slots were busy training.

THE DECISION RULE (read this before changing the default).
`engine_ppo.py` TRAINS by SAMPLING the gate: `g ~ Categorical(softmax([g_wait, g_play]))` (rollout(),
l.302-306). Its `GATE_TAU = 0.25` is explicitly "MONITORING ONLY: nothing in training uses it" (l.58-60).
`run_engine_env.GreedyPolicy` instead plays iff `g_play > g_wait`, i.e. p(play) > 0.5 -- stricter still.
The pro-calibrated gate prior has mean P(play) 0.11 and a largest single-elixir entry of 0.203, both
BELOW 0.25 and far below 0.5, so a correctly calibrated policy under either threshold rule renders as
catatonic while being perfectly healthy. Therefore this module DEFAULTS TO SAMPLING (`--rule sample`),
which is what training does, and always prints p(play) in the HUD so the decision is visible even when
the outcome is "wait". `--rule threshold --gate_tau T` reproduces the threshold rule; `--rule argmax`
reproduces `GreedyPolicy`. Every render says which rule it used, on the frame and in the JSON.

    cd icebow && PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe \
        ../scratchpad/gauntlet/L62/live_view.py replay --rec <recording.json> --focus 1 \
        --out ../scratchpad/gauntlet/ext/engine_view/live_TAG.mp4 --radii
    ... live --port 38031 --matches 1 --policy <ckpt.pt> --radii --out <mp4>      # needs a FREE slot
    ... export --rec <recording.json> --focus 1 --out <payload.json>              # artifact payload
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ICEBOW = ROOT / "icebow"
for _p in (str(ICEBOW / "src"), str(HERE), str(ROOT / "scratchpad" / "gauntlet" / "L61")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_bc_v2 as L61                                            # noqa: E402  (L61 adapter, unmodified)
from engine_view import (NOTE_TAG, PLAY_SHOW_S,                      # noqa: E402  (L62, unmodified)
                         _mirror_fns, _overlay_targets, score_focus_play, view_engine_from_frame)

EXT = ROOT / "scratchpad" / "gauntlet" / "ext"
OUT_DIR = EXT / "engine_view"
TICK_S = 0.05
_NEG = -1e9

# --- colours (BGR, all distinct from every colour sim_view uses on an engine frame) ---------------
_ACCEPT = (120, 255, 140)        # the policy's cell, engine ACCEPTED: green cross
_REFUSE = (60, 60, 255)          # ...REFUSED: red cross + the result code
_SHADOW = (200, 200, 200)        # ...not applied (replay mode): grey
_WAIT = (150, 150, 150)
_GHOST = (0, 90, 255)            # the ghost opponent's plays: orange diamond (same as engine_view)
_FIRE = (150, 100, 255)          # THE SECOND RADIUS RING: reach + target hitbox (see _overlay_fire_rings)
_STRIP_BG = (18, 18, 18)
_STRIP_FG = (225, 225, 225)
_STRIP_DIM = (140, 140, 140)
_STRIP_H = 52                    # my own HUD strip, appended BELOW render_frame's output

RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 22: "native_rejected",
                     1014: "ability_exhausted", 1050: "not_enough_elixir"}

# Tower footprint half-sizes, the sim's own (clashrl.sim.engine._PRINCESS_HALF / _KING_HALF).
_PRINCESS_HALF, _KING_HALF = 1.5, 2.0


def shared_W():
    """ONE SimMatchEnv for the whole process.

    TRAP: `engine_env.py` loads `build_bc_v2` under its OWN module name ("l61_build_bc_v2"), so its
    `V2._W` is a DIFFERENT dict from the `build_bc_v2` this file and `engine_view.py` import. Both are
    the same code, so initialising both would build two `SimMatchEnv` instances (two obs pipelines,
    two card DBs) in one process -- and `EngineMatchEnv.engine_to_cell` would read the OTHER dict's
    `centers` and raise KeyError (measured). Whichever is initialised first is shared into the other."""
    try:
        from engine_env import V2
    except Exception:                       # noqa: BLE001 -- engine_env is optional for pure replay use
        V2 = None
    if V2 is not None and V2._W and not L61._W:
        L61._W.update(V2._W)
    if not L61._W:
        L61.init_worker()
    if V2 is not None and not V2._W:
        V2._W.update(L61._W)
    # The REAL SimEngine, captured before anything swaps `env.eng` for a FakeEngine. EngineView reads
    # lanes / tower_range / king_range / siege_sight / regulation / db off it so radii_of and
    # board_from_engine score identically to the sim feed; a FakeEngine carries none of those.
    L61._W.setdefault("sim_eng0", L61._W["env"].eng)
    if V2 is not None:
        V2._W.setdefault("sim_eng0", L61._W["sim_eng0"])
    return L61._W


# =================================================================================================
# 1. THE TWO RADIUS RINGS  (deliverable 3 -- HANDOFF 5cs.43)
# =================================================================================================
def _dash_ellipse(img, c, semi, col, on=3, period=9):
    """A finer dash than sim_view's sight ring (on=6, period=14) so the two never read as the same ring."""
    import cv2
    for a in range(0, 360, period):
        cv2.ellipse(img, c, semi, 0, a, a + on, col, 1)


def _body_radius(obj):
    """Collision radius in TILES of a thing on the board: a ViewUnit (its spec) or a Tower."""
    spec = getattr(obj, "spec", None)
    if spec is not None:
        return float(getattr(spec, "radius", 0.0) or 0.0)
    return float(getattr(obj, "radius", _PRINCESS_HALF) or _PRINCESS_HALF)


def _enemies_of(eng, team):
    out = [u for u in eng.units if u.hp > 0 and u.team != team and u.spec.kind != "spell"]
    for tm, tws in eng.towers.items():
        if tm == team:
            continue
        out += [tw for tw in tws if tw.alive]
    return out


def fire_ring_radius(eng, obj, team, r_atk, mode="nearest", fixed=0.5):
    """The radius at which the ENGINE actually releases the first shot, for THIS shooter, right now.

    MEASURED (engine_view.md 6 / HANDOFF 5cs.43): the engine tests reach CENTRE-TO-TARGET-EDGE, so the
    fire point is `reach + r_body(target)`, while `geometry_reward.radii_of` returns the bare `reach`
    that sim_view draws and the reward's P-terms score with. Over 5,268 every-tick frames every engine
    first shot landed at or outside the table radius once the target's hitbox was added, and the two
    cleanest cases (X-Bow at a tower 13.04 vs 11.5+1.5; Ice Wizard at a tower 6.94 vs 5.5+1.5) matched
    to within 0.06 tiles.  Returns (r_fire, label) or (None, reason).

    mode 'nearest': r_body of the nearest ENEMY body -- the target it would actually shoot now.
    mode 'fixed'  : reach + `fixed` tiles (0.5 = a typical small troop, 1.5 = a crown tower).
    NOT included: the sim engine's own `_REACH_SLOP` 0.6, which neither the table nor this ring carries.
    """
    if r_atk <= 0.0:
        return None, "no reach"
    if mode == "fixed":
        if float(fixed) <= 0.0:
            return None, "fire ring off"
        return r_atk + float(fixed), "+%.1f" % float(fixed)
    best, bd = None, 1e9
    for e in _enemies_of(eng, team):
        d = math.hypot((e.x - obj.x) * eng.tiles_x, (e.y - obj.y) * eng.tiles_y)
        if d < bd:
            bd, best = d, e
    if best is None:
        return None, "no enemy on board"
    rb = _body_radius(best)
    if rb <= 0.0:
        return None, "target has no hitbox"
    return r_atk + rb, "+%.2f" % rb


def _overlay_fire_rings(img, eng, W, mode="nearest", fixed=0.5):
    """Draw the SECOND ring wherever it differs from the table ring sim_view already drew.

    sim_view._draw_radii draws the bare `radii_of` reach (solid, team colour) + the sight radius
    (dotted, dimmed team colour). This adds, in pink, `reach + target hitbox` -- where the engine fires.
    Both rings are always drawn where they differ; NEITHER is silently preferred (that is the whole
    point: the reward scores the inner one, the engine obeys the outer one)."""
    from clashrl.geometry_reward import radii_of
    from clashrl.sim_view import _ASPECT, _HUD_TOP, _TILES_X, _TILES_Y
    BH = int(W / _ASPECT)

    def px(nx, ny):
        return int(nx * W), _HUD_TOP + int(ny * BH)

    def rad_px(t):
        return int(t / _TILES_X * W), int(t / _TILES_Y * BH)

    kw = dict(siege_sight=eng.siege_sight, tower_range=eng.tower_range, king_range=eng.king_range)
    n = 0
    for team, tws in eng.towers.items():
        for tw in tws:
            if not tw.alive:
                continue
            r_atk, _ = radii_of(tw, **kw)
            rf, _lab = fire_ring_radius(eng, tw, team, r_atk, mode, fixed)
            if rf is None or abs(rf - r_atk) < 1e-6:
                continue
            _dash_ellipse(img, px(tw.x, tw.y), rad_px(rf), _FIRE)
            n += 1
    for u in eng.units:
        if u.hp <= 0 or u.spec.kind == "spell":
            continue
        r_atk, _ = radii_of(u.spec, **kw)
        rf, _lab = fire_ring_radius(eng, u, u.team, r_atk, mode, fixed)
        if rf is None or abs(rf - r_atk) < 1e-6:
            continue
        _dash_ellipse(img, px(u.x, u.y), rad_px(rf), _FIRE)
        n += 1
    return n


# =================================================================================================
# 2. THE DECISION STRIP  (my own HUD, appended under render_frame's canvas -- sim_view untouched)
# =================================================================================================
def _strip(W, lines):
    import cv2
    img = np.full((_STRIP_H, W, 3), _STRIP_BG, np.uint8)
    for i, (txt, col, scale) in enumerate(lines[:3]):
        # FONT_HERSHEY_PLAIN advances ~7.0 px per character per unit scale on this build (measured by
        # eye against the 560 px strip), so clip there rather than letting a line run off the canvas.
        cv2.putText(img, txt[:max(8, int((W - 14) / (7.0 * scale)))], (7, 15 + 16 * i),
                    cv2.FONT_HERSHEY_PLAIN, scale, col, 1)
    return img


def _fmt_decision(d):
    """The one line that makes the decision legible: what the gate said, what was chosen, what happened."""
    if d is None:
        return "no decision this frame", _STRIP_DIM
    p = d.get("p_play")
    head = "p(play) %.3f %s" % (p, d.get("rule", "?")) if p is not None else "p(play) n/a"
    if not d.get("play"):
        why = d.get("wait_reason") or "gate said WAIT"
        return "%s -> WAIT (%s)" % (head, why), _WAIT
    card = d.get("card_key", "?")
    cell = d.get("cell")
    xy = d.get("engine_xy") or (None, None)
    where = "cell %s" % cell if xy[0] is None else "cell %s = (%.1f,%.1f)k" % (cell, xy[0] / 1000.0, xy[1] / 1000.0)
    res = d.get("result")
    if res is None:
        return "%s -> PLAY %s %s | SHADOW (not applied)" % (head, card, where), _SHADOW
    if res.get("accepted"):
        return "%s -> PLAY %s %s | engine ACCEPTED" % (head, card, where), _ACCEPT
    code = int(res.get("result_code", -1))
    nm = RESULT_CODE_NAMES.get(code, "native_%d" % code)
    if res.get("placement_valid") is False:
        nm += "/" + str(res.get("placement_reason"))
    return "%s -> PLAY %s %s | engine REFUSED %d %s" % (head, card, where, code, nm), _REFUSE


# =================================================================================================
# 3. THE LIVE WIRE
# =================================================================================================
class LiveEngineView:
    """Renders an `EngineMatchEnv` AS IT IS STEPPED. One frame per decision.

    Wrapper use (no edit to engine_env.py, no extra engine RPC):

        view = LiveEngineView(out="live.mp4", radii=True)
        view.attach(env)                      # wraps env._render and env.step
        ...  run the trainer / evaluator normally  ...
        view.close()

    The policy tells the view what the gate said via `view.note_gate(meta)` right before `env.step`;
    without it every other overlay still works and the strip prints "p(play) n/a".
    """

    def __init__(self, out=None, *, focus_side=None, radii=True, width=560, fps=6, grid=True,
                 fire_ring="nearest", fire_fixed=0.5, rule="sample", note=NOTE_TAG,
                 max_frames=0, png_dir=None, collect=False, progress=True):
        W = shared_W()
        self.sim_env = W["env"]
        self.spec_of = W["spec_of"]
        self.db = W["db"]
        self.sim_eng0 = W["sim_eng0"]
        self.acts = self.sim_env.actions if grid else None
        self.width, self.fps, self.radii = int(width), float(fps), bool(radii)
        self.fire_ring, self.fire_fixed = fire_ring, float(fire_fixed)
        self.rule, self.note = rule, note
        self.focus_side = focus_side
        self.out = Path(out) if out else None
        self.png_dir = Path(png_dir) if png_dir else None
        self.max_frames = int(max_frames)
        self.progress = progress
        self.collect = collect
        self._writer = None
        self.frames_written = 0
        self.decisions = 0
        self.plays_accepted = self.plays_refused = self.waits = 0
        self.rows = []                       # per-decision records (also the artifact payload source)
        self.marks = []                      # ghost / opponent play marks, decayed like engine_view's
        self._gate = None
        self._last_state = None
        self._last_placement = None
        self._attached = None
        self._orig_render = None
        self._orig_step = None
        self._ghost_seen = 0
        self._t_render = 0.0

    # ------------------------------------------------------------------ wrapper mode
    def attach(self, env):
        """Wrap `env._render` (which already gets the raw observe) and `env.step`. Reversible."""
        if self._attached is not None:
            raise RuntimeError("already attached")
        self._attached = env
        if self.focus_side is None:
            self.focus_side = int(getattr(env, "side", 0))
        # `env._render` / `env.step` are CLASS methods, so restoring means DELETING the instance
        # attribute we shadow them with -- assigning the bound method back would leave the instance
        # permanently patched (and would keep this view alive in a closure).
        self._had = (("_render" in env.__dict__), ("step" in env.__dict__))
        self._orig_render, self._orig_step = env._render, env.step

        def render(state, _o=self._orig_render):
            self._last_state = state              # the RAW engine observe, free of any extra RPC
            return _o(state)

        def step(action, _o=self._orig_step):
            gate = self._gate
            pre = self._last_state                # the observe the policy DECIDED on (pre-step)
            obs, r, done, info = _o(action)
            self.on_decision(env, action, info, gate=gate, state=self._last_state, pre_state=pre)
            self._gate = None
            return obs, r, done, info

        env._render, env.step = render, step
        return self

    def detach(self):
        env = self._attached
        if env is not None:
            had_r, had_s = getattr(self, "_had", (True, True))
            if had_r:
                env._render = self._orig_render
            else:
                env.__dict__.pop("_render", None)
            if had_s:
                env.step = self._orig_step
            else:
                env.__dict__.pop("step", None)
            self._attached = None
        return self

    def note_gate(self, meta):
        """Called by the policy just before env.step with {'p_play', 'rule', 'card_key', 'wait_reason', ...}."""
        self._gate = dict(meta) if meta else None

    # ------------------------------------------------------------------ the render
    def on_reset(self, env, state=None):
        self.focus_side = int(getattr(env, "side", self.focus_side or 0))
        self._last_state = state if state is not None else self._last_state
        self.marks, self._last_placement = [], None
        self._ghost_seen = 0

    def on_decision(self, env, action, info, gate=None, state=None, pre_state=None):
        """ONE decision -> ONE frame. `info` is EngineMatchEnv.step's info dict (carries info['play']).

        `state` is the POST-step observe (what the play did); `pre_state` is the observe the policy
        DECIDED on. The row carries both ticks: `tick` (post) and `obs_tick` (pre), so a viewer can
        show the board exactly as the policy saw it and the effect one step later."""
        if self.max_frames and self.frames_written >= self.max_frames:
            return None
        state = state if state is not None else self._last_state
        if state is None:
            state = env.eng.observe()          # only ever hit if the caller never used attach()
        focus = int(getattr(env, "side", self.focus_side or 0))
        frame = state if ("entities" in state and "towers" in state) else frame_of(state)
        eng = view_engine_from_frame(frame, focus, self.spec_of, full=("projectiles" in frame),
                                     sim_eng=self.sim_eng0)
        eng.feed = "engine_live" if self._attached is not None else eng.feed
        xy, team_of = _mirror_fns(focus)

        play_info = (info or {}).get("play")
        pre_frame = None
        if pre_state is not None:
            pre_frame = pre_state if ("entities" in pre_state and "towers" in pre_state) else frame_of(pre_state)
        d = self._decision_row(env, action, play_info, gate, frame, pre_frame)
        # the focus play, scored by the SAME reward code sim_view uses (P1 band + term readout)
        if d.get("play") and d.get("engine_xy") and self.radii and d.get("accepted") is not False:
            spec = self.spec_of(d["card_key"]) or self.spec_of("__generic__")
            nx, ny = xy(int(d["engine_xy"][0]), int(d["engine_xy"][1]))
            self._last_placement = score_focus_play(eng, spec, nx, ny, eng.t)
            d["scores"] = {k: (round(v, 4) if isinstance(v, float) else v)
                           for k, v in (self._last_placement.get("scores") or {}).items()}
        if self._last_placement is not None and eng.t - self._last_placement["t"] <= PLAY_SHOW_S:
            eng.last_placement = self._last_placement
        self._add_ghost_marks(env, eng, xy)
        if (info or {}).get("outcome"):
            eng.done = True
            eng.outcome = "%s crowns %s" % (info["outcome"], info.get("crowns"))
        img = self._draw(eng, d)
        self.rows.append(d)
        self.decisions += 1
        return img

    def _decision_row(self, env, action, play_info, gate, frame, pre_frame=None):
        play, card_id, cell = (int(action[0]), int(action[1]), int(action[2])) if action else (0, 0, 0)
        g = dict(gate or {})
        el = frame["elixir"]
        pre = pre_frame if pre_frame is not None else frame
        pel = pre["elixir"]
        d = {"tick": int(frame["tick"]), "seconds": round(frame["tick"] * TICK_S, 2),
             "obs_tick": int(pre["tick"]),                       # the frame the policy decided on
             "obs_elixir": [round(float(pel[0] or 0.0), 3), round(float(pel[1] or 0.0), 3)],
             "hand": g.get("hand"), "queue": g.get("queue"),     # the hand / cycle the policy saw
             "p_cell": g.get("p_cell"),
             "play": bool(play), "card_id": card_id if play else None,
             "card_key": g.get("card_key") or (env.deck_keys[card_id] if play else None),
             "cell": cell if play else None,
             "p_play": g.get("p_play"), "rule": g.get("rule", self.rule),
             "wait_reason": g.get("wait_reason"),
             "p_card": g.get("p_card"), "top_cards": g.get("top_cards"),
             "n_playable": g.get("n_playable"),
             "elixir": [round(float(el[0] or 0.0), 3), round(float(el[1] or 0.0), 3)],
             "engine_xy": None, "accepted": None, "result_code": None, "result": None}
        if play_info:
            d["engine_xy"] = [int(play_info["x"]), int(play_info["y"])]
            d["cell"] = int(play_info["cell"])
            acc = play_info.get("accepted")
            d["accepted"] = None if acc is None else bool(acc)
            if acc is not None:
                d["result_code"] = int(play_info["result_code"])
                d["result"] = {"accepted": d["accepted"], "result_code": d["result_code"],
                               "placement_valid": play_info.get("placement_valid"),
                               "placement_reason": play_info.get("placement_reason")}
        elif play:
            try:
                d["engine_xy"] = list(env.cell_to_engine(cell))
            except Exception:                       # noqa: BLE001 -- the view never breaks the run
                pass
        if play:
            self.plays_accepted += int(d["accepted"] is True)
            self.plays_refused += int(d["accepted"] is False)
        else:
            self.waits += 1
        return d

    def _add_ghost_marks(self, env, eng, xy):
        """The ghost opponent's plays, in their own colour. `ghost_events` is append-only on the env."""
        ev = getattr(env, "ghost_events", None)
        if ev is None:
            return
        ghosts = getattr(env, "_ghosts", [])
        by_tick = collections.defaultdict(list)
        for gg in ghosts:
            by_tick[int(gg["tick"])].append(gg)
        for k in range(self._ghost_seen, len(ev)):
            tk, ok, reason = ev[k]
            cands = by_tick.get(int(tk)) or []
            gg = cands[0] if cands else None
            if gg is None:
                continue
            nx, ny = xy(int(gg["x"]), int(gg["y"]))
            self.marks.append(dict(t=eng.t, x=nx, y=ny, label=str(gg.get("card", "?"))[:12],
                                   ok=bool(ok), reason=reason))
        self._ghost_seen = len(ev)

    def _draw(self, eng, d):
        import cv2
        from clashrl.sim_view import _ASPECT, _HUD_TOP, render_frame
        t0 = time.perf_counter()
        img = render_frame(eng, self.width, self.note, self.acts, radii=self.radii)
        self._t_render += time.perf_counter() - t0
        W = self.width
        BH = int(W / _ASPECT)
        n_fire = _overlay_fire_rings(img, eng, W, self.fire_ring, self.fire_fixed) if self.radii else 0
        _overlay_targets(img, eng, W)
        # ghost / opponent plays
        for m in list(self.marks):
            if eng.t - m["t"] > PLAY_SHOW_S:
                continue
            c = (int(m["x"] * W), _HUD_TOP + int(m["y"] * BH))
            cv2.drawMarker(img, c, _GHOST, cv2.MARKER_DIAMOND, 15, 2)
            lab = m["label"] + ("" if m["ok"] else " X")
            cv2.putText(img, lab, (c[0] - 20, c[1] - 10), cv2.FONT_HERSHEY_PLAIN, 0.7,
                        _GHOST if m["ok"] else _REFUSE, 1)
        self.marks = [m for m in self.marks if eng.t - m["t"] <= PLAY_SHOW_S]
        # OUR decision: the chosen cell
        if d.get("play") and d.get("engine_xy"):
            xy, _ = _mirror_fns(self.focus_side)
            nx, ny = xy(int(d["engine_xy"][0]), int(d["engine_xy"][1]))
            c = (int(nx * W), _HUD_TOP + int(ny * BH))
            col = _ACCEPT if d.get("accepted") else (_REFUSE if d.get("accepted") is False else _SHADOW)
            cv2.drawMarker(img, c, col, cv2.MARKER_CROSS, 17, 2)
            cv2.circle(img, c, 9, col, 1)
            cv2.putText(img, str(d.get("card_key") or "?")[:12], (c[0] + 11, c[1] + 4),
                        cv2.FONT_HERSHEY_PLAIN, 0.8, col, 1)
        line1, col1 = _fmt_decision(d)
        el = d["elixir"]
        if not self.radii:
            ring, rcol = "radii overlay OFF (--radii to draw both rings)", _STRIP_DIM
        elif n_fire:
            ring = "rings: solid = TABLE reach (reward) | pink dash = reach + target hitbox (engine fires)"
            rcol = _FIRE
        else:
            ring, rcol = "rings: solid = TABLE reach; no fire ring (no enemy body on board)", _STRIP_DIM
        line2 = "tick %d  %.1fs   elixir you %.2f / them %.2f   decision #%d   feed %s" % (
            d["tick"], d["seconds"], el[0], el[1], self.decisions + 1, eng.feed)
        img = np.vstack([img, _strip(W, [(line1, col1, 0.85), (line2, _STRIP_FG, 0.8), (ring, rcol, 0.75)])])
        self._write(img)
        return img

    def _write(self, img):
        import cv2
        if self.out is None and self.png_dir is None:
            self.frames_written += 1
            return
        if self._writer is None and self.png_dir is None:
            self.out.parent.mkdir(parents=True, exist_ok=True)
            w = cv2.VideoWriter(str(self.out), cv2.VideoWriter_fourcc(*"mp4v"), self.fps,
                                (img.shape[1], img.shape[0]))
            if not w.isOpened():
                self.png_dir = self.out.with_suffix("")
                self.png_dir.mkdir(parents=True, exist_ok=True)
                print(f"[live-view] mp4v writer failed; writing PNG frames to {self.png_dir}")
            else:
                self._writer = w
        if self._writer is not None:
            self._writer.write(img)
        else:
            self.png_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(self.png_dir / f"{self.frames_written:06d}.png"), img)
        self.frames_written += 1
        if self.progress and self.frames_written % 200 == 0:
            print(f"[live-view] {self.frames_written} frames", flush=True)

    @staticmethod
    def still(path, img):
        import cv2
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), img)

    def close(self):
        self.detach()
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        return self.summary()

    def summary(self):
        return {"decisions": self.decisions, "frames": self.frames_written,
                "plays_accepted": self.plays_accepted, "plays_refused": self.plays_refused,
                "waits": self.waits, "rule": self.rule, "radii": self.radii,
                "fire_ring_mode": self.fire_ring,
                "ms_per_render_frame_call": round(1000 * self._t_render / max(1, self.decisions), 2),
                "out": str(self.out or self.png_dir)}


def frame_of(state):
    """EngineMatchEnv._frame_of, reused verbatim, PLUS the projectiles the recorder-shaped frame drops.

    `_frame_of` is a staticmethod on a file I must not edit; calling it keeps the entity/tower shape
    byte-identical to what the adapter and the trainer see, and the extra key is additive
    (view_engine_from_frame reads `projectiles` when present and ignores it when absent)."""
    from engine_env import EngineMatchEnv
    fr = EngineMatchEnv._frame_of(state)
    pj = state.get("projectiles")
    if pj:
        rows = []
        for p in pj:
            if isinstance(p, dict):
                rows.append([int(p.get("side", 0)), int(p.get("x", 0)), int(p.get("y", 0)),
                             int(p.get("target_x", p.get("x", 0))), int(p.get("target_y", p.get("y", 0))),
                             p.get("name", str(p.get("card_id", -1)))])
            else:
                rows.append(list(p))
        fr["projectiles"] = rows
    return fr


# =================================================================================================
# 4. THE POLICY PROBE  (gate probability + the three decision rules)
# =================================================================================================
class ProbePolicy:
    """`run_engine_env.GreedyPolicy`'s network / masks, with the DECISION RULE made explicit and the
    gate's probability reported. `act()` keeps GreedyPolicy's signature so it drops into any driver."""

    def __init__(self, env, ckpt, device="cpu", rule="sample", gate_tau=0.25, heads="argmax", seed=0,
                 view=None):
        import torch
        from run_engine_env import GreedyPolicy
        self.g = GreedyPolicy(env, ckpt=ckpt, device=device)
        self.torch = torch
        self.env = env
        self.rule = rule
        self.gate_tau = float(gate_tau)
        self.heads = heads
        self.rng = random.Random(seed)
        self.view = view
        self.meta = dict(self.g.meta)
        self.meta.update(rule=rule, gate_tau=self.gate_tau, heads=heads, ckpt=str(ckpt))
        self.last = None

    def _pick(self, logits, mask):
        """argmax or a Categorical sample over the MASKED logits (engine_ppo.rollout's factorisation)."""
        torch = self.torch
        lg = logits.masked_fill(~mask, _NEG).flatten()
        p = torch.softmax(lg, -1)
        if self.heads == "sample":
            return int(torch.multinomial(p, 1)), p
        return int(lg.argmax()), p

    def probe(self, env, obs):
        """-> (action, meta). meta carries p_play, the rule, the chosen card and the top-3 cards."""
        torch = self.torch
        G = self.g
        with torch.no_grad():
            x = (torch.as_tensor(obs, device=G.dev).unsqueeze(0)
                 .permute(0, 3, 1, 2).contiguous().float() / 255.0)
            hand = torch.as_tensor(env.hand_vec, device=G.dev).unsqueeze(0)
            nxt = torch.as_tensor(env.next_vec, device=G.dev).unsqueeze(0)
            elx = torch.as_tensor(env.elixir_vec, device=G.dev).unsqueeze(0)
            thr = torch.as_tensor(env.threat_vec, device=G.dev).unsqueeze(0)
            z, cards, cells = G.net.forward_parts(x, hand, nxt, elx, thr)
            gq = G.gate(z)
            # the exact monitoring quantity engine_ppo l.335 / gate_probe.py report
            p_play = float(torch.sigmoid(gq[0, 1] - gq[0, 0]))
            elixir = elx * 10.0
            playable = (hand > 0.5) & (G.costs.view(1, -1) <= elixir + 1e-6)
            meta = {"p_play": round(p_play, 5), "rule": self.rule, "gate_tau": self.gate_tau,
                    "n_playable": int(playable.sum()), "wait_reason": None}
            try:                                    # the ordered cycle: hand first, then the queue
                q = [env.deck_keys[int(i)] for i in env.sim._queue_ids()]
                meta["hand"], meta["queue"] = q[:4], q[4:]
            except Exception:                       # noqa: BLE001 -- fall back to the unordered hand vector
                meta["hand"] = [env.deck_keys[i] for i, v in enumerate(env.hand_vec) if float(v) >= 0.5]
                meta["queue"] = None
            if not bool(playable.any()):
                meta["wait_reason"] = "nothing in hand is affordable"
                return self._ret((0, 0, 0), meta)
            if self.rule == "sample":
                do = (self.rng.random() < p_play)
                if not do:
                    meta["wait_reason"] = "sampled WAIT at p=%.3f" % p_play
            elif self.rule == "threshold":
                do = p_play > self.gate_tau
                if not do:
                    meta["wait_reason"] = "p <= tau %.2f" % self.gate_tau
            else:                                                  # 'argmax' == GreedyPolicy's rule
                do = float(gq[0, 1]) > float(gq[0, 0])
                if not do:
                    meta["wait_reason"] = "argmax gate = WAIT (p <= 0.5)"
            card, pc = self._pick(cards, playable)
            order = np.argsort(-pc.cpu().numpy())[:3]
            meta["top_cards"] = [[env.deck_keys[int(i)], round(float(pc[int(i)]), 4)] for i in order]
            meta["p_card"] = round(float(pc[card]), 5)
            meta["card_key"] = env.deck_keys[card]
            if not do:
                return self._ret((0, 0, 0), meta)
            pk = env.sim.pocket_state(0)
            cm = G.cellmask(card, (2 if pk[0] else 0) + (1 if pk[1] else 0))
            cell, pcell = self._pick(cells[0, card], cm)
            meta["p_cell"] = round(float(pcell[cell]), 6)
            meta["cell"] = int(cell)
            return self._ret((1, card, int(cell)), meta)

    def _ret(self, action, meta):
        self.last = meta
        if self.view is not None:
            self.view.note_gate(meta)
        return action, meta

    def act(self, env, obs):
        return self.probe(env, obs)[0]


# =================================================================================================
# 5. THE REPLAY ENV  (the same surface, fed from a recording -- no engine, no socket)
# =================================================================================================
class ReplayEngineEnv:
    """Presents `EngineMatchEnv`'s surface, driven from a recording on disk.

    WHAT IS REAL: every board state is a real engine state (the recording is a real engine match) and
    the observation is built by the SAME adapter the trainer uses.
    WHAT IS NOT: the policy's action is NOT applied -- the world advances along the RECORDING, so the
    policy's decision is a SHADOW (what it would have done in that state) and `info['play']['accepted']`
    is None, never a fabricated result_code. This is a test harness for the live wire and the source of
    the artifact payload; it is NOT a training env.

    Hand / cycle tracking is L61's rule, verbatim in method: the initial 8-slot queue from
    `build_bc_dataset.engine_queue`, then `sim._play_slot` on every accepted focus-side play in the log.
    """

    def __init__(self, rec_path, focus_side=1, decision_ticks=10):
        from engine_env import EngineMatchEnv
        W = shared_W()
        self.sim = W["env"]
        self.db = W["db"]
        self.spec_of = W["spec_of"]
        self.slot_of_base = W["slot_of_base"]
        self.sim_eng0 = W["sim_eng0"]
        self.actions = self.sim.actions
        self.gw = self.actions.gw
        self.n_cards = int(self.sim.n_cards)
        self.n_cells = int(self.sim.n_cells)
        self.threat_dim = int(self.sim.threat_dim)
        self.obs_shape = self.sim.obs_shape
        self.deck_keys = list(self.sim.deck_keys)
        self.anywhere_ids = set(self.sim.anywhere_ids)
        self.decision_ticks = int(decision_ticks)
        self.agent_dt = decision_ticks * TICK_S
        self._EME = EngineMatchEnv
        self.rec = json.loads(Path(rec_path).read_text(encoding="utf-8"))
        self.tag = self.rec.get("tag", Path(rec_path).stem)
        self.side = int(focus_side)
        self.opp = 1 - self.side
        self._mirror = (self.side == 1)
        self.eng = None                                # NO engine connection, deliberately
        self.entry = {"tag": self.tag}

    # the coordinate mapping is EngineMatchEnv's own code, called unbound on this instance
    def cell_to_engine(self, cell, mirror=None):
        return self._EME.cell_to_engine(self, cell, mirror)

    def engine_to_cell(self, x, y, mirror=None):
        return self._EME.engine_to_cell(self, x, y, mirror)

    # -------------------------------------------------------------- timeline
    def timeline(self):
        ev = list(self.rec.get("frames", [])) + list(self.rec.get("play_frames", []))
        ev.sort(key=lambda f: (int(f["tick"]), f.get("play_index", -1)))
        return ev

    def reset(self, entry=None, *, index=None):
        import zlib
        import build_bc_dataset as V1
        self.frames = self.timeline()
        self.fi = 0
        self.tick = int(self.frames[0]["tick"])
        self.log = sorted([e for e in self.rec.get("log", [])
                           if e.get("accepted") and e.get("x") is not None],
                          key=lambda e: int(e.get("engine_tick", e["tick"])))
        self.li = 0
        self.our_plays = self.our_rejected = 0
        self.ghost_ok = self.ghost_rejected = 0
        self.ghost_events = []
        self._ghosts = [{"tick": int(e.get("engine_tick", e["tick"])), "x": int(e["x"]), "y": int(e["y"]),
                         "card": e.get("card", "?")}
                        for e in self.log if int(e["side"]) == self.opp]
        self._ghost_fired = 0
        self.done = self.terminated = False
        self.steps = 0
        self.ep_reward = 0.0
        self._last_upd = None
        self.sim.rng.seed(zlib.crc32(f"{self.tag}:{self.side}".encode()))
        self.sim.domain_rand.enabled = False
        self.sim.domain_rand.resample()
        self.sim._canvas_stack.reset()
        self.sim._reset_vectors()
        self.sim._tid_unlit_t = None
        self.sim._threat_credits = 0
        self.sim.evo_charge = [0] * self.sim.n_slots
        q0 = V1.engine_queue(self.rec, self.side)
        self.hand_source = "heuristic"
        if q0 is not None and all(b in self.slot_of_base for b in q0) and len(set(q0)) == 8:
            self.sim.cycle = [self.slot_of_base[b] for b in q0]
            self.hand_source = "engine"
        else:
            self.sim.cycle = list(range(self.sim.n_slots))
        self.hand_mismatch = 0
        return self._render(self.frames[0])

    def _render(self, frame):
        eng, n_unmapped, _ = L61.frame_to_engine(frame, self.side, self.spec_of,
                                                 {"names": collections.Counter(),
                                                  "unmapped": collections.Counter()})
        self.sim.eng = eng
        self.sim.agent_dt = self.agent_dt if self._last_upd is None else max(0.05, eng.t - self._last_upd)
        self.sim._update_vectors()
        self._last_upd = eng.t
        self.hand_vec = self.sim.hand_vec
        self.next_vec = self.sim.next_vec
        self.elixir_vec = self.sim.elixir_vec
        self.threat_vec = self.sim.threat_vec
        self._last_obs = self.sim._last_obs
        self._last_frame = frame
        return self._last_obs

    def _advance_hand(self, upto_tick):
        """Every accepted FOCUS-side play in the log up to `upto_tick` leaves the pro's hand (L61's rule)."""
        import build_bc_dataset as V1
        while self.li < len(self.log):
            e = self.log[self.li]
            t = int(e.get("engine_tick", e["tick"]))
            if t > upto_tick:
                break
            self.li += 1
            if int(e["side"]) != self.side:
                continue
            base = V1.key_base(str(e.get("card", "")))
            slot = self.slot_of_base.get(base)
            if slot is None:
                continue
            if slot not in self.sim.cycle[:4]:
                self.sim.cycle.remove(slot)
                self.sim.cycle.insert(0, slot)
                self.hand_mismatch += 1
            self.sim._play_slot(self.sim._slot_card_id(slot))

    def step(self, action):
        """Advance the RECORDING by `decision_ticks`; the action is recorded, never applied."""
        play, card_id, cell = int(action[0]), int(action[1]), int(action[2])
        info_play = None
        if play:
            cell = self.actions.deploy_clamp(int(card_id) in self.anywhere_ids, int(cell))
            x, y = self.cell_to_engine(int(cell))
            info_play = {"card_id": card_id, "cell": int(cell), "deck_index": None, "x": x, "y": y,
                         "accepted": None, "result_code": None, "shadow": True}
            self.our_plays += 1
        target = self.tick + self.decision_ticks
        while self.fi + 1 < len(self.frames) and int(self.frames[self.fi + 1]["tick"]) <= target:
            self.fi += 1
        if self.fi + 1 < len(self.frames) and int(self.frames[self.fi]["tick"]) < target:
            self.fi += 1                                   # a sparse (1 s) recording: take the next frame
        self.tick = int(self.frames[self.fi]["tick"])
        self._advance_hand(self.tick)
        while self._ghost_fired < len(self._ghosts) and self._ghosts[self._ghost_fired]["tick"] <= self.tick:
            self.ghost_events.append((self._ghosts[self._ghost_fired]["tick"], 1, "recorded"))
            self.ghost_ok += 1
            self._ghost_fired += 1
        done = self.fi >= len(self.frames) - 1
        self.done = self.terminated = done
        self.steps += 1
        outcome = crowns = None
        if done:
            fin = self.rec.get("final") or {}
            crowns, outcome = fin.get("crowns"), fin.get("outcome")
            self.outcome, self.final_crowns = outcome, crowns
        obs = self._render(self.frames[self.fi])
        info = {"tick": self.tick, "outcome": outcome, "crowns": crowns, "terminated": done,
                "tail_capped": False, "play": info_play, "tag": self.tag,
                "ghost_ok": self.ghost_ok, "ghost_rejected": 0,
                "our_plays": self.our_plays, "our_rejected": 0, "shadow": True}
        return obs, 0.0, done, info

    def episode_summary(self):
        fin = self.rec.get("final") or {}
        return {"tag": self.tag, "tick": self.tick, "seconds": round(self.tick * TICK_S, 1),
                "steps": self.steps, "terminated": True, "outcome": fin.get("outcome"),
                "crowns": fin.get("crowns"), "reward": 0.0, "our_plays": self.our_plays,
                "our_rejected": 0, "shadow": True, "hand_source": self.hand_source,
                "hand_mismatch": self.hand_mismatch}

    def close(self):
        pass


# =================================================================================================
# 6. DRIVERS
# =================================================================================================
def _drive(env, pol, view, max_steps=100000, stills=None, out_stem=None):
    obs = env.reset()
    view.on_reset(env, state=getattr(env, "_last_frame", None))
    done, n = False, 0
    still_at = set(stills or ())
    saved = []
    while not done and n < max_steps:
        a, meta = pol.probe(env, obs)
        view.note_gate(meta)
        pre = getattr(env, "_last_frame", None)   # the frame the policy decided on
        obs, r, done, info = env.step(a)
        img = view.on_decision(env, a, info, gate=meta, state=getattr(env, "_last_frame", None),
                               pre_state=pre)
        if n in still_at and img is not None and out_stem:
            p = Path(str(out_stem) + "_still%d_tick%d.png" % (n, info["tick"]))
            view.still(p, img)
            saved.append(str(p))
        n += 1
    return env.episode_summary(), saved


def mode_replay(a):
    env = ReplayEngineEnv(a.rec, focus_side=a.focus, decision_ticks=a.decision_ticks)
    view = LiveEngineView(out=a.out, focus_side=a.focus, radii=a.radii, width=a.width, fps=a.fps,
                          fire_ring=a.fire_ring, fire_fixed=a.fire_fixed, rule=a.rule,
                          max_frames=a.max_frames)
    pol = ProbePolicy(env, a.policy, device=a.device, rule=a.rule, gate_tau=a.gate_tau,
                      heads=a.heads, seed=a.seed, view=view)
    n_est = max(1, len(env.timeline()) // max(1, a.decision_ticks))
    stills = {int(n_est * f) for f in (0.12, 0.5, 0.85)}
    summ, saved = _drive(env, pol, view, stills=stills,
                         out_stem=str(Path(a.out).with_suffix("")) if a.out else None)
    out = view.close()
    out.update(episode=summ, policy=pol.meta, stills=saved, tag=env.tag, focus_side=a.focus,
               mode="replay (SHADOW decisions: the policy did not drive this match)")
    print(json.dumps(out, indent=1, default=str))
    if a.rows:
        Path(a.rows).write_text(json.dumps(view.rows), encoding="utf-8")
    return out


def mode_live(a):
    """THE LIVE PATH. Needs a FREE engine slot -- see live_view.md 6 before running."""
    from engine_env import EngineMatchEnv
    env = EngineMatchEnv(port=a.port, decision_ticks=a.decision_ticks)
    view = LiveEngineView(out=a.out, radii=a.radii, width=a.width, fps=a.fps, fire_ring=a.fire_ring,
                          fire_fixed=a.fire_fixed, rule=a.rule, max_frames=a.max_frames)
    pol = ProbePolicy(env, a.policy, device=a.device, rule=a.rule, gate_tau=a.gate_tau,
                      heads=a.heads, seed=a.seed, view=view)
    view.attach(env)                    # <- the wrapper: engine_env.py untouched, no extra RPC
    rows = []
    for i in range(a.matches):
        obs = env.reset(index=a.start + i)
        view.on_reset(env)
        done, n = False, 0
        while not done and n < 100000:
            act, meta = pol.probe(env, obs)
            obs, r, done, info = env.step(act)      # the wrapper renders inside step()
            n += 1
        s = env.episode_summary()
        rows.append({k: v for k, v in s.items() if k != "ghost_events"})
        print(f"[live-view] match {i+1}/{a.matches} {s['tag']} tick {s['tick']} {s['outcome']} "
              f"crowns {s['crowns']} our {s['our_plays']}p/{s['our_rejected']}rej", flush=True)
    out = view.close()
    env.close()
    out.update(matches=rows, policy=pol.meta, mode="live (the policy DROVE the engine)")
    print(json.dumps(out, indent=1, default=str))
    if a.rows:
        Path(a.rows).write_text(json.dumps(view.rows), encoding="utf-8")
    return out


# =================================================================================================
# 7. ARTIFACT PAYLOAD
# =================================================================================================
def build_payload(a):
    """Everything the HTML visualizer draws, from ONE recording + ONE checkpoint, as compact JSON."""
    from clashrl.geometry_reward import radii_of
    env = ReplayEngineEnv(a.rec, focus_side=a.focus, decision_ticks=a.decision_ticks)
    view = LiveEngineView(out=None, focus_side=a.focus, radii=True, rule=a.rule, progress=False)
    pol = ProbePolicy(env, a.policy, device=a.device, rule=a.rule, gate_tau=a.gate_tau,
                      heads=a.heads, seed=a.seed, view=view)
    summ, _ = _drive(env, pol, view)
    rec = env.rec
    kw = dict(siege_sight=float(env.sim_eng0.siege_sight), tower_range=float(env.sim_eng0.tower_range),
              king_range=float(env.sim_eng0.king_range))
    # per-NAME spec table: radii + hitbox, so the frames stay as small as the owner's artifact
    names = set()
    for f in rec.get("frames", []) + rec.get("play_frames", []):
        for e in f.get("entities", []):
            names.add(e[3])
    specs = {}
    for nm in sorted(names):
        if nm == "-1":
            continue
        sp = env.spec_of(nm)
        if sp is None:
            specs[nm] = {"unmapped": 1}
            continue
        ra, rs = radii_of(sp, **kw)
        specs[nm] = {"key": sp.key, "kind": sp.kind, "r_atk": round(float(ra), 3),
                     "r_sight": round(float(rs), 3), "r_body": round(float(sp.radius), 3),
                     "flying": bool(sp.flying), "elixir": float(sp.elixir),
                     "siege": bool(getattr(sp, "siege", False))}
    frames = []
    for f in sorted(rec.get("frames", []) + rec.get("play_frames", []),
                    key=lambda q: (int(q["tick"]), q.get("play_index", -1))):
        row = {"t": int(f["tick"]),
               "el": [None if f["elixir"][0] is None else round(float(f["elixir"][0]), 3),
                      None if f["elixir"][1] is None else round(float(f["elixir"][1]), 3)],
               "e": [[int(e[0]), int(e[1]), int(e[2]), e[3], int(e[4]), int(e[5]),
                      int(e[6]) if len(e) > 6 else -1] for e in f.get("entities", [])],
               "tw": [[int(t[0]), t[1], t[2], int(t[3]), int(t[4]), int(t[5]), int(t[6])]
                      for t in f.get("towers", [])]}
        pj = f.get("projectiles")
        if pj:
            row["p"] = [[int(q[0]), int(q[1]), int(q[2]), int(q[3]), int(q[4]), q[5]] for q in pj]
        frames.append(row)
    plays = [{"t": int(e.get("engine_tick", e["tick"])), "side": int(e["side"]), "card": e.get("card"),
              "x": int(e["x"]), "y": int(e["y"]), "ok": bool(e.get("accepted")),
              "res": e.get("result_name") or e.get("result_code")}
             for e in rec.get("log", []) if e.get("x") is not None]
    from clashrl.sim.engine import build_spec
    deck = []
    for i, k in enumerate(env.deck_keys):
        row = {"key": k, "elixir": round(float(pol.g.costs[i]), 1)}
        try:
            sp = build_spec(env.db, k, 11)
            row.update(kind=sp.kind, r_atk=round(float(radii_of(sp, **kw)[0]), 3),
                       r_body=round(float(sp.radius), 3))
        except Exception:                           # noqa: BLE001 -- cost alone is enough for the HUD
            pass
        deck.append(row)
    reg, ot = float(env.sim_eng0.regulation), float(env.sim_eng0.overtime)
    out = {"schema": "live_view_payload_v2",
           "deck": deck,
           # elixir phase boundaries (s): the sim's elixir_rate rule (2x at reg-60, 3x at reg+ot-60);
           # measured on this engine recording: regen 0.36 -> 0.72 /s at tick 2401, 0.72 -> 1.08 at 4801
           "phase_s": [reg - 60.0, reg + max(0.0, ot - 60.0)],
           "tag": env.tag, "focus_side": a.focus, "decision_ticks": a.decision_ticks, "tick_s": TICK_S,
           "final": rec.get("final"), "final_decks": rec.get("final_decks"),
           "policy": pol.meta, "rule": a.rule, "gate_tau": a.gate_tau, "heads": a.heads, "shadow": True,
           "board": {"tiles_x": 18, "tiles_y": 32, "units_per_tile": 1000,
                     "tower_range": kw["tower_range"], "king_range": kw["king_range"],
                     "siege_sight": kw["siege_sight"],
                     "princess_half": _PRINCESS_HALF, "king_half": _KING_HALF},
           "specs": specs, "frames": frames, "plays": plays, "decisions": view.rows, "episode": summ}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        print("[live-view] payload -> %s  (%.2f MB, %d frames, %d decisions, %d recorded plays)"
              % (a.out, Path(a.out).stat().st_size / 1e6, len(frames), len(view.rows), len(plays)))
    return out


def mode_export(a):
    build_payload(a)


# =================================================================================================
# 8. SELF TEST -- the assertions that stand in for a live run while the slots are busy
# =================================================================================================
def selftest(a):
    import cv2
    from clashrl.geometry_reward import radii_of
    from clashrl.sim_view import render_frame
    res = {"rec": a.rec, "focus": a.focus, "rule": a.rule, "heads": a.heads}
    env = ReplayEngineEnv(a.rec, focus_side=a.focus, decision_ticks=a.decision_ticks)
    obs = env.reset()
    res["obs_shape_matches_sim"] = [list(obs.shape), list(env.obs_shape)]
    assert tuple(obs.shape) == tuple(env.obs_shape), res["obs_shape_matches_sim"]

    # (A) the cell<->engine mapping on the REPLAY env is EngineMatchEnv's own code, unbound
    errs = []
    for c in range(0, env.n_cells, 7):
        x, y = env.cell_to_engine(c)
        c2, d = env.engine_to_cell(x, y)
        errs.append((c2 == c, d))
    res["cell_roundtrip_exact"] = [int(sum(1 for ok, _ in errs if ok)), len(errs),
                                   round(float(max(d for _, d in errs)), 6)]
    assert res["cell_roundtrip_exact"][0] == res["cell_roundtrip_exact"][1]

    # (B) the fire-ring overlay changes pixels and only pixels (render_frame's own output untouched)
    fr = env._last_frame
    eng = view_engine_from_frame(fr, a.focus, env.spec_of, sim_eng=env.sim_eng0)
    W = 460
    img0 = render_frame(eng, W, NOTE_TAG, env.actions, radii=True)
    img1 = img0.copy()
    n_fire = _overlay_fire_rings(img1, eng, W, "nearest")
    res["reset_frame"] = {"units": len(eng.units), "fire_rings": n_fire,
                          "px_changed": int((img0 != img1).any(axis=2).sum())}

    # (C) drive the whole wire
    pol = ProbePolicy(env, a.policy, device="cpu", rule=a.rule, gate_tau=a.gate_tau, heads=a.heads,
                      seed=a.seed)
    view = LiveEngineView(out=None, focus_side=a.focus, radii=True, width=W, progress=False)
    view.on_reset(env, state=env._last_frame)
    done, n = False, 0
    busiest = (0, None, None)
    ps, plays = [], 0
    t0 = time.perf_counter()
    while not done and n < 100000:
        act, meta = pol.probe(env, obs)
        view.note_gate(meta)
        obs, r, done, info = env.step(act)
        img = view.on_decision(env, act, info, gate=meta, state=env._last_frame)
        ps.append(meta.get("p_play"))
        plays += int(act[0] == 1)
        nb = sum(1 for e in env._last_frame["entities"] if e[3] != "-1")
        if nb > busiest[0]:
            busiest = (nb, env._last_frame, img)
        n += 1
    res["decisions"] = n
    res["plays_chosen"] = plays
    ps = [p for p in ps if p is not None]
    arr = np.array(ps)
    res["p_play"] = {"mean": round(float(arr.mean()), 4), "max": round(float(arr.max()), 4),
                     "min": round(float(arr.min()), 4), "p90": round(float(np.percentile(arr, 90)), 4),
                     "frac_gt_0.25": round(float((arr > 0.25).mean()), 4),
                     "frac_gt_0.50": round(float((arr > 0.50).mean()), 4), "n": int(arr.size)}
    res["episode"] = env.episode_summary()
    res["view_summary"] = view.summary()
    res["wall_s_whole_replay"] = round(time.perf_counter() - t0, 1)

    # (D) the busiest frame: how far apart the two rings actually are, in tiles
    _nb, frb, imgb = busiest
    engb = view_engine_from_frame(frb, a.focus, env.spec_of, sim_eng=env.sim_eng0)
    kw = dict(siege_sight=engb.siege_sight, tower_range=engb.tower_range, king_range=engb.king_range)
    gaps = []
    for u in engb.units:
        if u.hp <= 0 or u.spec.kind == "spell":
            continue
        ra, _ = radii_of(u.spec, **kw)
        rf, _l = fire_ring_radius(engb, u, u.team, ra, "nearest")
        if rf is not None:
            gaps.append({"what": u.name, "r_table": round(ra, 2), "r_fire": round(rf, 2),
                         "gap_tiles": round(rf - ra, 3)})
    for tm, tws in engb.towers.items():
        for tw in tws:
            if not tw.alive:
                continue
            ra, _ = radii_of(tw, **kw)
            rf, _l = fire_ring_radius(engb, tw, tm, ra, "nearest")
            if rf is not None:
                gaps.append({"what": ("king" if tw.king else "princess") + "_t%d" % tm,
                             "r_table": round(ra, 2), "r_fire": round(rf, 2),
                             "gap_tiles": round(rf - ra, 3)})
    res["ring_gaps_busiest_frame"] = {
        "tick": int(frb["tick"]), "n_bodies": _nb, "rows": gaps,
        "gap_tiles_min": round(min(g["gap_tiles"] for g in gaps), 3) if gaps else None,
        "gap_tiles_max": round(max(g["gap_tiles"] for g in gaps), 3) if gaps else None}
    # (E) THE WRAPPER PATH -- the exact mechanism `live` mode uses on a real EngineMatchEnv:
    #     attach() wraps _render + step, the driver calls only env.step, and detach() restores both.
    env2 = ReplayEngineEnv(a.rec, focus_side=a.focus, decision_ticks=a.decision_ticks)
    pol2 = ProbePolicy(env2, a.policy, device="cpu", rule=a.rule, gate_tau=a.gate_tau, heads=a.heads,
                       seed=a.seed)
    v2 = LiveEngineView(out=None, radii=True, width=W, progress=False, max_frames=40)
    r0, s0 = env2._render, env2.step
    v2.attach(env2)
    pol2.view = v2
    obs2 = env2.reset()
    v2.on_reset(env2, state=env2._last_frame)
    done2, k = False, 0
    while not done2 and k < 40:
        act2, _m = pol2.probe(env2, obs2)          # probe() calls view.note_gate itself
        obs2, _r, done2, _i = env2.step(act2)      # the WRAPPER renders inside step()
        k += 1
    v2.close()
    res["wrapper_path"] = {"steps_driven": k, "frames_rendered_by_wrapper": v2.frames_written,
                           "decisions": v2.decisions,
                           "gate_seen": sum(1 for r in v2.rows if r.get("p_play") is not None),
                           "detached_render_restored": env2._render.__func__ is r0.__func__,
                           "detached_step_restored": env2.step.__func__ is s0.__func__,
                           "no_instance_shadow_left": ("step" not in env2.__dict__
                                                       and "_render" not in env2.__dict__)}
    assert v2.decisions == k, res["wrapper_path"]
    assert res["wrapper_path"]["gate_seen"] == k, res["wrapper_path"]
    assert res["wrapper_path"]["detached_render_restored"] and res["wrapper_path"]["detached_step_restored"]
    assert res["wrapper_path"]["no_instance_shadow_left"], res["wrapper_path"]

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        if imgb is not None:
            cv2.imwrite(str(Path(a.out).with_suffix(".png")), imgb)
            res["still"] = str(Path(a.out).with_suffix(".png"))
        Path(a.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))
    return res


# =================================================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["live", "replay", "export", "selftest"])
    ap.add_argument("--rec", default=str(EXT / "replay_00LYPLJLC80L_run1.json"))
    ap.add_argument("--focus", type=int, default=1)
    ap.add_argument("--port", type=int, default=38031)
    ap.add_argument("--matches", type=int, default=1)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--policy", default=str(ICEBOW / "data" / "bc_pro" / "models" / "bc_bias_native_s0.pt"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--decision-ticks", dest="decision_ticks", type=int, default=10)
    # THE DECISION RULE -- sampling is the default because it is what engine_ppo trains with.
    ap.add_argument("--rule", choices=["sample", "threshold", "argmax"], default="sample")
    ap.add_argument("--sample", dest="rule", action="store_const", const="sample",
                    help="(default) sample the gate, as engine_ppo.rollout does")
    ap.add_argument("--gate_tau", type=float, default=0.25, help="threshold for --rule threshold")
    ap.add_argument("--heads", choices=["argmax", "sample"], default="argmax",
                    help="card/cell heads: argmax (legible) or sample (training-faithful)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--radii", action="store_true", default=False)
    ap.add_argument("--no-radii", dest="radii", action="store_false")
    ap.add_argument("--fire_ring", choices=["nearest", "fixed", "off"], default="nearest")
    ap.add_argument("--fire_fixed", type=float, default=0.5)
    ap.add_argument("--width", type=int, default=560)
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--max_frames", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows", default=None, help="write the per-decision rows as JSON")
    a = ap.parse_args()
    import torch
    torch.manual_seed(a.seed)
    torch.set_num_threads(1)
    if a.fire_ring == "off":
        a.fire_ring, a.fire_fixed = "fixed", 0.0
    globals()["selftest" if a.mode == "selftest" else f"mode_{a.mode}"](a)


if __name__ == "__main__":
    main()
