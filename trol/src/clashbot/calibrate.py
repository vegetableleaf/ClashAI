"""Interactive tools to calibrate coordinates and capture detection templates."""
from __future__ import annotations

import time

import cv2

from .capture import WindowCapture
from .vision import Vision


def _capture_from_cfg(cfg) -> WindowCapture:
    return WindowCapture(
        cfg.get("window", "title_contains", default=None),
        cfg.get("window", "region", default=None),
    )


def capture_template(cfg, name: str, cards: bool = False) -> None:
    """Grab the current frame and let you drag-select a region to save as a template."""
    capture = _capture_from_cfg(cfg)
    vision = Vision(cfg)
    print("Bring the game into view. Capturing in 2 seconds...")
    time.sleep(2)
    frame = capture.grab()
    if frame is None:
        print("Could not capture the window. Set window.region in config.yaml.")
        return

    work = vision.work(frame)
    roi = cv2.selectROI("Drag a box, then press ENTER (or c to cancel)", work, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = (int(v) for v in roi)
    if w == 0 or h == 0:
        print("Cancelled.")
        return

    crop = work[y:y + h, x:x + w]
    out_dir = cfg.path("templates", "cards") if cards else cfg.path("templates")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = name if name.endswith(".png") else name + ".png"
    out_path = out_dir / fname
    cv2.imwrite(str(out_path), crop)
    print(f"Saved {out_path}  ({w}x{h} at work width {work.shape[1]})")


def calibrate(cfg) -> None:
    """Live preview with overlays; left-click prints normalized coordinates."""
    capture = _capture_from_cfg(cfg)
    vision = Vision(cfg)
    win = "calibrate  (click = print normalized coords, q = quit)"
    param = {"W": 1, "H": 1}

    def on_mouse(event, x, y, _flags, p):
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"normalized: [{x / p['W']:.3f}, {y / p['H']:.3f}]")

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse, param)

    while True:
        frame = capture.grab()
        if frame is None:
            print("No capture; set window.region in config.yaml.")
            break
        work = vision.work(frame).copy()
        H, W = work.shape[:2]
        param["W"], param["H"] = W, H

        for (nx, ny) in cfg.get("hand", "slots", default=[]):
            cv2.circle(work, (int(nx * W), int(ny * H)), 6, (0, 255, 0), 2)
        bar_y = cfg.get("elixir", "bar_y", default=0.965)
        for nx in cfg.get("elixir", "pip_xs", default=[]):
            cv2.circle(work, (int(nx * W), int(bar_y * H)), 3, (255, 0, 255), -1)
        tc = cfg.get("target", "tower_center", default=[0.5, 0.14])
        r = cfg.get("target", "jitter_radius", default=0.04)
        cv2.circle(work, (int(tc[0] * W), int(tc[1] * H)), int(r * W), (0, 0, 255), 2)
        for key in ("button", "good_game"):
            pt = cfg.get("emote", key, default=None)
            if pt:
                cv2.drawMarker(work, (int(pt[0] * W), int(pt[1] * H)), (0, 220, 255),
                               cv2.MARKER_CROSS, 12, 2)

        state, _ = vision.detect_state(frame)
        elixir = vision.read_elixir(frame)
        cv2.putText(work, f"{state.name}  elixir~{elixir}", (6, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow(win, work)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
