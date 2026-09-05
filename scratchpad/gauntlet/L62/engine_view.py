"""L62: the ENGINE feed for the sim debugger.

`clashrl.sim_view.render_frame(eng, ...)` draws whatever engine-like object it is handed. The sim hands it a
`SimEngine`; this module hands it a REAL-ENGINE observation frame (cr-native-sandbox recordings) wrapped in a
duck-typed object that carries every attribute `render_frame` reads. ONE renderer, TWO feeds; sim_view.py is not
edited.

Honesty rule: what the engine does not export is ZERO / EMPTY here, and the HUD carries a fixed tag
("ENGINE FEED: no status/zone/arc export") so an empty overlay is never mistaken for "no stun".

Coordinates: engine units 0..18000 x 0..32000 (1 tile = 1000 units on BOTH axes), tick = 0.05 s. Focus side ->
team 0 -> bottom, with exactly the L61 mirror (`frame_to_engine` in scratchpad/gauntlet/L61/build_bc_v2.py):
side 1 focus => X -> 18000-X, Y -> 32000-Y, sides swapped; sim x = X/18000, sim y = 1 - Y/32000.

    cd icebow && PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L62/engine_view.py \
        --rec C:/.../replay_TAG.json --focus 1 --out C:/.../engine_view/TAG.mp4 --radii
    ... --check                     # one-frame assertions (tower anchors, mirror, radii pixels, placement pixels)
    ... --ranges                    # first-shot firing-range read from a record_full recording
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
sys.path.insert(0, str(ICEBOW / "src"))
sys.path.insert(0, str(ROOT / "scratchpad" / "gauntlet" / "L61"))
import build_bc_v2 as L61                                              # noqa: E402  (L61 adapter, unmodified)
from build_bc_v2 import ANCHORS, TICK_S, FakeEngine, FakeUnit, tower_at  # noqa: E402

EXT = ROOT / "scratchpad" / "gauntlet" / "ext"
OUT_DIR = EXT / "engine_view"
NOTE_TAG = "ENGINE FEED: no status/zone/arc export"          # <= 46 chars: render_frame clips the note there
NOT_EXPORTED = "engine feed: status timers/zones/arcs/abilities not exported"
PLAY_SHOW_S = 1.5                                            # how long a placement marker / readout stays up

# BGR, distinct from every colour sim_view uses
_OPP_MARK = (0, 90, 255)         # opponent's play: orange diamond
_ME_MARK = (255, 220, 120)       # focus play (no-radii mode): pale blue square
_UNMAPPED = (0, 0, 255)          # '?' label for a card with no sim spec


# The engine names a spawned body after its PARENT card. (name, max_hp) pairs measured in batch_v2 play frames
# (engine_view.md 2/8) whose sim identity is a different card; anything not listed keeps the parent's spec.
_SUBBODY = {
    ("Graveyard", 81): "Skeletons",          # 471 bodies, all 81 hp = a level-11 skeleton, never the zone
    ("SkeletonBalloon", 81): "Skeletons",
    ("Witch", 81): "Skeletons",
    ("Clone", 1): "__generic__",             # a 1-hp clone: the copied card's identity is NOT exported
}
# Bridge ability_state_code -> name, copied from native_core/env.py ABILITY_STATE_NAMES (docs: API.md 2, technical 20)
ABILITY_STATE_NAMES = {0: "unknown", 1: "absent", 2: "ready", 3: "on_cooldown", 4: "all_charges_consumed",
                       5: "limited_availability", 6: "disabled", 7: "not_enough_elixir", 8: "temporarily_unavailable",
                       9: "deploying", 10: "pending", 11: "casting", 12: "not_yet_available"}
_TARGET_LINK = (200, 200, 60)   # BGR, attack-target link (post-render overlay; sim_view has no target line)


# ------------------------------------------------------------------------------------------------ fake bodies
class ViewUnit(FakeUnit):
    """L61's FakeUnit + every per-unit attribute render_frame / _draw_radii / board_from_engine read.
    Every status timer is 0 because the engine does not export them (see NOT_EXPORTED)."""
    __slots__ = ("stun_left", "slow_left", "shield_left", "flying_left", "dash_left", "souls", "ability_active_s",
                 "ability_left", "attacking", "cloned", "taunt_ref", "kind_code", "name",
                 "entity_id", "level", "behavior_state", "pending_damage", "ability_state_code")

    def __init__(self, spec, team, x, y, hp, deploying, kind_code=-1, name=""):
        super().__init__(spec, team, x, y, hp, deploying)
        self.entity_id = None
        self.level = 0
        self.behavior_state = None
        self.pending_damage = 0
        self.ability_state_code = -1
        self.stun_left = self.slow_left = self.shield_left = self.flying_left = 0.0
        self.dash_left = self.souls = 0
        self.ability_active_s = 0.0
        self.ability_left = -1
        self.attacking = False
        self.cloned = False
        self.taunt_ref = None
        self.kind_code = kind_code
        self.name = name


class ViewProjectile:
    """What the projectile loop in render_frame reads: x,y,tx,ty,team,label,radius,pierce,parent,ground_only,width."""
    __slots__ = ("x", "y", "tx", "ty", "team", "label", "radius", "pierce", "parent", "ground_only", "width", "name")

    def __init__(self, x, y, tx, ty, team, label, radius, pierce, ground_only, name):
        self.x, self.y, self.tx, self.ty, self.team = x, y, tx, ty, team
        self.label, self.radius, self.pierce, self.ground_only = label, radius, pierce, ground_only
        self.parent = None
        self.width = 0.0
        self.name = name


class EngineView(FakeEngine):
    """Everything render_frame reads from a SimEngine. Lists the real engine does not export are EMPTY."""

    def __init__(self, t, units, towers, elixir, sim_eng=None):
        super().__init__(t, units, towers, elixir)
        # board / range constants: the SIM's own values so radii_of / board_from_engine score identically
        self.lanes = tuple(sim_eng.lanes) if sim_eng is not None else (3.5 / 18.0, 14.5 / 18.0)
        self.tower_range = float(getattr(sim_eng, "tower_range", 8.0))
        self.king_range = float(getattr(sim_eng, "king_range", 8.5))
        self.siege_sight = float(getattr(sim_eng, "siege_sight", 11.5))
        self.regulation = float(getattr(sim_eng, "regulation", 180.0))
        self.overtime = float(getattr(sim_eng, "overtime", 120.0))
        self.tiles_x = float(getattr(sim_eng, "tiles_x", 18.0))
        self.tiles_y = float(getattr(sim_eng, "tiles_y", 32.0))
        self.river_width = float(getattr(sim_eng, "river_width", 2.0))
        self.db = getattr(sim_eng, "db", None)
        self.outcome = None
        self.last_placement = None
        self.projectiles = []
        # --- NOT exported by the engine: honest empties (NOT_EXPORTED) ---
        self.zones, self.spells, self.spark_zones, self.vortices = [], [], [], []
        self.splash_events, self.rolls, self.arc_events, self.rage_zones = [], [], [], []
        self.ability_events, self._ability_pending = [], []
        self._banner, self._antenna = {}, {}
        self.feed = "engine"
        self.n_unmapped = self.n_deploying = 0

    def crowns(self, team: int) -> int:
        enemy = self.towers[1 - team]
        if not enemy[2].alive:
            return 3
        return sum(1 for tw in enemy if not tw.alive)


# ------------------------------------------------------------------------------------------------ frame -> view
_HP_SPECS = {}


def _spec_with_hp(spec, max_hp):
    """The engine names SPAWNED bodies after their parent card (a Skeleton Barrel's skeletons are 'SkeletonBalloon'
    with max_hp 81; the sim spec says 532), so the unit's HP bar (`u.hp / u.spec.hp` in render_frame) and
    `board_from_engine`'s hp_max must use the ENGINE's own max_hp. A per-(key, max_hp) spec copy does that."""
    mhp = float(max_hp or 0.0)
    if mhp <= 0.0 or abs(mhp - float(spec.hp or 0.0)) < 0.5:
        return spec
    k = (spec.key, mhp)
    if k not in _HP_SPECS:
        from dataclasses import replace
        _HP_SPECS[k] = replace(spec, hp=mhp)
    return _HP_SPECS[k]


def _mirror_fns(focus_side):
    mirror = (focus_side == 1)

    def xy(X, Y):
        if mirror:
            X, Y = 18000 - X, 32000 - Y
        return X / 18000.0, 1.0 - Y / 32000.0

    def team_of(side):
        return (1 - side) if mirror else side
    return xy, team_of


def view_engine_from_frame(frame, focus_side, spec_of, full=False, sim_eng=None, stats=None):
    """Engine observation frame -> EngineView in the focus side's local frame (focus = team 0 = bottom).

    Same mirror as L61.frame_to_engine. `full=True` marks the frame as a full observe (projectiles present);
    projectiles are read whenever the key exists either way."""
    xy, team_of = _mirror_fns(focus_side)
    stats = stats if stats is not None else {"names": collections.Counter(), "unmapped": collections.Counter()}
    towers = {0: [None, None, None], 1: [None, None, None]}
    king_kind = {}                                   # (team) -> kind of the '-1' king entity (12 inactive / 13 active)
    for e in frame["entities"]:
        if e[0] is not None and e[3] == "-1" and len(e) > 6:
            x, y = xy(int(e[1]), int(e[2]))
            if abs(x - 0.5) < 0.02:                  # the king sits on the centre column
                king_kind[team_of(int(e[0]))] = int(e[6])
    for side, typ, lane, X, Y, hp, mhp in frame["towers"]:
        tm = team_of(int(side))
        x, y = xy(int(X), int(Y))
        tw = tower_at(x, y, hp, mhp, typ == "king")
        if typ == "king":
            tw.active = (king_kind.get(tm, 13) == 13)  # measured: king kind 12 until activated, then 13
            towers[tm][2] = tw
        else:
            towers[tm][0 if x < 0.5 else 1] = tw
    for tm in (0, 1):                                # missing from the engine list = destroyed
        for i in range(3):
            if towers[tm][i] is None:
                ax, ay = ANCHORS[tm][i]
                towers[tm][i] = tower_at(ax, ay, 0.0, 1.0, i == 2)
    units, n_unmapped, n_deploying = [], 0, 0
    for e in frame["entities"]:
        side, X, Y, name, hp, mhp = e[:6]
        kind = e[6] if len(e) > 6 else -1
        if name == "-1" or hp <= 0:
            continue
        spec = spec_of(_SUBBODY.get((name, int(mhp)), name))
        stats["names"][name] += 1
        if spec is None:
            n_unmapped += 1
            stats["unmapped"][name] += 1
            spec = spec_of("__generic__")
        spec = _spec_with_hp(spec, mhp)
        x, y = xy(int(X), int(Y))
        deploying = kind in (12, 14)                 # L61 reading; measured for 9 cards w/ 1 s deploy (engine_view.md 1)
        n_deploying += int(deploying)
        u = ViewUnit(spec, team_of(int(side)), x, y, hp, deploying, kind, name)
        u.cloned = (name == "Clone")                 # measured: 17 'Clone' entities in batch_v2, every one max_hp 1
        units.append(u)
    el = frame["elixir"]
    elixir = [float(el[focus_side] or 0.0), float(el[1 - focus_side] or 0.0)]
    eng = EngineView(frame["tick"] * TICK_S, units, towers, elixir, sim_eng=sim_eng)
    eng.n_unmapped, eng.n_deploying = n_unmapped, n_deploying
    eng.feed = "engine_full" if (full or "projectiles" in frame) else "engine_compact"
    for p in frame.get("projectiles", []) or []:
        side, X, Y, TX, TY, name = p[:6]
        x, y = xy(int(X), int(Y))
        tx, ty = xy(int(TX), int(TY))
        if name == "-1":
            spec, label = None, "tower"
        else:
            spec = spec_of(name)
            label = spec.key if spec is not None else str(name).lower()
        radius = float(spec.spell_radius) if (spec is not None and spec.kind == "spell") else 0.0
        pierce = bool(getattr(spec, "rolls", False)) if spec is not None else False
        ground_only = bool(getattr(spec, "ground_only", False) or
                           (spec.kind != "spell" and not getattr(spec, "attacks_air", True))) if spec is not None else False
        eng.projectiles.append(ViewProjectile(x, y, tx, ty, team_of(int(side)), label, radius, pierce, ground_only, name))
    return eng


# ------------------------------------------------------------------------------------------------ raw full observe
class ViewZone:
    """A lingering area effect in sim_view's `zones` idiom (z.x, z.y, z.spec.spell_radius, z.left)."""
    __slots__ = ("x", "y", "spec", "left", "team", "name")

    def __init__(self, x, y, spec, left, team, name):
        self.x, self.y, self.spec, self.left, self.team, self.name = x, y, spec, left, team, name


