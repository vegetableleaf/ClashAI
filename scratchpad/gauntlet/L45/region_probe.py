"""Reproduce the s1b/s3 frozen-read failure: every 4 s build a FRESH WindowCapture (exactly what a new session does),
log the region it locks onto + what Vision reads from that region, across the match-end -> end-screen transition.
Also runs _render_area on the raw client area and saves it when the lock differs from the reference in-match lock."""
import sys, time, os, cv2, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config; from clashrl.capture import WindowCapture; from clashrl.vision import Vision
cfg = Config.load(); V = Vision(cfg); out = sys.argv[1]; dur = float(sys.argv[2]); os.makedirs(out, exist_ok=True)
t0 = time.time(); last = None
while time.time() - t0 < dur:
    c = WindowCapture(cfg.get("window", "title_contains", default=None), None)
    r = c.region; fr = c.grab()
    st = V.detect_state(fr) if fr is not None else None
    hand = V.recognize_hand(fr) if fr is not None else None; el = V.read_elixir_frac(fr) if fr is not None else None
    line = f"{time.strftime('%H:%M:%S')} region {r} locked={c._render_locked} state={st} hand={hand} elixir={el}"
    print(line, flush=True)
    if r != last and fr is not None:
        cv2.imwrite(os.path.join(out, f"lock_{time.strftime('%H%M%S')}_{r.left}_{r.top}_{r.width}x{r.height}.png"), cv2.resize(fr, None, fx=0.5, fy=0.5))
    last = r; time.sleep(4)
