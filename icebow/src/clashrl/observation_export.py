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
            assume_match: bool = False, tracker=None) -> Dict[str, Any]:
    """Read EVERYTHING off one BGR frame. `prev` (an earlier record) enables velocity.

    `tracker` is a live TeamTracker. Given one, every unit carries a STABLE `id` across records
    and a `remembered` block lists units the tracker still holds but the detector did not report
    this frame -- a unit walking behind a tower, or swallowed by a neighbour's box in a push.
    Without a tracker both are absent rather than faked: a single frame has no history, and an
    id that changed every read would be worse than none.

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
        # THE TILE IS THE HP BAR, NOT THE TOWER. read_towers returns the bar's read window, so
        # `tile` says where that bar floats, not where the tower stands. Measured over 120 val
        # frames it is stable: enemy y 0.99, own y 22.3-22.5 (x 3.17/13.17 and 4.02/13.62).
        # Those two are NOT mirror images about x=9, so the configured windows are themselves
        # only roughly placed -- do not derive a tower footprint from them.
        "tile_note": "tile is the HP BAR's centre, not the tower's ground position",
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
        found = det.detect(frame, conf=detector_conf)
        if tracker is not None:
            import time as _time
            now = _time.monotonic()
            tracker.tag(found, now)          # stamps d.track_id and fuses d.team over the track
            units["remembered"] = [
                {"id": u["id"], "cls": u["cls"], "card": u["base"], "team": u["team"],
                 "xy": [_r(u["xy"][0]), _r(u["xy"][1])],
                 "tile": grid.tile(u["xy"][0], u["xy"][1]),
                 "missing_s": u["missing_s"], "missed_reads": u["misses"],
                 # FROZEN at the last real sighting, not extrapolated. A unit that stops behind
                 # a tower would otherwise be reported marching through it.
                 "position": "last seen, not predicted"}
                for u in tracker.unseen(now)]
        for d in found:
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
                # Stable across records within one match, null without a tracker. NOT the
                # position in this list -- the detector reorders that every frame.
                "id": d.track_id,
            })
    except Exception as exc:                                        # noqa: BLE001
        units["error"] = str(exc)
    out["units"] = units

    # -- per-unit HP, from a SECOND detector ---------------------------------
    out["bars"] = _bars_block(cfg, frame, grid, units["list"])

    # -- velocity, only if a previous record was handed in --------------------
    # One frame cannot show motion. Rather than omit the field (ambiguous) or fake a zero
    # (a lie a simulator would integrate), it is present and null until two frames exist.
    out["motion"] = {"available": bool(prev),
                     "note": "per-unit velocity needs two frames; pass the previous record as "
                             "`prev`. The live bot gets finer motion from perception.py at ~10 Hz"}
    if prev:
        out["motion"]["units"] = _velocity(prev, out)
    return out


_BAR_MODEL = None       # loaded once, then reused; None means "not tried yet"


def _bars_block(cfg, frame, grid, unit_list: List[Dict]) -> Dict[str, Any]:
    """Detected HP bars, and the per-unit HP fraction they imply.

    A SEPARATE model from the one behind `units` (runs/bars, 2 classes) -- bars are geometry,
    not card art, and mixing them into the 225-class detector would mean retraining it. If
    those weights are absent this block reports `available: false` and every unit's `hp`
    stays null; nothing else in the record changes.

    Bars that match no unit are still listed. A bar with no owner is evidence of a unit the
    board detector missed, which is exactly the kind of thing a consumer should be able to
    see rather than have quietly dropped.
    """
    global _BAR_MODEL
    from .troop_hp import bar_team, match_bars, read_fill

    block: Dict[str, Any] = {
        "available": False,
        "method": "2-class YOLO (hp_bar, tower_hp_bar) + per-bar fill measurement",
        "reliability": "fill is calibrated on bar structure but UNVERIFIED against true HP -- "
                       "the training data carries no HP ground truth to score it against",
        "list": [],
    }
    w = Path(cfg.path("runs/bars/v1/weights/best.pt"))
    if not w.is_file():
        block["reason"] = f"no bar detector at {w}"
        return block
    try:
        if _BAR_MODEL is None:
            from ultralytics import YOLO
            _BAR_MODEL = YOLO(str(w))
        res = _BAR_MODEL.predict(frame, conf=0.30, verbose=False)[0]
        names = res.names
        h, wpx = frame.shape[:2]

        bars, kinds, confs = [], [], []
        for b in res.boxes:
            x0, y0, x1, y1 = (float(v) for v in b.xyxy[0])
            bars.append((x0 / wpx, y0 / h, x1 / wpx, y1 / h))
            kinds.append(names[int(b.cls)])
            confs.append(float(b.conf))

        # unit boxes, rebuilt from what the units block already published
        boxes = []
        for u in unit_list:
            (cx, cy), (bw, bh) = u["sprite_xy"], u["size_norm"]
            boxes.append((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))

        unit_bars = [i for i, k in enumerate(kinds) if k == "hp_bar"]
        owner = match_bars([bars[i] for i in unit_bars], boxes)

        for n, i in enumerate(unit_bars):
            ui = owner.get(n)
            frac = read_fill(frame, bars[i])
            cx = (bars[i][0] + bars[i][2]) / 2
            cy = (bars[i][1] + bars[i][3]) / 2
            block["list"].append({
                "kind": "unit",
                "conf": _r(confs[i], 3),
                "fill": None if frac is None else _r(frac, 3),
                "team": bar_team(frame, bars[i]),
                "xy": [_r(cx), _r(cy)],
                "tile": grid.tile(cx, cy),
                # null does NOT mean "no unit there" -- it means no SINGLE owner could be
                # named, which is either no candidate (18.1% on ground truth) or several
                # (2.5%). Guessing between candidates would trade a gap for a silent error.
                "unit_index": ui,
            })
            if ui is not None and frac is not None:
                unit_list[ui]["hp"] = {"frac": _r(frac, 3), "method": "bar fill"}

        for i, k in enumerate(kinds):
            if k != "hp_bar":
                cx = (bars[i][0] + bars[i][2]) / 2
                cy = (bars[i][1] + bars[i][3]) / 2
                tf = read_fill(frame, bars[i])
                block["list"].append({"kind": "tower", "conf": _r(confs[i], 3),
                                      # `or 0.0` here would report an UNREADABLE bar as an
                                      # empty one, i.e. a destroyed tower. Null means null.
                                      "fill": None if tf is None else _r(tf, 3),
                                      # bar_team() is a UNIT-bar reader. Tower bars overlap
                                      # almost completely in hue between the two sides, so it
                                      # would answer confidently and wrongly. The `towers`
                                      # block already carries each tower's side.
                                      "team": None,
                                      "xy": [_r(cx), _r(cy)], "tile": grid.tile(cx, cy),
                                      "unit_index": None})
        block["available"] = True
    except Exception as exc:                                        # noqa: BLE001
        block["error"] = str(exc)
    # present-but-null on every unit, so "no bar" is distinguishable from "no reader"
    for u in unit_list:
        u.setdefault("hp", None)
    return block


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