def _ptr(v):
    try:
        return int(v, 16) if isinstance(v, str) else (int(v) if v is not None else 0)
    except (TypeError, ValueError):
        return 0


def _card_name(card_id):
    """The recorder's naming (replay_drive.card_name) when the sandbox package imports; else the raw id."""
    card_id = int(card_id)
    if card_id < 0:
        return str(card_id)
    try:
        sb = str(ROOT / "research" / "ext" / "cr-native-sandbox")
        if sb not in sys.path:
            sys.path.insert(0, sb)
        from native_core.card_catalog import observed_card
        from native_core.env import CARD_NAMES
        identity = observed_card(card_id)
        return CARD_NAMES.get(int(identity["base_card_id"]), str(identity["form_name"]))
    except Exception:                                     # noqa: BLE001 -- viewer never crashes on a name
        return str(card_id)


def observe_to_frame(state, card_name=None):
    """Raw bridge full observe (jni_bridge.cpp observe / API.md 10) -> the recorder's frame shape, without
    dropping anything: each recorder row gets the raw entity / effect dict appended as its last element."""
    card_name = card_name or _card_name
    ents = []
    for e in state.get("entities", []):
        name = e.get("name")
        if name is None:
            name = card_name(int(e.get("card_id", -1)))
        ents.append([int(e["side"]), int(e["x"]), int(e["y"]), name, int(e["hp"]), int(e["max_hp"]),
                     int(e.get("kind", -1)), e])
    players = {int(p["side"]): p for p in state.get("players", [])}
    frame = {"tick": int(state["tick"]),
             "elixir": [players.get(sd, {}).get("elixir_exact", players.get(sd, {}).get("elixir", 0.0)) for sd in (0, 1)],
             "entities": ents,
             "towers": [[int(t["side"]), t.get("type"), t.get("lane"), int(t["x"]), int(t["y"]), int(t["hp"]),
                         int(t["max_hp"])] for t in state.get("episode", {}).get("crown_towers", [])],
             "projectiles": [[int(q["side"]), int(q["x"]), int(q["y"]), int(q["target_x"]), int(q["target_y"]),
                              card_name(int(q["card_id"])), q] for q in state.get("projectiles", [])],
             "effects": [[int(q["side"]), int(q["x"]), int(q["y"]), card_name(int(q["card_id"])), q]
                         for q in state.get("effects", [])]}
    return frame


