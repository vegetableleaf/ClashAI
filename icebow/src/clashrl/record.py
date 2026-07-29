"""Record human play on PC (screen frames + mouse actions) for imitation learning.

You play Clash Royale normally via Google Play Games; this captures the game
region to a video and logs every mouse click (position + timestamp). Later the
labeler turns that into (observation, action) pairs to pretrain the policy.

Coordinates: the process is set DPI-aware so mouse positions (physical pixels)
line up with the captured frames.
"""
from __future__ import annotations

import ctypes
import json
import time

import cv2

from .capture import WindowCapture


def _set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def record(cfg) -> None:
    _set_dpi_aware()
    try:
        from pynput import mouse
    except Exception as exc:  # noqa: BLE001
        print(f"[record] pynput is required for recording ({exc}). "
              "Install it: pip install pynput")
        return

    capture = WindowCapture(
        cfg.get("window", "title_contains", default=None),
        cfg.get("window", "region", default=None),
    )
    region = capture.region
    if region is None:
        print("[record] No capture region; set window.region in config.yaml.")
        return

    fps = float(cfg.get("record", "fps", default=12))
    log_moves = bool(cfg.get("record", "log_moves", default=False))
    session = cfg.path(cfg.get("record", "out_dir", default="data/sessions"),
                       time.strftime("%Y%m%d_%H%M%S"))
    session.mkdir(parents=True, exist_ok=True)

    w, h = int(region.width), int(region.height)
    writer = cv2.VideoWriter(str(session / "video.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():  # codec fallback
        writer = cv2.VideoWriter(str(session / "video.avi"),
                                 cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))

    start = time.time()
    events: list[dict] = []

    def on_click(x, y, button, pressed):
        events.append({"t": round(time.time() - start, 4), "type": "click",
                       "x": int(x), "y": int(y), "button": str(button), "pressed": bool(pressed)})

    def on_move(x, y):
        events.append({"t": round(time.time() - start, 4), "type": "move",
                       "x": int(x), "y": int(y)})

    listener = mouse.Listener(on_click=on_click, on_move=on_move if log_moves else None)
    listener.start()

    frame_times: list[float] = []
    period = 1.0 / fps
    print(f"[record] recording to {session}\n[record] play your matches now; press Ctrl+C to stop.")
    try:
        next_t = time.time()
        while True:
            frame = capture.grab()
            if frame is not None:
                writer.write(frame)
                frame_times.append(round(time.time() - start, 4))
            next_t += period
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()  # fell behind; resync
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        writer.release()
        (session / "events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events), encoding="utf-8")
        (session / "meta.json").write_text(json.dumps({
            "fps": fps,
            "start_time": start,
            "region": [int(region.left), int(region.top), w, h],
            "n_frames": len(frame_times),
            "frame_times": frame_times,
        }), encoding="utf-8")
        clicks = sum(1 for e in events if e["type"] == "click" and e["pressed"])
        print(f"[record] saved {len(frame_times)} frames and {clicks} clicks to {session}")
