"""Live view of the game window: what the bot sees right now, and what it makes of it.

Grabs the configured window through the same `WindowCapture` the bot uses and runs the
same `Vision` read over it, so this is not a decoration -- it answers the question that
otherwise costs an hour of guessing: is the screen being captured at all, does the frame
register as IN_MATCH, and are the hand cards recognised.

It is read-only. Nothing here clicks, and it works whether or not `play` is running.
"""
from __future__ import annotations

import base64
import threading
import time
from typing import Any, Dict, Optional

import cv2
import numpy as np

_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {"capture": None, "vision": None, "cfg_mtime": None}


def _ensure(cfg):
    """Build capture + vision once and reuse them; both are relatively expensive."""
    from ..capture import WindowCapture
    from ..vision import Vision
    with _LOCK:
        if _STATE["capture"] is None:
            _STATE["capture"] = WindowCapture(cfg.get("window", "title_contains", default=None),
                                              cfg.get("window", "region", default=None))
        if _STATE["vision"] is None:
            _STATE["vision"] = Vision(cfg)
        return _STATE["capture"], _STATE["vision"]


def reset() -> None:
    """Drop the cached capture/vision, e.g. after the window moved or the config changed."""
    with _LOCK:
        _STATE["capture"] = None
        _STATE["vision"] = None


# The order `Vision.detect_state` tries them in: the FIRST state whose template clears its
# threshold wins, so a result screen is never mistaken for a running match. Everything the
# bot does between matches hangs off this, which is why the panel shows the whole chain and
# not just the winner.
STATE_ORDER = [
    ("MATCH_END", "match_end", "Ergebnisbildschirm",
     "Taps 'Play again'. If nothing moves after a few seconds it taps OK "
     "instead and ends up back on the home screen."),
    ("IN_MATCH", "in_match", "In a match",
     "The only state in which the policy plays: pick a card, pick a cell, click. "
     "Everything else is navigation."),
    ("PARTY", "party_menu", "Party menu",
     "Picks 'Quick match' to get into a game."),
    ("HOME", "home_menu", "Home screen",
     "Locates the Battle button in the frame and taps it. If it cannot be found it taps the "
     "fixed coordinate from the config."),
]

UNKNOWN_MEANS = ("No state reached its threshold. The bot then simply waits "
                 "instead of clicking blindly. If it stays that way the templates do not match "
                 "your client.")


def state_report(cfg, vision, frame) -> Dict[str, Any]:
    """Per state: which templates decide it, how close each one is, and what happens then."""
    work = vision._work(frame)
    rows = []
    for name, key, label, action in STATE_ORDER:
        spec = cfg.get("states", key, default=None) or {}
        thr_default = float(spec.get("threshold", 0.8))
        entries = spec.get("templates") or ([spec.get("template")] if spec.get("template") else [])
        tpls, matched = [], False
        for entry in entries:
            if isinstance(entry, dict):
                tname, thr, region = entry.get("template"), float(
                    entry.get("threshold", thr_default)), entry.get("region")
            else:
                tname, thr, region = entry, thr_default, None
            tmpl = vision._templates.get(tname) if tname else None
            if tmpl is None:
                tpls.append({"name": tname, "score": None, "threshold": thr, "missing": True})
                continue
            area = work
            if region:
                hh, ww = work.shape[:2]
                x0, y0, x1, y1 = region
                area = work[max(0, int(y0 * hh)):min(hh, int(round(y1 * hh))),
                            max(0, int(x0 * ww)):min(ww, int(round(x1 * ww)))]
            if area.shape[0] < tmpl.shape[0] or area.shape[1] < tmpl.shape[1]:
                tpls.append({"name": tname, "score": None, "threshold": thr, "too_small": True})
                continue
            sc = round(float(cv2.matchTemplate(area, tmpl, cv2.TM_CCOEFF_NORMED).max()), 3)
            hit = sc >= thr
            matched = matched or hit
            tpls.append({"name": tname, "score": sc, "threshold": thr, "hit": hit,
                         "region": list(region) if region else None})
        rows.append({"state": name, "label": label, "action": action,
                     "matched": matched, "templates": tpls})
    return {"order": rows, "unknown_means": UNKNOWN_MEANS}


def snapshot(cfg, width: int = 420, quality: int = 65) -> Dict[str, Any]:
    """One frame plus the bot's reading of it. Never raises; reports the problem instead."""
    t0 = time.time()
    try:
        capture, vision = _ensure(cfg)
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "error": f"could not initialise capture or vision: {exc}"}

    if capture.region is None:
        return {"ok": False, "error": "No capture region. Is the game running, and does "
                                      "window.title_contains match the window title?"}
    try:
        frame = capture.grab()
    except Exception as exc:                                  # noqa: BLE001
        # The stored window region points nowhere once the window is closed, minimised
        # or moved. Drop it so the next call looks the window up again.
        reset()
        return {"ok": False,
                "error": "The game window cannot be captured right now "
                         "(closed or minimised?). It will be looked up again on the next attempt.",
                "detail": str(exc)}
    if frame is None:
        reset()
        return {"ok": False, "error": "No frame received. Window minimised or moved?"}

    h, w = frame.shape[:2]
    reg = capture.region
    out: Dict[str, Any] = {
        "ok": True, "width": w, "height": h,
        "region": [getattr(reg, "left", None), getattr(reg, "top", None),
                   getattr(reg, "width", None), getattr(reg, "height", None)]
        if reg is not None else None}

    try:
        out["state"] = vision.detect_state(frame).name
    except Exception as exc:                                  # noqa: BLE001
        out["state"] = "ERROR"
        out["state_error"] = str(exc)

    out["states"] = state_report(cfg, vision, frame)

    # hand cards + elixir, as the bot reads them
    try:
        hand = []
        for i, (cx, cy) in enumerate(vision.hand_slots):
            crop = vision.hand_crop(frame, cx, cy)
            cid, score = vision.match_card(crop) if crop.size else (-1, 0.0)
            key = vision.deck_keys[cid] if 0 <= cid < len(vision.deck_keys) else None
            hand.append({"slot": i + 1, "card": key, "score": round(float(score), 3)})
        out["hand"] = hand
    except Exception as exc:                                  # noqa: BLE001
        out["hand_error"] = str(exc)
    try:
        out["elixir"] = vision.read_elixir(frame)
    except Exception:                                         # noqa: BLE001
        out["elixir"] = None

    scale = width / float(w)
    small = cv2.resize(frame, (width, max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if ok:
        out["image"] = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
    out["ms"] = int((time.time() - t0) * 1000)
    return out