def view_engine_from_observe(state, focus_side, spec_of, sim_eng=None, stats=None, card_name=None):
    """Raw full observe -> EngineView with every per-entity field the bridge exports that the recorder dropped.

    Mappings and their standing (engine_view.md 8):
      target (attack component pointer)        -> u.target = the ViewUnit / Tower with that `id`   [exported; link overlay]
      event_timer_ms while kind in (12, 14)    -> u.deploy_left = ms / 1000                        [INFERRED, untested]
      attack_progress_ms > 0 with a target     -> u.attacking = True                               [INFERRED, untested]
      ability_state_code 10 pending / 11 casting -> eng._ability_pending ring, left = ability_pending_ms [docs name only]
      ability_state_code 2 ready               -> u.ability_left = charges (the [ABIL] tag)         [docs name only]
      level, behavior_state, pending_damage    -> kept on the unit; nothing in sim_view reads them
      non-projectile effects (vtable != projectile) -> eng.zones with the card's spell_radius     [code path only:
                                                  0 such effects in 23169 recorded full frames]
    """
    frame = observe_to_frame(state, card_name)
    eng = view_engine_from_frame(frame, focus_side, spec_of, full=True, sim_eng=sim_eng, stats=stats)
    eng.feed = "engine_observe"
    xy, team_of = _mirror_fns(focus_side)
    # view_engine_from_frame keeps entity order for the alive, non-tower rows -> re-associate the raw dicts
    raws = [e[7] for e in frame["entities"] if e[3] != "-1" and e[4] > 0]
    assert len(raws) == len(eng.units)
    by_id = {}
    for u, raw in zip(eng.units, raws):
        u.entity_id = int(raw.get("category", raw.get("entity_id", 0)) or 0)
        u.level = int(raw.get("level", 0) or 0)
        u.behavior_state = raw.get("behavior_state")
        u.pending_damage = int(raw.get("pending_damage") or 0)
        u.ability_state_code = int(raw.get("ability_state_code", -1))
        by_id[_ptr(raw.get("id"))] = u
        if u.deploy_left > 0 and raw.get("event_timer_ms") is not None:
            u.deploy_left = max(0.0, int(raw["event_timer_ms"]) / 1000.0)      # inferred: the deploy countdown
        if u.ability_state_code == 2 and int(raw.get("ability_charges_remaining", 0) or 0) > 0:
            u.ability_left = int(raw["ability_charges_remaining"])
        if u.ability_state_code in (10, 11):
            left = max(0, int(raw.get("ability_pending_ms") or 0)) / 1000.0
            eng._ability_pending.append((u.team, u, int(raw.get("ability_mana_cost") or 0), left,
                                         ABILITY_STATE_NAMES[u.ability_state_code]))
    # towers are entities too (card_id -1): map their raw id -> Tower object by position
    for e in frame["entities"]:
        if e[3] == "-1":
            x, y = xy(int(e[1]), int(e[2]))
            tm = team_of(int(e[0]))
            tw = min(eng.towers[tm], key=lambda t: (t.x - x) ** 2 + (t.y - y) ** 2)
            by_id[_ptr(e[7].get("id"))] = tw
    for u, raw in zip(eng.units, raws):
        tgt = _ptr(raw.get("target"))
        if tgt:
            u.target = by_id.get(tgt)                     # None = target outside the public entity set
            u.locked = u.target is not None
            if int(raw.get("attack_progress_ms") or 0) > 0 and u.target is not None:
                u.attacking = True
    # lingering areas: any 4M-series effect that is not a projectile
    proj_ids = {_ptr(q[6].get("id")) for q in frame["projectiles"]}
    for side, X, Y, name, raw in frame["effects"]:
        if _ptr(raw.get("id")) in proj_ids:
            continue
        spec = spec_of(name)
        if spec is None:
            eng.n_unmapped += 1
            continue
        x, y = xy(int(X), int(Y))
        eng.zones.append(ViewZone(x, y, spec, 0.0, team_of(int(side)), name))   # left unknown: no timer exported
    return eng


