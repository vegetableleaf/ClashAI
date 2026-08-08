"""Run EVERY reader the bot uses over one still frame, and report what each one said.

The board detector is only one of five readers. The rest -- hand cards, elixir, tower HP,
which screen is showing -- are plain code that has always run silently, so the panel gave
the impression that the detector was the whole of "reading the screen" and that anything
it cannot do is simply not read. It is read; it is just read somewhere else:

    what                 how                                     trained?
    screen state         template match (templates/*.png)         no
    hand cards           template match (templates/cards/*.png)   no
    elixir               counts filled pips on the bar by HSV     no
    tower HP             small digit CNN (hp_digits.npz)          yes, ships trained
    units on the board   YOLO detector                            yes, THE vision AI

This module calls all of them on a single frame and returns both the VALUES and the
BOXES they were read from, so the UI can draw each reader's region on the picture. That
turns "does it read the tower HP?" from a question about the code into something you can
look at -- and makes a mis-calibrated crop (the usual cause of a wrong read) visible as a
box sitting in the wrong place rather than as a silently wrong number.

Nothing here trains, writes or changes anything: it is a read-only view of the same calls
env/play make every tick.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2


def _hand_boxes(cfg, vision) -> List[Dict[str, float]]:
    """The tray crops recognize_hand() matches, in normalised x/y/w/h."""
    out = []
    for cx, cy in vision.hand_slots:
        out.append({"x": cx - vision.card_w, "y": cy - vision.card_h,
                    "w": 2 * vision.card_w, "h": 2 * vision.card_h})
    return out


def read_frame(cfg, path: Path, detector_conf: float = 0.25) -> Dict[str, Any]:
    """Everything the bot would extract from this frame, with the regions it looked at."""
    frame = cv2.imread(str(path))
    if frame is None:
        return {"error": f"could not read {path.name}"}
    h, w = frame.shape[:2]
    out: Dict[str, Any] = {"size": [w, h], "readers": []}

    from ..vision import Vision
    vision = Vision(cfg)

    # -- 1. which screen -------------------------------------------------
    try:
        state = vision.detect_state(frame)
        out["state"] = getattr(state, "name", str(state))
    except Exception as exc:                          # noqa: BLE001
        out["state"] = None
        out["state_error"] = str(exc)

    # -- 2. hand cards ---------------------------------------------------
    hand: Dict[str, Any] = {"slots": [], "how": "template match against templates/cards/*.png "
                                                "(colour first, equalised luminance as a retry "
                                                "for greyed-out cards)", "trained": False}
    try:
        keys = list(getattr(vision, "deck_keys", []) or [])
        boxes = _hand_boxes(cfg, vision)
        for i, (cx, cy) in enumerate(vision.hand_slots):
            crop = vision.hand_crop(frame, cx, cy)
            empty = vision.slot_is_empty(crop)
            idx, score = (-1, 0.0) if empty else vision.match_card(crop)
            # The greying is the game saying "you cannot afford this yet" -- worth reporting,
            # since a card can be correctly identified and still be unplayable.
            sat = float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1].mean()) if crop.size else 0.0
            hand["slots"].append({
                "slot": i,
                "card": keys[idx] if 0 <= idx < len(keys) else None,
                "state": "empty" if empty else ("read" if idx >= 0 else "unknown"),
                "affordable": None if empty else bool(sat >= 60),
                "score": round(float(score), 3),
                "box": boxes[i],
            })
        hand["read"] = sum(1 for s in hand["slots"] if s["card"])
        hand["empty"] = sum(1 for s in hand["slots"] if s["state"] == "empty")
        # Cards with no template at all can never be read; naming them beats a bare "?".
        hand["no_template"] = [k for k, tl in zip(keys, getattr(vision, "_card_tpls", []))
                               if not tl]
    except Exception as exc:                          # noqa: BLE001
        hand["error"] = str(exc)
    out["hand"] = hand

    # -- 2b. the NEXT card ------------------------------------------------
    nxt: Dict[str, Any] = {"how": "template match against templates/next/*.png (its own set: "
                                  "the preview is smaller and blue-tinted)", "trained": False}
    try:
        keys = list(getattr(vision, "deck_keys", []) or [])
        have = [k for k, tl in zip(keys, getattr(vision, "_next_tpls", [])) if tl]
        idx = vision.recognize_next(frame)
        nxt["card"] = keys[idx] if 0 <= idx < len(keys) else None
        nxt["has_templates"] = have
        if not have:
            nxt["error"] = ("no templates/next/*.png for this deck -- the preview cannot be "
                            "read until they exist")
        if vision.next_slot:
            nxt["box"] = {"x": vision.next_slot[0] - vision.next_card_w,
                          "y": vision.next_slot[1] - vision.next_card_h,
                          "w": 2 * vision.next_card_w, "h": 2 * vision.next_card_h}
    except Exception as exc:                          # noqa: BLE001
        nxt["error"] = str(exc)
    out["next"] = nxt

    # -- 3. elixir -------------------------------------------------------
    elixir: Dict[str, Any] = {"how": "counts filled pips on the bar (HSV threshold)",
                              "trained": False}
    try:
        elixir["value"] = int(vision.read_elixir(frame))
        bar_y = float(cfg.get("elixir", "bar_y", default=0.97))
        xs = list(cfg.get("elixir", "pip_xs", default=[]) or [])
        elixir["pips"] = [{"x": float(x), "y": bar_y} for x in xs]
    except Exception as exc:                          # noqa: BLE001
        elixir["error"] = str(exc)
    out["elixir"] = elixir

    # -- 4. tower HP -----------------------------------------------------
    towers: Dict[str, Any] = {"how": "the NUMBER via a small digit CNN (hp_digits.npz), and "
                                     "independently the BAR FILL by colour -- the bar also says "
                                     "whether the tower is still standing at all",
                              "trained": True, "readings": []}
    try:
        from ..tower_hp import read_towers
        rect = lambda b: ({"x": b[0], "y": b[1], "w": b[2] - b[0], "h": b[3] - b[1]}  # noqa: E731
                          if b else None)
        for t in read_towers(frame, cfg):
            towers["readings"].append({
                "name": t["name"], "label": t["label"], "kind": t["kind"], "side": t["side"],
                "hp": t["hp"], "conf": t["conf"], "state": t["state"],
                "fill": None if t["fill"] is None else round(t["fill"], 3),
                "box": rect(t["box"]), "bar": rect(t["bar"]),
            })
    except Exception as exc:                          # noqa: BLE001
        towers["error"] = str(exc)
    out["towers"] = towers

    # -- 5. units on the board (THE vision AI) ---------------------------
    units: Dict[str, Any] = {"how": "YOLO board detector", "trained": True, "boxes": []}
    try:
        from ..replay_mine import load_detector
        det = load_detector(cfg, None)
        found = det.detect(frame, conf=detector_conf)
        if not getattr(det, "_model", None):
            units["error"] = "no trained detector -- nothing to read the board with"
        for d in found:
            units["boxes"].append({"cls": d.cls, "conf": round(float(d.conf), 3),
                                   "cx": float(d.cx), "cy": float(d.cy),
                                   "w": float(d.w), "h": float(d.h),
                                   "team": getattr(d, "team", None)})
    except Exception as exc:                          # noqa: BLE001
        units["error"] = str(exc)
    out["units"] = units
    return out
