"""Per-card score profile for each video -- the readout the per-slot argmax should have been.

deckid.py's first two calibrations both looked broken for the same reason: they asked "what does this
slot show?" and scored the answer. But a slot can be occluded, mid-drag, or covered by an emote, and the
"Next" slot is drawn smaller -- so per-slot accuracy is not the quantity that decides a VIDEO.

What decides a video is: for each of the eight icebow cards, does it EVER appear with a strong match
anywhere in the sampled hands? A deck cycles, so over a handful of frames all eight of a player's cards
pass through the hand. A video of a different deck may share two or three commodity cards (log, rocket,
skeletons appear in many lists) but cannot show all eight.

So: profile = max score per card over every slot of every sampled frame. The verdict compares the WORST
of the eight icebow maxima against the best non-icebow maximum. If a deck is really icebow, its weakest
member still beats every card it does not play.

Run over known-icebow footage AND an unknown channel sample together, so the threshold is read off the
gap between two populations instead of guessed. Writes profile.json.

usage: profile.py <video> [<video> ...] [--frames 6]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deckid import ICEBOW, in_battle, load_templates, slot_card_scores   # noqa: E402


def profile(path: str, n: int, T, names) -> dict:
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    best: dict[str, float] = {}
    used = 0
    for i in np.linspace(int(total * 0.05), int(total * 0.95), n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if not ok or not in_battle(f):
            continue
        used += 1
        for per in slot_card_scores(f, T, names):
            for card, sc in per.items():
                if sc > best.get(card, -2):
                    best[card] = sc
    cap.release()
    ice = {c: round(best.get(c, 0.0), 3) for c in ICEBOW}   # every card now HAS a score
    other = sorted(((v, k) for k, v in best.items() if k not in ICEBOW), reverse=True)[:5]
    worst_ice = min(ice.values()) if ice else 0.0
    best_other = other[0][0] if other else 0.0
    return {"file": Path(path).name, "shape": [w, h], "portrait": h > w,
            "frames_used": used, "of": n, "icebow": ice,
            "worst_icebow": round(worst_ice, 3), "best_other": round(best_other, 3),
            "separation": round(worst_ice - best_other, 3),
            "top_other": [[k, round(v, 3)] for v, k in other]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--out", default="scratchpad/gauntlet/L66/profile.json")
    a = ap.parse_args()
    T, names = load_templates()
    res = []
    for p in a.paths:
        r = profile(p, a.frames, T, names)
        res.append(r)
        print(json.dumps({k: r[k] for k in ("file", "shape", "frames_used", "worst_icebow",
                                            "best_other", "separation")}), flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