def _overlay_targets(img, eng, W):
    """Attack links (post-render): body -> its exported target. sim_view draws no target line of its own."""
    import cv2
    from clashrl.sim_view import _ASPECT, _HUD_TOP
    BH = int(W / _ASPECT)
    n = 0
    for u in eng.units:
        t = getattr(u, "target", None)
        if u.hp <= 0 or t is None or getattr(t, "hp", 0) <= 0:
            continue
        a = (int(u.x * W), _HUD_TOP + int(u.y * BH))
        b = (int(t.x * W), _HUD_TOP + int(t.y * BH))
        cv2.line(img, a, b, _TARGET_LINK, 1)
        n += 1
    return n


# ------------------------------------------------------------------------------------------------ plays + scoring
def _play_spec(entry, spec_of, db):
    """CardSpec for a driven play: the engine display name in `hand_before[hand_index]` (exact), else the slug."""
    hb, hi = entry.get("hand_before"), entry.get("hand_index")
    if hb and hi is not None and 0 <= int(hi) < len(hb):
        sp = spec_of(hb[int(hi)])
        if sp is not None:
            return sp
    k = L61.V1.key_base(str(entry.get("card", "")))
    if db is not None and db.get(k):
        try:
            from clashrl.sim.engine import build_spec
            return build_spec(db, k, 11)
        except Exception:                             # noqa: BLE001
            return None
    return None


def score_focus_play(eng, spec, x, y, t):
    """Exactly what sim_view._score_last_placement does, on the engine frame (import geometry_reward directly)."""
    from clashrl.geometry_reward import board_from_engine, placement_from_spec, score_placement
    eng.last_deploy[0] = (spec, x, y, t)
    kw = dict(siege_sight=eng.siege_sight, tower_range=eng.tower_range, king_range=eng.king_range)
    scores = score_placement(board_from_engine(eng, 0), placement_from_spec(spec, x, y, db=eng.db, **kw))
    eng.last_placement = dict(x=x, y=y, base=spec.base, kind=spec.kind, t=t, scores=scores)
    return eng.last_placement


def timeline(rec):
    """(tick, kind, frame) in tick order: play frames first at a tick, then the drift/full frames."""
    ev = [("drift", f) for f in rec.get("frames", [])] + [("play", f) for f in rec.get("play_frames", [])]
    ev.sort(key=lambda kf: (kf[1]["tick"], 0 if kf[0] == "play" else 1, kf[1].get("play_index", -1)))
    return ev


def plays_by_tick(rec):
    """Accepted driven plays from the log, keyed by engine tick (the play_frame tick when one exists)."""
    by_pi = {}
    for f in rec.get("play_frames", []):
        by_pi[int(f["play_index"])] = f
    out = collections.defaultdict(list)
    for e in rec["log"]:
        if "play_index" not in e or not e.get("accepted", False):
            continue
        pf = by_pi.get(int(e["play_index"]))
        tick = int(pf["tick"]) if pf is not None else int(e.get("engine_tick", e["tick"]))
        out[tick].append(e)
    out = dict(out)
    return out


def _overlay_plays(img, eng, marks, W, radii):
    """Post-render marks: opponent plays (orange diamond), focus plays when no readout is drawn, '?' for unmapped."""
    import cv2
    from clashrl.sim_view import _ASPECT, _HUD_TOP
    BH = int(W / _ASPECT)
    for m in marks:
        if not (0.0 <= eng.t - m["t"] <= PLAY_SHOW_S):
            continue
        c = (int(m["x"] * W), _HUD_TOP + int(m["y"] * BH))
        if m["team"] == 1:
            cv2.drawMarker(img, c, _OPP_MARK, cv2.MARKER_DIAMOND, 15, 2)
            col = _OPP_MARK
        else:
            if not (radii and eng.last_placement is not None):
                cv2.drawMarker(img, c, _ME_MARK, cv2.MARKER_SQUARE, 13, 1)
            col = _ME_MARK
        lab = m["label"] + ("?" if m["unmapped"] else "")
        cv2.putText(img, lab, (c[0] - 20, c[1] - 10), cv2.FONT_HERSHEY_PLAIN, 0.7,
                    _UNMAPPED if m["unmapped"] else col, 1)


def _overlay_tag(img, text, W):
    """Bottom strip under the elixir bars (rows H-12..H-2 are unused by render_frame)."""
    import cv2
    cv2.putText(img, text[:84], (8, img.shape[0] - 4), cv2.FONT_HERSHEY_PLAIN, 0.65, (90, 220, 255), 1)


