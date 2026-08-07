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
     "Tippt 'Nochmal spielen'. Bewegt sich danach nichts, tippt er nach ein paar Sekunden "
     "stattdessen OK und landet wieder im Hauptmenü."),
    ("IN_MATCH", "in_match", "Im Match",
     "Der einzige Zustand, in dem die Policy spielt: Karte wählen, Feld wählen, klicken. "
     "Alles andere ist Navigation."),
    ("PARTY", "party_menu", "Party-Menü",
     "Wählt 'Schnelles Spiel', um in ein Match zu kommen."),
    ("HOME", "home_menu", "Hauptmenü",
     "Sucht den Battle-Knopf im Bild und tippt ihn. Wird er nicht gefunden, tippt er die "
     "fest eingetragene Stelle."),
]

UNKNOWN_MEANS = ("Kein Zustand hat seine Schwelle erreicht. Der Bot wartet dann einfach ab, "
                 "statt blind zu klicken. Bleibt es dauerhaft dabei, passen die Vorlagen nicht "
                 "zu deinem Client.")


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

    out["states"] = state_report(cfg, vision, frame)

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
