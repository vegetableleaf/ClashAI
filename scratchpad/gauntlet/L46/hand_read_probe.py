"""Run the hand recogniser on frames of a recorded live match: per-slot best identity + score,
so an unread slot (-1) is explained by its score rather than guessed at."""
import sys, cv2, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.vision import Vision
cfg = Config.load(sys.argv[1]); vid = sys.argv[2]; every = int(sys.argv[3]) if len(sys.argv) > 3 else 92
v = Vision(cfg); print("deck", v.deck_keys, "threshold", v.match_threshold, "templates per key", [len(t) for t in v._card_tpls])
cap = cv2.VideoCapture(vid); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); w = int(cap.get(3)); h = int(cap.get(4)); print("video", vid, n, "frames", w, "x", h)
fi = 0; rows = []
while True:
    ok, fr = cap.read()
    if not ok: break
    if fi % every == 0:
        slots = []
        for si, (cx, cy) in enumerate(v.hand_slots):
            crop = v.hand_crop(fr, cx, cy)
            i, s = v.match_card(crop)
            # runner-up: score of the best template of every other key
            slots.append((i, round(s, 3)))
        rows.append((fi, slots)); print(f"frame {fi:5d} t={fi/18.5:6.1f}s  " + "  ".join(f"[{v.deck_keys[i] if i >= 0 else '-1':10s} {s:.2f}]" for i, s in slots))
    fi += 1