# ------------------------------------------------------------------------------------------------ render a recording
def render_recording(path, focus_side, out_mp4, radii=True, width=460, fps=20, grid=True, stills=True,
                     max_frames=0, progress=True):
    import cv2
    from clashrl.sim_view import _ASPECT, _HUD_BOT, _HUD_TOP, render_frame
    L61.init_worker()
    env, spec_of, db = L61._W["env"], L61._W["spec_of"], L61._W["db"]
    acts = env.actions if grid else None
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    tag = rec.get("tag", Path(path).stem)
    xy, team_of = _mirror_fns(focus_side)
    ev = timeline(rec)
    plays = plays_by_tick(rec)
    if max_frames:
        ev = ev[:max_frames]
    H = int(width / _ASPECT) + _HUD_TOP + _HUD_BOT
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_mp4), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, H))
    png_dir = None
    if not writer.isOpened():
        writer = None
        png_dir = out_mp4.with_suffix("")
        png_dir.mkdir(parents=True, exist_ok=True)
        print(f"[engine-view] mp4v writer failed; writing PNG frames to {png_dir}")
    stats = {"names": collections.Counter(), "unmapped": collections.Counter()}
    marks, last_placement, handled = [], None, set()
    n_unmapped_plays = n_focus_scored = n_opp = 0
    t_render = 0.0
    n = 0
    still_paths = []
    still_ix = {int(len(ev) * 0.1): "early", int(len(ev) * 0.5): "mid", int(len(ev) * 0.9): "late"}
    want_readout = True
    note = NOTE_TAG
    for i, (kind, fr) in enumerate(ev):
        eng = view_engine_from_frame(fr, focus_side, spec_of, full=(kind == "play" or "projectiles" in fr),
                                     sim_eng=env.eng, stats=stats)
        tick = int(fr["tick"])
        # plays due at this frame: a play frame takes its own play_index; any other frame takes every not-yet-handled
        # play whose tick is <= this tick and within 40 ticks (the full recording has a frame at every play tick)
        if kind == "play":
            due = [e for e in plays.get(tick, []) if int(e["play_index"]) == int(fr["play_index"])]
        else:
            due = [e for t_ in plays if tick - 40 <= t_ <= tick for e in plays[t_] if int(e["play_index"]) not in handled]
        for e in due:
            handled.add(int(e["play_index"]))
            spec = _play_spec(e, spec_of, db)
            team = team_of(int(e["side"]))
            x, y = xy(int(e["x"]), int(e["y"]))
            unmapped = spec is None
            n_unmapped_plays += int(unmapped)
            label = (spec.key if spec is not None else str(e.get("card", "?")))
            marks.append(dict(t=eng.t, x=x, y=y, team=team, label=label[:12], unmapped=unmapped))
            if team == 0 and spec is not None and radii:
                last_placement = score_focus_play(eng, spec, x, y, eng.t)
                n_focus_scored += 1
            elif team == 1:
                n_opp += 1
        if last_placement is not None and eng.t - last_placement["t"] <= PLAY_SHOW_S:
            eng.last_placement = last_placement
        if i == len(ev) - 1 and rec.get("final"):
            eng.done = True                                    # the recording's own verdict on its last frame
            eng.outcome = "%s crowns %s" % (rec["final"].get("outcome"), rec["final"].get("crowns"))
        t0 = time.perf_counter()
        img = render_frame(eng, width, note, acts, radii=radii)
        t_render += time.perf_counter() - t0
        _overlay_plays(img, eng, marks, width, radii)
        _overlay_targets(img, eng, width)
        _overlay_tag(img, f"{tag} s{focus_side} {eng.feed} tick {tick} | {NOT_EXPORTED[12:]}", width)
        marks = [m for m in marks if eng.t - m["t"] <= PLAY_SHOW_S]
        if writer is not None:
            writer.write(img)
        else:
            cv2.imwrite(str(png_dir / f"{n:06d}.png"), img)
        if stills:
            readout_up = radii and eng.last_placement is not None and eng.t - eng.last_placement["t"] <= PLAY_SHOW_S
            if i in still_ix:
                p = out_mp4.with_name(f"{out_mp4.stem}_{still_ix[i]}_tick{tick}.png")
                cv2.imwrite(str(p), img)
                still_paths.append(str(p))
            if want_readout and readout_up and i >= len(ev) * 0.3:
                p = out_mp4.with_name(f"{out_mp4.stem}_readout_tick{tick}.png")
                cv2.imwrite(str(p), img)
                still_paths.append(str(p))
                want_readout = False
        n += 1
        if progress and n % 500 == 0:
            print(f"[engine-view] {n}/{len(ev)} frames, {1000 * t_render / n:.1f} ms/frame", flush=True)
    if writer is not None:
        writer.release()
    summary = dict(tag=tag, focus_side=focus_side, frames=n, ms_per_frame=round(1000 * t_render / max(1, n), 2),
                   out=str(out_mp4 if writer is not None else png_dir), stills=still_paths, fps=fps,
                   focus_plays_scored=n_focus_scored, opponent_plays=n_opp, unmapped_plays=n_unmapped_plays,
                   unmapped_entity_names=dict(stats["unmapped"]), entity_names=dict(stats["names"].most_common()),
                   record_full=bool(rec.get("record_full")), n_play_frames=len(rec.get("play_frames", [])),
                   n_drift_frames=len(rec.get("frames", [])))
    print(json.dumps({k: v for k, v in summary.items() if k != "entity_names"}, indent=1))
    return summary


