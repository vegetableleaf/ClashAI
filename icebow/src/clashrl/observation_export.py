"""ONE frame -> ONE versioned JSON record holding everything the screen can tell us.

This is the hand-off contract to the SIMULATOR. Everything here already existed, but it was
spread across five readers with five shapes and five notions of "where": the detector speaks
normalized image coordinates, the tower reader speaks its own boxes, the action grid speaks tile
indices, and nothing said which numbers were trustworthy. A simulator author reading that has to
reverse-engineer our internals before writing a single line -- so this module fixes ONE shape,
converts every position into the ARENA TILE lattice a simulator actually thinks in, and marks
every field with how it was obtained and how much to trust it.

FOUR RULES this format follows, and the reason for each:

1. EVERY POSITION IS GIVEN TWICE -- normalized image `xy` AND arena tile `tile`. The tile lattice
   (18 x 32, Clash Royale's real board) is what a simulator needs; the image coordinates are what
   lets anyone re-draw the box on the screenshot and check us. Emitting only one would force the
   consumer to either trust our calibration blindly or redo it.

2. FLYERS REPORT THEIR SHADOW, NOT THEIR SPRITE. A flying unit is drawn ABOVE the tile it
   occupies, so its box centre is metres off the truth. `tile` is derived from `Detection.gy`
   (the shadow) and `airborne` says whether that correction was applied. A simulator placing a
   Baby Dragon by its sprite centre puts it a tile and a half too far forward.

3. NOTHING IS SILENTLY ESTIMATED. Every block carries `method` (how it was read) and either a
   confidence or an explicit `null`. Where a reader is a known scaffold rather than a trusted
   number -- troop HP is measured off a bar that only appears once a unit is damaged -- the block
   says `"reliability": "scaffold"`. A consumer can filter on that instead of discovering it from
   bad simulation results.

4. FIELDS ARE PRESENT EVEN WHEN UNREADABLE, as null. A missing key is ambiguous between "this
   build does not produce it" and "it could not be read here"; an explicit null with a `method`
   is not.

The schema is VERSIONED. `schema` changes only when a field's MEANING changes -- adding fields is
not a version bump, so a consumer may ignore unknown keys but must never ignore the version.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

SCHEMA = "clashai-observation/1"

# Clash Royale's real board. NOT action.grid, which the RL config coarsens to 18x24 to shrink the
# action space -- that is a training detail and would be a lie in an interchange format.
TILES_X, TILES_Y = 18, 32


class _Grid:
    """Normalized image xy -> arena tile, using the SAME arena_box the tap grid is calibrated to.

    Kept separate from actions.ActionGrid because that one carries the coarsened training grid and
    the deploy-clamping rules; here we want the plain board lattice and no clamping games."""

    def __init__(self, cfg):
        box = (cfg.get("action", "arena_box", default=None)
               or cfg.get("env", "arena_region", default=[0.03, 0.10, 0.97, 0.86]))
        self.x0, self.y0, self.x1, self.y1 = (float(v) for v in box)

    def tile(self, nx: float, ny: float) -> Optional[List[float]]:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            return None
        # FRACTIONAL, not an int index: a simulator wants the sub-tile position (a unit standing
        # between two tiles is real), and rounding here would throw that away irreversibly.
        tx = (nx - self.x0) / (self.x1 - self.x0) * TILES_X
        ty = (ny - self.y0) / (self.y1 - self.y0) * TILES_Y
        return [round(tx, 3), round(ty, 3)]


def _r(v, n=4):
    return None if v is None else round(float(v), n)


def observe(cfg, frame, detector_conf: float = 0.25, prev: Optional[Dict] = None,
            assume_match: bool = False) -> Dict[str, Any]:
    """Read EVERYTHING off one BGR frame. `prev` (an earlier record) enables velocity.

    `assume_match` overrides the screen-state reader. That reader template-matches against
    templates captured from THIS machine's client, so on a frame from anyone else's client -- a
    different language, a different aspect ratio, a YouTube capture -- it returns UNKNOWN and
    every match-only block below suppresses itself. For a labelled dataset frame the caller knows
    it is a match and the detector does not; this lets the caller say so, and the record still
    reports what the reader actually thought under `screen`.
    """
    from .vision import Vision
    from .replay_mine import load_detector

    h, w = frame.shape[:2]
    grid = _Grid(cfg)
    vision = Vision(cfg)
    out: Dict[str, Any] = {
        "schema": SCHEMA,
        "frame": {"width": w, "height": h},
        "arena": {"tiles": [TILES_X, TILES_Y],
                  "box_norm": [grid.x0, grid.y0, grid.x1, grid.y1],
                  "note": "tile coordinates are FRACTIONAL; [0,0] is the top-left of the "
                          "opponent's back line, [18,32] the bottom-right of yours",
                  # The single biggest source of systematic error in this record, and invisible
                  # unless stated: box_norm is calibrated to ONE client's layout. Feed a frame
                  # from a different aspect ratio or a cropped capture and every tile is offset
                  # by the same amount -- consistent, so it looks correct, and wrong.
                  "calibration_warning":
                      "box_norm comes from action.arena_box in config.yaml, calibrated for the "
                      "capturing client. Tiles from a frame of a DIFFERENT client are offset. "
                      "Check by confirming the princess towers land near tile y 3.5 and 28.5"},
    }

    # -- which screen -------------------------------------------------------
    try:
        st = vision.detect_state(frame)
        state = getattr(st, "name", str(st))
    except Exception as exc:                                        # noqa: BLE001
        state, out["screen_error"] = None, str(exc)
    detected_match = state == "IN_MATCH"
    in_match = detected_match or assume_match
    out["screen"] = {"state": state, "in_match": in_match,
                     "detected_in_match": detected_match,
                     "assumed": bool(assume_match and not detected_match),
                     "method": "template match against templates/*.png (captured from THIS "
                               "machine's client -- returns UNKNOWN on a foreign client)"}
    # Outside a match none of the readers below mean anything -- an elixir count off a menu is
    # noise, not data. Saying so beats emitting six confident wrong numbers.
    if not in_match:
        out["note"] = "not in a match; the blocks below are unread, not zero"

    # -- hand ---------------------------------------------------------------
    hand: Dict[str, Any] = {"method": "template match against templates/cards/*.png",
                            "reliability": "deck-bound: only cards with a template can be named",
                            "slots": []}
    try:
        keys = list(getattr(vision, "deck_keys", []) or [])
        for i, (cx, cy) in enumerate(vision.hand_slots):
            crop = vision.hand_crop(frame, cx, cy)
            empty = vision.slot_is_empty(crop)
            idx, score = (-1, 0.0) if empty else vision.match_card(crop)
            sat = float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1].mean()) if crop.size else 0.0
            hand["slots"].append({
                "slot": i,
                "card": keys[idx] if 0 <= idx < len(keys) else None,
                "state": "empty" if empty else ("read" if idx >= 0 else "unknown"),
                # greyed-out = the game saying "you cannot afford this yet". A card can be
                # correctly identified AND unplayable; a simulator needs both facts separately.
                "affordable": None if empty else bool(sat >= 60),
                "match_score": _r(score, 3),
            })
    except Exception as exc:                                        # noqa: BLE001
        hand["error"] = str(exc)
    out["hand"] = hand

    # -- next card ----------------------------------------------------------
    nxt: Dict[str, Any] = {"method": "template match against templates/next/*.png "
                                     "(own set: the preview is smaller and blue-tinted)"}
    try:
        keys = list(getattr(vision, "deck_keys", []) or [])
        have = [k for k, tl in zip(keys, getattr(vision, "_next_tpls", [])) if tl]
        i = vision.recognize_next(frame)
        nxt["card"] = keys[i] if 0 <= i < len(keys) else None
        if not have:
            nxt["error"] = "no templates/next/*.png for this deck -- unreadable until they exist"
    except Exception as exc:                                        # noqa: BLE001
        nxt["error"] = str(exc)
    out["next_card"] = nxt

    # -- elixir -------------------------------------------------------------
    elixir: Dict[str, Any] = {"method": "counts filled pips on the bar by HSV threshold"}
    try:
        elixir["value"] = int(vision.read_elixir(frame)) if in_match else None
        elixir["max"] = 10
    except Exception as exc:                                        # noqa: BLE001
        elixir["error"] = str(exc)
    # The 1x/2x/3x phase is TIME-DERIVED and needs match context a single frame does not have.
    # Saying "unknown from one frame" is the honest answer; the live bot gets it from ElixirClock.
    elixir["multiplier"] = None
    elixir["multiplier_note"] = ("not derivable from one frame -- clock.ElixirClock tracks it from "
                                 "elapsed match time, cross-checked against the on-screen badge")
    out["elixir"] = elixir

    # -- towers -------------------------------------------------------------
    towers: Dict[str, Any] = {
        "method": "HP digits via a small CNN (hp_digits.npz); bar fill by colour, independently",
        "list": []}
    try:
        from .tower_hp import read_towers
        for t in read_towers(frame, cfg):
            box = t.get("box")
            cx = (box[0] + box[2]) / 2 if box else None
            cy = (box[1] + box[3]) / 2 if box else None
            towers["list"].append({
                "name": t["name"], "kind": t["kind"], "side": t["side"],
                "hp": t["hp"] if in_match else None,
                "hp_conf": _r(t.get("conf"), 3),
                "fill": _r(t.get("fill"), 3) if in_match else None,
                "state": t["state"] if in_match else "no_match",
                "xy": [_r(cx), _r(cy)],
                "tile": grid.tile(cx, cy) if cx is not None else None,
                # non-zero = this frame's geometry did not match config.yaml and the read window
                # had to be moved to find the bar. A simulator can treat that as a quality flag.
                "snapped": _r(t.get("snapped") or 0.0, 4),
            })
    except Exception as exc:                                        # noqa: BLE001
        towers["error"] = str(exc)
    out["towers"] = towers

    # -- units --------------------------------------------------------------
    units: Dict[str, Any] = {"method": f"YOLO board detector at conf>={detector_conf}",
                             "team_method": "TeamTracker evidence fusion (own-play anchor, motion "
                                            "direction, HP-bar colour, first-seen side, body art)",
                             "list": []}
    try:
        det = load_detector(cfg, None)
        if not getattr(det, "_model", None):
            units["error"] = "no trained detector"
        for d in det.detect(frame, conf=detector_conf):
            airborne = d.ground_cy is not None
            gy = d.gy                                # shadow for flyers, box centre for ground
            units["list"].append({
                "cls": d.cls,
                "card": d.base,                      # _evo/_hero/_ability/_aoe stripped
                "conf": _r(d.conf, 3),
                "team": d.team,                      # "mine" | "enemy" | "unknown"
                "xy": [_r(d.cx), _r(gy)],
                "tile": grid.tile(d.cx, gy),
                "size_norm": [_r(d.w), _r(d.h)],
                # A flyer's sprite sits ABOVE its tile. `tile` is already corrected; this says so,
                # and sprite_xy keeps the uncorrected centre for anyone re-drawing the box.
                "airborne": airborne,
                "sprite_xy": [_r(d.cx), _r(d.cy)],
                "team_evidence": {"bar": d.bar_vote, "body": d.body_vote},
            })
    except Exception as exc:                                        # noqa: BLE001
        units["error"] = str(exc)
    out["units"] = units

    # -- velocity, only if a previous record was handed in --------------------
    # One frame cannot show motion. Rather than omit the field (ambiguous) or fake a zero
    # (a lie a simulator would integrate), it is present and null until two frames exist.
    out["motion"] = {"available": bool(prev),
                     "note": "per-unit velocity needs two frames; pass the previous record as "
                             "`prev`. The live bot gets finer motion from perception.py at ~10 Hz"}
    if prev:
        out["motion"]["units"] = _velocity(prev, out)
    return out


def _velocity(prev: Dict, cur: Dict) -> List[Dict]:
    """Nearest-neighbour match of same-class units between two records, in TILES.

    Deliberately naive and deliberately labelled as such: real tracking lives in perception.py
    with a proper tracker. This exists so a two-frame export is not silently motionless."""
    out = []
    old = [u for u in prev.get("units", {}).get("list", []) if u.get("tile")]
    for u in cur.get("units", {}).get("list", []):
        if not u.get("tile"):
            continue
        same = [o for o in old if o["cls"] == u["cls"] and o.get("team") == u.get("team")]
        if not same:
            continue
        near = min(same, key=lambda o: (o["tile"][0] - u["tile"][0]) ** 2
                                       + (o["tile"][1] - u["tile"][1]) ** 2)
        out.append({"cls": u["cls"], "team": u["team"], "tile": u["tile"],
                    "delta_tiles": [round(u["tile"][0] - near["tile"][0], 3),
                                    round(u["tile"][1] - near["tile"][1], 3)],
                    "match": "nearest same-class neighbour (naive; not a tracker)"})
    return out


def observe_file(cfg, path: Path, detector_conf: float = 0.25,
                 assume_match: bool = False) -> Dict[str, Any]:
    frame = cv2.imread(str(path))
    if frame is None:
        return {"schema": SCHEMA, "error": f"could not read {path}"}
    rec = observe(cfg, frame, detector_conf, assume_match=assume_match)
    rec["source"] = path.name
    return rec
