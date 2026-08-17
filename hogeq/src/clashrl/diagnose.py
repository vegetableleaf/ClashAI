"""Diagnose menu navigation.

Grabs the current game frame, reports the match score of every screen-state template
(so you can see why HOME/PARTY/etc. isn't being detected), shows where the Battle button
was located vs the configured tap point, and saves the annotated frame. Run it while the
game sits on the screen the bot won't advance past (e.g. HOME if it won't press Battle).
"""
from __future__ import annotations

import pathlib

import cv2

from .capture import WindowCapture
from .vision import Vision


def diagnose(cfg) -> None:
    capture = WindowCapture(cfg.get("window", "title_contains", default=None),
                            cfg.get("window", "region", default=None))
    if capture.region is None:
        print("[diag] no capture region; set window.region in config.yaml.")
        return
    print(f"[diag] capture region (x,y,w,h): {capture.region}")
    vision = Vision(cfg)
    frame = capture.grab()
    if frame is None:
        print("[diag] capture returned NO frame -- the game window isn't being captured "
              "(wrong window.region / window moved or minimised).")
        return
    h, w = frame.shape[:2]
    work = vision._work(frame)
    print(f"[diag] frame {w}x{h}, work {work.shape[1]}x{work.shape[0]}")

    for key in ("home_menu", "party_menu", "in_match", "match_end"):
        spec = cfg.get("states", key, default=None)
        if not spec:
            continue
        thr_default = float(spec.get("threshold", 0.8))
        for entry in (spec.get("templates") or [spec.get("template")]):
            # A templates list may mix plain filenames with dict entries carrying their OWN
            # threshold + search region (the strict OVERTIME banner). Mirror detect_state
            # exactly, otherwise the diagnosis reports a score the bot never computes.
            if isinstance(entry, dict):
                name = entry.get("template")
                thr = float(entry.get("threshold", thr_default))
                region = entry.get("region")
            else:
                name, thr, region = entry, thr_default, None
            tmpl = vision._templates.get(name) if name else None
            if tmpl is None:
                print(f"[diag] {key:11}: template '{name}' MISSING from templates/")
                continue
            area = work
            ox = oy = 0
            if region:                        # normalized [x0, y0, x1, y1] search window
                hh, ww = work.shape[:2]
                x0, y0, x1, y1 = region
                ox, oy = max(0, int(x0 * ww)), max(0, int(y0 * hh))
                area = work[oy:min(hh, int(round(y1 * hh))), ox:min(ww, int(round(x1 * ww)))]
            if area.shape[0] < tmpl.shape[0] or area.shape[1] < tmpl.shape[1]:
                print(f"[diag] {key:11}: template '{name}' larger than the "
                      f"{'search region' if region else 'frame'} (scale mismatch)")
                continue
            res = cv2.matchTemplate(area, tmpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            cx = (ox + ml[0] + tmpl.shape[1] / 2.0) / work.shape[1]
            cy = (oy + ml[1] + tmpl.shape[0] / 2.0) / work.shape[0]
            hit = "MATCH" if mv >= thr else " no  "
            reg = f" region={list(region)}" if region else ""
            print(f"[diag] {key:11} {name:18} score={mv:.3f} thr={thr:.2f} [{hit}] "
                  f"center=({cx:.3f},{cy:.3f}){reg}")

    print(f"[diag] detect_state -> {vision.detect_state(frame).name}")
    batt = cfg.get("buttons", "battle_button", default=None)
    loc = vision.locate(frame, "home_menu.png", 0.0)     # best-effort location, any score
    if batt:
        print(f"[diag] configured battle_button tap = {batt}")
    if loc:
        print(f"[diag] Battle button best-match center = ({loc[0]:.3f}, {loc[1]:.3f}) "
              "(what the bot will now tap when HOME is detected)")

    out = frame.copy()
    if batt:
        cv2.drawMarker(out, (int(batt[0] * w), int(batt[1] * h)), (0, 0, 255),
                       cv2.MARKER_TILTED_CROSS, 22, 2)     # red = configured point
    if loc:
        cv2.drawMarker(out, (int(loc[0] * w), int(loc[1] * h)), (0, 255, 0),
                       cv2.MARKER_CROSS, 22, 2)            # green = located button
    dst = pathlib.Path(cfg.path("data")) / "diag_state.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), out)
    print(f"[diag] saved current frame (red=configured tap, green=located button) to {dst}")