# ------------------------------------------------------------------------------------------------ --check
def check(path, focus_side=1, width=460):
    import cv2
    from clashrl.sim_view import _ASPECT, _HUD_TOP, _TEAM, render_frame
    L61.init_worker()
    env, spec_of = L61._W["env"], L61._W["spec_of"]
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    ev = timeline(rec)
    BH = int(width / _ASPECT)

    def px(nx, ny):
        return int(nx * width), _HUD_TOP + int(ny * BH)

    res = {}
    # (a) tower pixel positions vs the sim's own reset anchors
    env.reset()
    sim_px = {tm: [px(tw.x, tw.y) for tw in env.eng.towers[tm]] for tm in (0, 1)}
    fr0 = ev[0][1]
    e0 = view_engine_from_frame(fr0, focus_side, spec_of, sim_eng=env.eng)
    eng_px = {tm: [px(tw.x, tw.y) for tw in e0.towers[tm]] for tm in (0, 1)}
    err = max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for tm in (0, 1) for a, b in zip(sim_px[tm], eng_px[tm]))
    res["a_tower_px_max_err"] = int(err)
    res["a_sim_px"] = sim_px
    res["a_engine_px"] = eng_px
    assert err == 0, f"tower pixel mismatch {err}"
    # (b) mirror round-trip: focus_side=1 -> focus towers at the BOTTOM (larger y pixel), engine side 1 at Y>16000
    e1 = view_engine_from_frame(fr0, 1, spec_of, sim_eng=env.eng)
    e0b = view_engine_from_frame(fr0, 0, spec_of, sim_eng=env.eng)
    img1 = render_frame(e1, width, "", None)
    y_focus = min(tw.y for tw in e1.towers[0])
    y_enemy = max(tw.y for tw in e1.towers[1])
    assert y_focus > y_enemy, "focus towers not at the bottom"
    side1_Y = [t[4] for t in fr0["towers"] if t[0] == 1]
    assert min(side1_Y) > 16000, "engine side 1 is not the high-row side in this recording"
    # the pixel check: team-0 colour must appear only in the lower half of the board, team-1 only in the upper
    def rows_with(img, col):
        sel = np.all(img == np.array(col, np.uint8), axis=2)
        ys = np.nonzero(sel.any(axis=1))[0]
        return (int(ys.min()), int(ys.max())) if len(ys) else None
    r0, r1 = rows_with(img1[_HUD_TOP:_HUD_TOP + BH], _TEAM[0]), rows_with(img1[_HUD_TOP:_HUD_TOP + BH], _TEAM[1])
    res["b_team0_rows"] = r0
    res["b_team1_rows"] = r1
    assert r0 and r1 and r0[0] > BH * 0.5 and r1[1] < BH * 0.5, "mirror pixel check failed"
    # and the two focus choices are exact mirrors of each other
    for tm in (0, 1):
        for ia, ib in ((0, 1), (1, 0), (2, 2)):    # the mirror swaps left/right princess slots
            a, b = e1.towers[tm][ia], e0b.towers[1 - tm][ib]
            assert abs(a.x - (1 - b.x)) < 1e-9 and abs(a.y - (1 - b.y)) < 1e-9, (tm, ia, a.x, a.y, b.x, b.y)
    res["b_mirror_exact"] = True
    # (c) radii overlay changes pixels on a frame with units on it
    fr = next(f for k, f in ev if sum(1 for e in f["entities"] if e[3] != "-1" and e[4] > 0) >= 3)
    e = view_engine_from_frame(fr, focus_side, spec_of, sim_eng=env.eng)
    a = render_frame(e, width, "", None, radii=False).astype(np.int32)
    b = render_frame(e, width, "", None, radii=True).astype(np.int32)
    res["c_radii_changed_px"] = int((np.abs(a - b).sum(axis=2) > 0).sum())
    res["c_tick"] = int(fr["tick"])
    assert res["c_radii_changed_px"] > 0
    # (d) a scored placement: annulus + text change pixels (the first accepted focus play with a spec)
    xy, team_of = _mirror_fns(focus_side)
    plays = plays_by_tick(rec)
    frames_at = {}
    for k, f in ev:
        frames_at.setdefault(int(f["tick"]), f)
    done = False
    for tick in sorted(plays):
        for pe in plays[tick]:
            if team_of(int(pe["side"])) != 0:
                continue
            spec = _play_spec(pe, spec_of, L61._W["db"])
            if spec is None or tick not in frames_at:
                continue
            f = frames_at[tick]
            e = view_engine_from_frame(f, focus_side, spec_of, sim_eng=env.eng)
            base = render_frame(e, width, "", None, radii=True).astype(np.int32)
            x, y = xy(int(pe["x"]), int(pe["y"]))
            lp = score_focus_play(e, spec, x, y, e.t)
            scored = render_frame(e, width, "", None, radii=True).astype(np.int32)
            sc = lp["scores"]
            has_band = bool(sc.get("threat_x") is not None and (sc.get("p1_band_hi") or 0) > (sc.get("p1_band_lo") or 0))
            rec_d = dict(tick=tick, card=spec.key, kind=spec.kind, x=round(x, 4), y=round(y, 4),
                         threat=sc.get("threat_base"), band=(sc.get("p1_band_lo"), sc.get("p1_band_hi")),
                         changed_px=int((np.abs(base - scored).sum(axis=2) > 0).sum()),
                         terms={k: round(v, 3) for k, v in sc.items() if isinstance(v, (int, float)) and abs(v) > 1e-9})
            assert rec_d["changed_px"] > 0
            if not done:
                res["d_first_play"] = rec_d
                done = True
            if has_band and spec.kind == "building":
                res["d_annulus_play"] = rec_d
                break
        if "d_annulus_play" in res:
            break
    res["d_placement_changed_px"] = res.get("d_annulus_play", res.get("d_first_play", {})).get("changed_px")
    assert done, "no scorable focus play found"
    # (e) every attribute render_frame reads via getattr is really present (no silent default masking a bug)
    for attr in ("t", "units", "towers", "elixir", "zones", "spells", "spark_zones", "projectiles", "lanes", "last_deploy",
                 "outcome", "regulation", "overtime", "siege_sight", "tower_range", "king_range", "last_placement",
                 "elixir_rate", "vortices", "splash_events", "rolls", "arc_events", "rage_zones", "ability_events",
                 "_ability_pending", "_banner", "_antenna", "done", "crowns", "db"):
        assert hasattr(e, attr), attr
    u_attrs = ("stun_left", "slow_left", "shield_left", "invis_left", "flying_left", "deploy_left", "dash_left", "souls",
               "ability_active_s", "ability_left", "attacking", "cloned", "taunt_ref", "target", "spec", "team", "x", "y", "hp")
    for attr in u_attrs:
        assert all(hasattr(u, attr) for u in e.units), attr
    res["e_attrs_present"] = True
    # (f) the raw-observe path: a SYNTHETIC full observe built from a recorded play frame with the per-entity
    # fields the bridge exports but the recorder dropped (target, event_timer_ms, attack_progress_ms,
    # ability_state_code / ability_pending_ms) and one non-projectile effect. Exercises the code path only;
    # the field SEMANTICS are not verified here (engine_view.md 8).
    pf = next(f for _, f in ev if "projectiles" in f and len(f["entities"]) >= 8
              and any(e[6] in (12, 14) and e[3] != "-1" for e in f["entities"])
              and any(e[6] == 15 and e[3] != "-1" for e in f["entities"]))
    base = view_engine_from_frame(pf, focus_side, spec_of, sim_eng=env.eng)
    img_base = render_frame(base, width, NOTE_TAG, None, radii=True)
    ents, ids = [], {}
    for i, e in enumerate(pf["entities"]):
        d = {"id": "0x%x" % (0x7f00 + i), "category": 5000000 + i, "kind": e[6], "side": e[0], "x": e[1], "y": e[2],
             "card_id": -1 if e[3] == "-1" else 26000000 + i, "level": 11, "hp": e[4], "max_hp": e[5], "name": e[3],
             "behavior_state": 0, "ability_slot": 0, "ability_state_code": 1, "ability_available": False,
             "ability_cooldown_remaining_ms": -1, "ability_charges_remaining": -1, "ability_pending_ms": -1,
             "ability_mana_cost": -1, "pending_damage": 0, "event_timer_ms": 0, "target": None,
             "attack_progress_ms": 0, "attack_load_timer_ms": 0, "movement_direction_x": 0, "movement_direction_y": 0,
             "path_nodes": None}
        ents.append(d)
        ids.setdefault((e[0], e[3] == "-1", e[6]), []).append(d)
    dep = next(d for d in ents if d["card_id"] != -1 and d["kind"] in (12, 14) and d["hp"] > 0)
    dep["event_timer_ms"] = 600
    act = next(d for d in ents if d["card_id"] != -1 and d["kind"] == 15 and d["hp"] > 0 and d is not dep)
    enemy_tw = next(d for d in ents if d["card_id"] == -1 and d["side"] != act["side"])
    act["target"], act["attack_progress_ms"] = enemy_tw["id"], 250
    act["ability_state_code"], act["ability_pending_ms"], act["ability_mana_cost"] = 11, 300, 1
    state = {"tick": pf["tick"], "players": [{"side": sd, "elixir_exact": pf["elixir"][sd]} for sd in (0, 1)],
             "entities": ents,
             "episode": {"crown_towers": [dict(side=t[0], type=t[1], lane=t[2], x=t[3], y=t[4], hp=t[5], max_hp=t[6])
                                          for t in pf["towers"]]},
             "projectiles": [{"id": "0x9%03x" % i, "side": q[0], "x": q[1], "y": q[2], "target_x": q[3], "target_y": q[4],
                              "card_id": 27000000 + i, "vtable_rva": "0x1"} for i, q in enumerate(pf["projectiles"])],
             "effects": [{"id": "0x9%03x" % i, "side": q[0], "x": q[1], "y": q[2], "card_id": 27000000 + i,
                          "vtable_rva": "0x1"} for i, q in enumerate(pf["projectiles"])]
                        + [{"id": "0xa000", "side": act["side"], "x": act["x"], "y": act["y"], "card_id": 28000001,
                            "vtable_rva": "0x2"}]}
    pnames = {27000000 + i: q[5] for i, q in enumerate(pf["projectiles"])}
    pnames[28000001] = "Poison"

    def cn(cid):
        cid = int(cid)
        return "-1" if cid < 0 else pnames.get(cid, next((d["name"] for d in ents if d["card_id"] == cid), str(cid)))

    obs = view_engine_from_observe(state, focus_side, spec_of, sim_eng=env.eng, card_name=cn)
    assert obs.feed == "engine_observe"
    assert len(obs.units) == len(base.units)
    u_dep = next(u for u in obs.units if u.name == dep["name"] and abs(u.deploy_left - 0.6) < 1e-9)
    u_act = next(u for u in obs.units if u.entity_id == act["category"])
    assert u_act.target is not None and getattr(u_act.target, "king", None) is not None, "target -> a Tower"
    assert u_act.attacking and u_act.locked
    assert len(obs._ability_pending) == 1 and abs(obs._ability_pending[0][3] - 0.3) < 1e-9
    assert len(obs.zones) == 1 and obs.zones[0].spec.key == "poison"
    assert len(obs.projectiles) == len(pf["projectiles"])
    img_obs = render_frame(obs, width, NOTE_TAG, None, radii=True)
    n_links = _overlay_targets(img_obs, obs, width)
    assert n_links == 1
    res["f_observe_tick"] = pf["tick"]
    res["f_observe_changed_px"] = int((np.abs(img_obs.astype(int) - img_base.astype(int)).sum(axis=2) > 0).sum())
    res["f_observe_fields"] = dict(deploy_left=u_dep.deploy_left, target=type(u_act.target).__name__,
                                   attacking=u_act.attacking, ability_pending=obs._ability_pending[0][3:],
                                   zone=(obs.zones[0].name, obs.zones[0].spec.spell_radius), links=n_links)
    assert res["f_observe_changed_px"] > 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    still = OUT_DIR / ("%s_s%d_observe_SYNTHETIC_tick%d.png" % (Path(path).stem.replace("replay_", ""), focus_side, pf["tick"]))
    cv2.imwrite(str(still), img_obs)
    res["f_observe_still"] = str(still)
    print(json.dumps(res, indent=1, default=str))
    return res


