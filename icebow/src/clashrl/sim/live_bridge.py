"""LIVE -> SimEngine bridge: reconstruct a searchable engine state from what the screen shows.

Rollout search works by CLONING a `SimEngine` and rolling it forward. Live has no engine -- only
detections -- so this module builds one. It is the missing piece HANDOFF named first when it ruled
live search out:

    "There is no detector -> SimEngine bridge, per-unit HP is unavailable, there is no opponent
     deck/hand model, and ~80 per-unit fields are unobservable. On top of that a quarter-tile
     position error costs 62% of the search's gain and the damage SATURATES there."

/!\\ READ THAT BEFORE TRUSTING ANY OUTPUT OF THIS MODULE. The ceiling is measured at ~38% of the
sim gain from POSITION ERROR ALONE, and the other unobservables compound on top. The owner accepted
that ceiling deliberately ("a gain is a gain"). This module's job is to make the capped gain
reachable AND to make the size of the cap measurable -- not to pretend the gap is closed.

WHAT IS OBSERVED, WHAT IS ASSUMED
---------------------------------
observed   unit identity (detector class -> card key), unit position (frame -> board), which
           towers are alive, own hand + next card, own elixir, match clock
ASSUMED    per-unit HP          -> spec maximum. Live cannot read troop HP; `troop_hp.py` covers
                                   only a few large bodies. A half-dead Giant reads as full.
ASSUMED    unit facing/target   -> the engine re-acquires on its own from position
ASSUMED    deploy/charge state  -> treated as fully deployed and idle
ASSUMED    opponent hand        -> uniform over their DETECTED deck (deck_detect), or the meta
                                   pool if no deck is known. Their cycle is unobservable.
ASSUMED    opponent elixir      -> `opponent_elixir.py`'s estimate, which is itself inferred
UNMODELLED shields, buffs, status timers, ability cooldowns, spawner timers -- the ~80 fields

Every assumption above BIASES SEARCH TOWARD OPTIMISM about enemy bodies (full HP) and toward
IGNORANCE about their hand. Both push the same way: search will under-rate defence.

VALIDATION
----------
`reconstruction_error()` runs the bridge against a state where ground truth EXISTS -- a live sim
match -- by rebuilding the engine from what a detector would have seen and diffing it against the
real one. That is the only honest way to size the gap, because in live play there is nothing to
diff against.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .engine import SimEngine, Unit, build_spec, _TILES_X, _TILES_Y


# Detector classes that are not troops/buildings and must never become Units.
_NON_BODY = {"", "none", "unknown", "background", "tower", "king_tower", "princess_tower"}


def _clean_key(name: str) -> str:
    """Detector class name -> card KB key. detect_classes.yaml already names them after KB keys."""
    return str(name or "").strip().lower().replace(" ", "_").replace("-", "_")


def tracks_to_bodies(db, tracks: Sequence[Any], actions, level: int = 11,
                     own_team: int = 0, frame=None, cfg=None,
                     drops: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """Normalise detector tracks into `{key, team, x, y}` board-space records.

    `tracks` items may be dicts or tuples; we accept either rather than couple this module to one
    tracker's shape, because `enemy_tracks` is a passthrough whose contract has already gone
    silently inert once (HANDOFF: the `with_base` TypeError).
    """
    # Pass `drops` to learn WHY tracks were rejected. Without it a zero-body result is
    # indistinguishable from "the detector saw nothing", and those need completely different
    # fixes -- exactly the ambiguity that left live search inert twice.
    # RESOLVE THE CONVERTER ONCE, LOUDLY. `frame_to_board` lives on BoardWarp, NOT on
    # ActionSpace -- calling it on the ActionSpace raises AttributeError, and a broad
    # `except: continue` around the per-track call turned that ONE structural mistake into 49
    # silent per-track drops every decision. MEASURED in a live run: seen=49,
    # frame_to_board_failed=49. A missing converter is a configuration error and is reported as
    # one, not smeared across every track.
    conv = getattr(actions, "frame_to_board", None)
    if conv is None:
        conv = getattr(getattr(actions, "warp", None), "frame_to_board", None)
    if conv is None:
        if drops is not None:
            drops["NO_frame_to_board_on_actions"] = drops.get("NO_frame_to_board_on_actions", 0) + 1
        return []
    out: List[Dict[str, Any]] = []
    tracks = list(tracks or ())
    def _drop(reason: str) -> None:
        if drops is not None:
            drops[reason] = drops.get(reason, 0) + 1
    if drops is not None:
        drops["seen"] = drops.get("seen", 0) + len(tracks)
    for tr in tracks:
        if isinstance(tr, dict):
            name = tr.get("base") or tr.get("cls") or tr.get("label") or ""
            fx, fy = tr.get("x"), tr.get("y")
            team = int(tr.get("team", 1 - own_team))
        else:
            # THE TRACKER'S REAL FORMAT IS (x, y, ..., base) -- NOT (name, x, y). Assuming the
            # latter silently mangled every track: for the string "knight" it read tr[0..2] as
            # 'k','n','i', produced no body, and the caller's min_bodies guard skipped every
            # decision. That is how live search shipped inert twice.
            # Callers must pass enemy_tracks(..., with_base=True); without it there is no identity
            # at index 4 and the track is correctly dropped rather than guessed at.
            try:
                fx, fy = float(tr[0]), float(tr[1])
                name = str(tr[4]) if len(tr) > 4 and tr[4] else ""
            except Exception:                                  # noqa: BLE001
                _drop("bad_tuple")
                continue
            team = 1 - own_team
        key = _clean_key(name)
        if key in _NON_BODY or fx is None or fy is None:
            _drop("no_identity" if key in _NON_BODY else "no_coords")
            continue
        # /!\ build_spec DOES NOT RAISE on an unknown key -- it returns a DEFAULT 300-hp troop.
        # A mislabelled or novel detector class would therefore inject a PHANTOM BODY into every
        # rollout, and search would plan around a unit that does not exist. Membership in the card
        # DB is the real check; the try/except alone was not one.
        if key not in db.cards:
            _drop("not_a_card:" + key[:18])
            continue
        try:
            spec = build_spec(db, key, level)
        except Exception:                                      # noqa: BLE001
            _drop("build_spec_failed")
            continue
        if spec.kind == "spell":
            _drop("is_spell")
            continue
        try:
            bx, by = conv(float(fx), float(fy))
        except Exception:                                      # noqa: BLE001
            _drop("frame_to_board_failed")
            continue
        # READ THE HEALTH BAR when a frame and a box are available. `troop_hp` has existed as a
        # scaffold the whole time -- "measure the GREEN filled fraction of that bar ... multiply by
        # the unit's max HP" -- and the bridge simply never called it, which is what made every
        # body enter at spec maximum and overstate enemy hitpoints by +77%.
        # None means NO BAR, which correctly means UNDAMAGED: Clash Royale only draws the bar once
        # a unit has taken damage. So None -> 1.0 is the right default, not a fallback.
        hp_frac = None
        box = tr.get("box") if isinstance(tr, dict) else None
        if frame is not None and box is not None:
            try:
                from ..troop_hp import read_hp_fraction
                hp_frac = read_hp_fraction(frame, tuple(box), cfg)
            except Exception:                                  # noqa: BLE001
                hp_frac = None                                 # reader unavailable -> assume full
        out.append({"key": key, "spec": spec, "team": int(team),
                    "x": float(bx), "y": float(by),
                    "hp_frac": (None if hp_frac is None
                                else float(min(1.0, max(0.02, hp_frac))))})
    return out


def build_engine(cfg, db, rng, bodies: Sequence[Dict[str, Any]],
                 elixir: Tuple[float, float] = (5.0, 5.0),
                 t: float = 0.0,
                 towers_alive: Optional[Dict[int, Sequence[bool]]] = None,
                 tower_hp: Optional[Dict[int, Sequence[float]]] = None,
                 level: int = 11) -> SimEngine:
    """Build a SimEngine populated from observed bodies. Returns an engine search can clone.

    /!\\ Every body enters at FULL SPEC HP -- see the module docstring. This is the single largest
    modelled inaccuracy and it systematically over-states enemy defence.
    """
    eng = SimEngine(cfg, db, rng)
    eng.reset()
    eng.units.clear()
    for b in bodies:
        _f = b.get("hp_frac")
        _hp = float(b["spec"].hp) * (1.0 if _f is None else float(_f))
        u = Unit(spec=b["spec"], team=int(b["team"]),
                 x=float(b["x"]), y=float(b["y"]), hp=_hp)
        u.deploy_left = 0.0            # already on the field: it was SEEN, so it has landed
        eng.units.append(u)
    try:
        eng.elixir[0] = float(elixir[0])
        eng.elixir[1] = float(elixir[1])
    except Exception:                                          # noqa: BLE001
        pass
    eng.t = float(t)
    if towers_alive:
        for team, flags in towers_alive.items():
            for tw, alive in zip(eng.towers.get(int(team), []), flags):
                if not alive:
                    tw.alive = False
                    tw.hp = 0.0
    if tower_hp:
        for team, hps in tower_hp.items():
            for tw, hp in zip(eng.towers.get(int(team), []), hps):
                if hp is not None and hp > 0:
                    tw.hp = min(float(tw.max_hp), float(hp))
    return eng


# ------------------------------------------------------------------ validation against ground truth

def observe_as_detector(eng: SimEngine, own_team: int = 0,
                        drop: float = 0.0, pos_sigma: float = 0.0,
                        rng=None, read_hp: bool = False,
                        hp_err: float = 0.0) -> List[Dict[str, Any]]:
    """What a PERFECT-identity detector would report for this engine.

    Models the two live losses that are measurable: missed bodies (`drop`) and position error
    (`pos_sigma`, in TILES). HP loss is not modelled here because the bridge discards HP entirely
    -- that error is total by construction, not a parameter.
    """
    import random as _r
    rng = rng or _r.Random(0)
    out = []
    for u in eng.units:
        if u.hp <= 0:
            continue
        if drop > 0.0 and rng.random() < drop:
            continue
        x, y = u.x, u.y
        if pos_sigma > 0.0:
            x += rng.gauss(0.0, pos_sigma) / _TILES_X
            y += rng.gauss(0.0, pos_sigma) / _TILES_Y
        frac = None
        if read_hp:
            frac = max(0.02, min(1.0, u.hp / max(1e-6, u.spec.hp)))
            if hp_err > 0.0:                                   # bar-reading error, +- hp_err
                frac = max(0.02, min(1.0, frac * (1.0 + rng.uniform(-hp_err, hp_err))))
        out.append({"key": u.spec.base, "spec": u.spec, "team": int(u.team),
                    "x": float(x), "y": float(y), "hp_frac": frac})
    return out


def reconstruction_error(truth: SimEngine, rebuilt: SimEngine) -> Dict[str, float]:
    """Diff a rebuilt engine against the real one. The honest measure of what the bridge loses."""
    tl = [u for u in truth.units if u.hp > 0]
    rl = [u for u in rebuilt.units if u.hp > 0]
    hp_true = sum(u.hp for u in tl)
    hp_rebuilt = sum(u.hp for u in rl)
    # nearest-neighbour position error over same-key bodies
    errs = []
    pool = list(rl)
    for u in tl:
        cands = [v for v in pool if v.spec.base == u.spec.base]
        if not cands:
            continue
        v = min(cands, key=lambda w: (w.x - u.x) ** 2 + (w.y - u.y) ** 2)
        pool.remove(v)
        errs.append(math.hypot((v.x - u.x) * _TILES_X, (v.y - u.y) * _TILES_Y))
    return {
        "bodies_true": float(len(tl)),
        "bodies_rebuilt": float(len(rl)),
        "bodies_missing": float(len(tl) - len(rl)),
        "hp_true": float(hp_true),
        "hp_rebuilt": float(hp_rebuilt),
        "hp_overstate_frac": float((hp_rebuilt - hp_true) / hp_true) if hp_true > 0 else 0.0,
        "pos_err_mean_tiles": float(sum(errs) / len(errs)) if errs else 0.0,
        "pos_err_max_tiles": float(max(errs)) if errs else 0.0,
        "matched": float(len(errs)),
    }
