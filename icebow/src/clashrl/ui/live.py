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


def snapshot(cfg, width: int = 420, quality: int = 65) -> Dict[str, Any]:
    """One frame plus the bot's reading of it. Never raises; reports the problem instead."""
    t0 = time.time()
    try:
        capture, vision = _ensure(cfg)
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "error": f"Fenster/Erkennung nicht initialisierbar: {exc}"}

    if capture.region is None:
        return {"ok": False, "error": "Kein Aufnahmebereich. Läuft das Spiel, und passt "
                                      "window.title_contains zum Fenstertitel?"}
    try:
        frame = capture.grab()
    except Exception as exc:                                  # noqa: BLE001
        # Der gespeicherte Fensterbereich zeigt ins Leere, sobald das Fenster geschlossen,
        # minimiert oder verschoben wurde. Verwerfen, damit der nächste Aufruf neu sucht.
        reset()
        return {"ok": False,
                "error": "Das Spielfenster lässt sich gerade nicht abfotografieren "
                         "(geschlossen oder minimiert?). Es wird beim nächsten Versuch neu gesucht.",
                "detail": str(exc)}
    if frame is None:
        reset()
        return {"ok": False, "error": "Kein Bild erhalten. Fenster minimiert oder verschoben?"}

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
        out["state"] = "FEHLER"
        out["state_error"] = str(exc)

    # Bestwert jedes Zustands-Templates: genau daran sieht man, ob es knapp oder weit daneben ist.
    scores = {}
    try:
        work = vision._work(frame)
        for name, tmpl in vision._templates.items():
            if work.shape[0] < tmpl.shape[0] or work.shape[1] < tmpl.shape[1]:
                continue
            scores[name] = round(float(cv2.matchTemplate(work, tmpl,
                                                         cv2.TM_CCOEFF_NORMED).max()), 3)
    except Exception:                                         # noqa: BLE001
        pass
    out["template_scores"] = dict(sorted(scores.items(), key=lambda kv: -kv[1])[:8])

    # Handkarten + Elixier, wie der Bot sie liest
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