# ------------------------------------------------------------------------------------------------ --ranges
def measure_ranges(path, shooters=("Tesla", "Cannon", "Xbow", "Musketeer", "IceWizard", "-1"), idle_ticks=40):
    """First-shot firing range from a record_full recording: a projectile is a NEW shot when it is within 1 tile of a
    same-side shooter of its name (towers for '-1') and that shooter had no shot in the previous `idle_ticks` ticks.
    Range = shooter -> nearest enemy body to (target_x, target_y) at that tick, in tiles (1000 units)."""
    from clashrl.geometry_reward import radii_of
    L61.init_worker()
    spec_of = L61._W["spec_of"]
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    F = rec["frames"]
    assert rec.get("record_full"), "needs a record_full recording"
    out = {}
    for name in shooters:
        last_shot = {}                              # shooter key -> last tick it fired
        first = []                                  # (tick, dist_to_target_body, dist_to_tx_ty, shooter, target name)
        for f in F:
            tick = f["tick"]
            ents = f["entities"]
            for p in f.get("projectiles", []):
                side, X, Y, TX, TY, pname = p[:6]
                if pname != name:
                    continue
                if name == "-1":
                    cands = [(t[3], t[4], f"{t[0]}:{t[1]}:{t[2]}:{t[1]}") for t in f["towers"] if t[0] == side]
                else:
                    cands = [(e[1], e[2], f"{e[0]}:{e[3]}:{e[1]}:{e[2]}") for e in ents if e[0] == side and e[3] == name]
                if not cands:
                    continue
                sx, sy, sk = min(cands, key=lambda c: (c[0] - X) ** 2 + (c[1] - Y) ** 2)
                if ((sx - X) ** 2 + (sy - Y) ** 2) ** 0.5 > 1200:
                    continue                        # already in flight, not a new shot
                # a body's key changes as it moves: key troops by side+name only, buildings/towers by position
                key = sk if name in ("-1", "Tesla", "Cannon", "Xbow") else f"{side}:{name}"
                idle = (tick - last_shot.get(key, -10 ** 9)) > idle_ticks
                last_shot[key] = tick
                if not idle:
                    continue
                enemies = [e for e in ents if e[0] != side and e[4] > 0]
                if not enemies:
                    continue
                tgt = min(enemies, key=lambda e: (e[1] - TX) ** 2 + (e[2] - TY) ** 2)
                d_body = ((tgt[1] - sx) ** 2 + (tgt[2] - sy) ** 2) ** 0.5 / 1000.0
                d_txy = ((TX - sx) ** 2 + (TY - sy) ** 2) ** 0.5 / 1000.0
                tsp = spec_of(tgt[3]) if tgt[3] != "-1" else None
                r_t = 1.5 if tgt[3] == "-1" else float(getattr(tsp, "radius", 0.5) or 0.5)   # sim hitbox of the target
                first.append((tick, round(d_body, 2), round(d_txy, 2), key, tgt[3], int(tgt[3] == "-1"), round(d_body - r_t, 2)))
        spec = spec_of(name) if name != "-1" else None
        if name == "-1":
            table = dict(princess=radii_of(tower_at(0.2, 0.8, 1, 1, False)), king=radii_of(tower_at(0.5, 0.9, 1, 1, True)))
        else:
            table = radii_of(spec) if spec is not None else None
        d = np.array([x[1] for x in first]) if first else np.zeros(0)
        d2 = np.array([x[2] for x in first]) if first else np.zeros(0)
        troop_only = np.array([x[1] for x in first if not x[5]]) if first else np.zeros(0)
        d_edge = np.array([x[6] for x in first]) if first else np.zeros(0)
        out[name] = dict(n_first_shots=len(first),
                         d_body_tiles=dict(max=float(d.max()) if len(d) else None, p90=float(np.percentile(d, 90)) if len(d) else None,
                                           median=float(np.median(d)) if len(d) else None, min=float(d.min()) if len(d) else None),
                         d_body_troop_targets=dict(n=int(len(troop_only)), max=float(troop_only.max()) if len(troop_only) else None,
                                                   p90=float(np.percentile(troop_only, 90)) if len(troop_only) else None,
                                                   median=float(np.median(troop_only)) if len(troop_only) else None),
                         d_txy_tiles=dict(max=float(d2.max()) if len(d2) else None, median=float(np.median(d2)) if len(d2) else None),
                         d_edge_tiles=dict(max=float(d_edge.max()) if len(d_edge) else None, p90=float(np.percentile(d_edge, 90)) if len(d_edge) else None,
                                           median=float(np.median(d_edge)) if len(d_edge) else None),
                         radii_of=table, sim_key=(spec.key if spec is not None else "tower"),
                         n_shots_total=sum(1 for f in F for p in f.get("projectiles", []) if p[5] == name),
                         top_first_shots=sorted(first, key=lambda x: -x[1])[:6], first_shots=first[:8])
    out["Tesla_hitscan"] = tesla_hitscan(F, spec_of)
    print(json.dumps(out, indent=1, default=str))
    return out


