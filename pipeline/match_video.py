"""Render a recorded engine match (`engine_play.py --record-every N`) as a vertical MP4.

This is NOT the game's graphics -- the sandbox engine has no renderer and no art. It draws what the
engine's own observation reports: the four crown towers, every live entity as a dot scaled by hit
points, both elixir bars, and a flash wherever the model placed a card. That is exactly the
information the model itself gets, which is the honest thing to show.

Output is 1080x1920 (Instagram's vertical frame) at the recording's own rate, so a 3-minute match at
`--record-every 2` is a ~3-minute clip. `--speed` drops frames to fit a shorter slot.

Usage:
    python pipeline/match_video.py <frames_*.json> -o clip.mp4 [--speed 3] [--label "icebow v4 - 19.8% top-1"]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ENGINE_X, ENGINE_Y = 18000.0, 32000.0

W, H = 1080, 1920
MARGIN = 60
BOARD_TOP, BOARD_BOT = 300, 1680          # arena band; HUD above, elixir below
PALETTE = {
    "bg":     (24, 22, 20),
    "ground": (58, 74, 52),
    "grid":   (70, 88, 62),
    "river":  (140, 108, 60),
    "line":   (96, 96, 92),
    "text":   (238, 236, 228),
    "muted":  (150, 148, 140),
    "me":     (210, 132, 44),               # BGR: blue-ish = the model
    "them":   (58, 68, 208),                # BGR: red = opponent
    "flash":  (120, 235, 250),
    "elx":    (200, 80, 190),
}
FONT = cv2.FONT_HERSHEY_SIMPLEX


def board_px(x: float, y: float, mirror: bool) -> tuple[int, int]:
    """Engine units -> pixels. The model always plays from the BOTTOM, so mirror when it is side 0."""
    fx, fy = x / ENGINE_X, y / ENGINE_Y
    if mirror:
        fx, fy = 1.0 - fx, 1.0 - fy
    return (int(MARGIN + fx * (W - 2 * MARGIN)),
            int(BOARD_TOP + (1.0 - fy) * (BOARD_BOT - BOARD_TOP)))


def draw_arena(img, mirror: bool) -> None:
    cv2.rectangle(img, (MARGIN, BOARD_TOP), (W - MARGIN, BOARD_BOT), PALETTE["ground"], -1)
    for i in range(1, 18):                                   # tile grid, 18 x 32
        x = int(MARGIN + i / 18 * (W - 2 * MARGIN))
        cv2.line(img, (x, BOARD_TOP), (x, BOARD_BOT), PALETTE["grid"], 1)
    for j in range(1, 32):
        y = int(BOARD_TOP + j / 32 * (BOARD_BOT - BOARD_TOP))
        cv2.line(img, (MARGIN, y), (W - MARGIN, y), PALETTE["grid"], 1)
    ymid = int(BOARD_TOP + 0.5 * (BOARD_BOT - BOARD_TOP))     # the river
    cv2.rectangle(img, (MARGIN, ymid - 14), (W - MARGIN, ymid + 14), PALETTE["river"], -1)
    cv2.rectangle(img, (MARGIN, BOARD_TOP), (W - MARGIN, BOARD_BOT), PALETTE["line"], 2)


def entity_colour(side: int, me: int) -> tuple[int, int, int]:
    return PALETTE["me"] if side == me else PALETTE["them"]


def draw_frame(fr: dict, me: int, mirror: bool, label: str, flash: dict | None, clock: float) -> np.ndarray:
    img = np.full((H, W, 3), PALETTE["bg"], np.uint8)
    draw_arena(img, mirror)

    for e in fr.get("entities", []):
        x, y = e.get("x"), e.get("y")
        if x is None or y is None:
            continue
        px, py = board_px(float(x), float(y), mirror)
        hp, mx = float(e.get("hp") or 0), float(e.get("max_hp") or 0) or 1.0
        col = entity_colour(int(e.get("side", 0)), me)
        # The engine leaves crown towers unnamed -- they are the only entities with no name.
        raw_name = e.get("name")
        is_tower = raw_name is None        # max_hp is NOT a second witness: a Pekka outweighs a princess tower
        name = "" if raw_name is None else str(raw_name)
        r = 26 if is_tower else max(8, min(22, int(8 + 14 * math.sqrt(max(hp, 1) / 3000.0))))
        if is_tower:
            cv2.rectangle(img, (px - r, py - r), (px + r, py + r), col, -1)
        else:
            cv2.circle(img, (px, py), r, col, -1)
        frac = max(0.0, min(1.0, hp / mx))
        if frac < 0.999:                                       # hp ring only when damaged
            cv2.ellipse(img, (px, py), (r + 5, r + 5), -90, 0, int(360 * frac), PALETTE["text"], 2)

    if flash is not None and flash.get("x") is not None:
        fx, fy = float(flash["x"]) * ENGINE_X, float(flash["y"]) * ENGINE_Y
        px, py = board_px(fx, fy, mirror)
        col = PALETTE["flash"] if flash.get("accepted") else (60, 60, 220)
        for rad in (26, 40, 54):
            cv2.circle(img, (px, py), rad, col, 2)
        cv2.putText(img, str(flash.get("card", "")).replace("_", " "), (px - 60, py - 66),
                    FONT, 0.7, col, 2, cv2.LINE_AA)

    # elixir_exact is the real value; "elixir" is the floored integer the UI would show
    elx = {int(p.get("side", i)): float(p.get("elixir_exact", p.get("elixir")) or 0)
           for i, p in enumerate(fr.get("players", []))}
    hands = {int(p.get("side", i)): [h.get("name", "") for h in p.get("hand", [])]
             for i, p in enumerate(fr.get("players", []))}
    for k, (side, y0) in enumerate(((me, BOARD_BOT + 60), (1 - me, BOARD_TOP - 90))):
        v = elx.get(side, 0.0)
        cv2.rectangle(img, (MARGIN, y0), (W - MARGIN, y0 + 34), (44, 42, 40), -1)
        w = int((W - 2 * MARGIN) * max(0.0, min(1.0, v / 10.0)))
        cv2.rectangle(img, (MARGIN, y0), (MARGIN + w, y0 + 34), PALETTE["elx"], -1)
        cv2.putText(img, "%.1f" % v, (W - MARGIN - 74, y0 + 27), FONT, 0.7, PALETTE["text"], 2, cv2.LINE_AA)

    hand = hands.get(me, [])
    for i, nm in enumerate(hand[:4]):        # the four cards the model is actually holding
        x0 = MARGIN + i * (W - 2 * MARGIN) // 4
        cv2.rectangle(img, (x0 + 4, BOARD_BOT + 110), (x0 + (W - 2 * MARGIN) // 4 - 4, BOARD_BOT + 176),
                      (44, 42, 40), -1)
        cv2.putText(img, str(nm)[:11], (x0 + 14, BOARD_BOT + 150), FONT, 0.55, PALETTE["text"], 1, cv2.LINE_AA)
    cv2.putText(img, label, (MARGIN, 110), FONT, 1.0, PALETTE["text"], 2, cv2.LINE_AA)
    cv2.putText(img, "the model sees only this", (MARGIN, 158), FONT, 0.62, PALETTE["muted"], 1, cv2.LINE_AA)
    cv2.putText(img, "%d:%02d" % (int(clock // 60), int(clock % 60)), (W - MARGIN - 150, 110),
                FONT, 1.0, PALETTE["text"], 2, cv2.LINE_AA)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", type=Path, help="frames_<tag>_m<N>.json from engine_play --record-every")
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--speed", type=int, default=1, help="keep every Nth frame (3 = 3x faster)")
    ap.add_argument("--fps", type=int, default=0, help="override output fps (default: the recording's own rate)")
    ap.add_argument("--label", default="", help="HUD line, e.g. the checkpoint and its top-1")
    ap.add_argument("--hold", type=float, default=2.0, help="seconds to hold the final frame")
    a = ap.parse_args()

    d = json.loads(a.frames.read_text(encoding="utf-8"))
    frames = d["frames"]
    if not frames:
        print("no frames in %s -- was --record-every set?" % a.frames, file=sys.stderr)
        return 2
    me = int(d.get("side", 1))
    # Side 1 sits at HIGH engine y (its king tower is at y=29000, side 0's at y=3000), and this
    # renderer puts low y at the bottom -- so side 1 is the one that needs flipping.
    mirror = me == 1                       # draw the model at the bottom whichever side it played
    tick_s = 0.05
    fps = a.fps or max(1, min(30, int(round(1.0 / (d.get("record_every", 2) * tick_s)))))
    out = a.out or a.frames.with_suffix(".mp4")
    label = a.label or "%s  %s" % (d.get("tag", ""), d.get("outcome", ""))

    tmp = out.with_suffix(".raw.mp4")
    vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    if not vw.isOpened():
        print("cv2 could not open a writer for %s" % tmp, file=sys.stderr)
        return 3
    kept = 0
    last = None
    for i, fr in enumerate(frames):
        if i % max(1, a.speed):
            continue
        clock = float(fr.get("tick", 0)) * tick_s
        last = draw_frame(fr, me, mirror, label, fr.get("play"), clock)
        vw.write(last)
        kept += 1
    for _ in range(int(a.hold * fps)):     # hold the final board so the result is readable
        if last is not None:
            vw.write(last)
    vw.release()

    # mp4v plays nowhere reliably; H.264 + faststart is what Instagram and phones want.
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(out)], check=True)
        tmp.unlink()
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print("ffmpeg re-encode skipped (%s); raw file left at %s" % (type(e).__name__, tmp), file=sys.stderr)
        out = tmp
    print(json.dumps({"out": str(out), "frames": kept, "fps": fps,
                      "seconds": round(kept / fps + a.hold, 1), "tag": d.get("tag"),
                      "outcome": d.get("outcome"), "crowns": [d.get("crowns_for"), d.get("crowns_against")]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
