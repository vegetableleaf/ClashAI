"""Offline: does a 38-px-short region lock (what a fresh WindowCapture takes on the MATCH_END screen)
break hand/elixir reads on an IN_MATCH frame? Uses the half-scale probe frame of the 1198 lock."""
import sys, cv2, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.vision import Vision
cfg = Config.load()
v = Vision(cfg)
f = cv2.imread("../scratchpad/gauntlet/L45/region_probe/lock_225240_734_18_657x1198.png")
h, w = f.shape[:2]
full = cv2.resize(f, (657, 1198))
print("frame", f.shape, "-> upscaled", full.shape)
for trim, label in [(0, "lock 1198 (in-match scan)"), (38, "lock 1160 (MATCH_END scan)"), (18, "lock 1216 top0 (pad 18 rows)")]:
    if label.startswith("lock 1216"):
        img = np.vstack([np.zeros((18, 657, 3), np.uint8), full])
    else:
        img = full[:1198 - trim]
    hand = v.recognize_hand(img)
    try:
        el = v.read_elixir(img); elf = v.read_elixir_frac(img)
    except Exception as e:
        el, elf = "err", repr(e)
    nxt = None
    try:
        nxt = v.recognize_next(img)
    except Exception:
        pass
    print(f"{label:32s} shape {img.shape[:2]} hand {hand} next {nxt} elixir {el} / {elf}")