def tesla_hitscan(F, spec_of):
    """Tesla emits NO projectile (0 in 5268 full frames): read its reach from enemy hp-drops that equal its per-hit
    damage (sim table: dps * hit period = 220 at level 11, and 220 is the engine's own value) while a Tesla exists."""
    from clashrl.geometry_reward import radii_of
    sp = spec_of("Tesla")
    hit = round(float(sp.dps) * 1.1)                       # 200 dps * 1.1 s hit speed = 220
    drops, prev = [], None
    for f in F:
        if prev is not None:
            teslas = [e for e in f["entities"] if e[3] == "Tesla"]
            if teslas:
                pe = collections.defaultdict(list)
                for e in prev["entities"]:
                    if e[3] != "-1":
                        pe[(e[0], e[3])].append(e)
                for e in f["entities"]:
                    if e[3] == "-1" or not pe.get((e[0], e[3])):
                        continue
                    q = min(pe[(e[0], e[3])], key=lambda c: (c[1] - e[1]) ** 2 + (c[2] - e[2]) ** 2)
                    if q[4] - e[4] == hit:
                        for t in teslas:
                            if t[0] != e[0]:
                                d = ((t[1] - e[1]) ** 2 + (t[2] - e[2]) ** 2) ** 0.5 / 1000.0
                                r_t = float(getattr(spec_of(e[3]), "radius", 0.5) or 0.5)
                                drops.append((f["tick"], e[3], round(d, 2), round(d - r_t, 2), t[6]))
        prev = f
    d = np.array([x[2] for x in drops]) if drops else np.zeros(0)
    de = np.array([x[3] for x in drops]) if drops else np.zeros(0)
    return dict(method="hp-drop == %d while a Tesla exists (no Tesla projectile in the recording)" % hit, n=len(drops),
                d_body_tiles=dict(max=float(d.max()) if len(d) else None, p90=float(np.percentile(d, 90)) if len(d) else None,
                                  median=float(np.median(d)) if len(d) else None),
                d_edge_tiles=dict(max=float(de.max()) if len(de) else None, p90=float(np.percentile(de, 90)) if len(de) else None),
                tesla_kinds=dict(collections.Counter(x[4] for x in drops)), targets=dict(collections.Counter(x[1] for x in drops)),
                radii_of=radii_of(sp), top=sorted(drops, key=lambda x: -x[2])[:5])


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--focus", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--radii", action="store_true")
    ap.add_argument("--no-grid", action="store_true")
    ap.add_argument("--width", type=int, default=460)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ranges", action="store_true")
    ap.add_argument("--idle", type=int, default=40)
    args = ap.parse_args()
    if args.check:
        check(args.rec, args.focus, args.width)
        return
    if args.ranges:
        measure_ranges(args.rec, idle_ticks=args.idle)
        return
    out = args.out or str(OUT_DIR / (Path(args.rec).stem + f"_s{args.focus}.mp4"))
    render_recording(args.rec, args.focus, out, radii=args.radii, width=args.width, fps=args.fps,
                     grid=not args.no_grid, max_frames=args.max_frames)


if __name__ == "__main__":
    main()
