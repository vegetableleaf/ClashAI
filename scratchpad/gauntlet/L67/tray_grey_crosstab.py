"""L67w P1: where do the two greyness signals of tray_grey_probe.py disagree, and which one is right?

Cross-tabulates badge_pink (< / >= --pink) against card_sat (< / >= --sat) over sampled clip frames and writes a
contact sheet of crops from each disagreeing cell, so the tap-path rule uses the signal that matches what the game
shows.

usage: python tray_grey_crosstab.py --clips <clip.mp4> [...] --sheet <png> [--every 2.0] [--pink 0.05] [--sat 0.15]
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "icebow" / "src"))

from tray_grey_probe import measures, slot_boxes                          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", type=Path, required=True)
    ap.add_argument("--sheet", type=Path, required=True)
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--pink", type=float, default=0.05)
    ap.add_argument("--sat", type=float, default=0.15)
    a = ap.parse_args()
    from clashrl.config import Config
    cfg = Config.load()
    slots = cfg.get("hand", "slots")
    card_w, card_h = float(cfg.get("hand", "card_w")), float(cfg.get("hand", "card_h"))
    cells = collections.Counter()
    by_slot = collections.Counter()
    samples = collections.defaultdict(list)
    for clip in a.clips:
        cap = cv2.VideoCapture(str(clip))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for fi in range(0, n, max(1, int(round(fps * a.every)))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, fr = cap.read()
            if not ok:
                continue
            h, w = fr.shape[:2]
            boxes = slot_boxes(w, h, slots, card_w, card_h)
            for k, (cs, bp) in enumerate(measures(fr, boxes)):
                key = ("badge pink" if bp >= a.pink else "badge grey", "card colour" if cs >= a.sat else "card grey")
                cells[key] += 1
                by_slot[(k,) + key] += 1
                if key in (("badge grey", "card colour"), ("badge pink", "card grey")) and len(samples[key]) < 24:
                    (x0, y0, x1, y1), (bx0, by0, bx1, by1) = boxes[k]
                    samples[key].append((k, bp, cs, fr[y0:max(y1, by1), min(x0, bx0):max(x1, bx1)].copy()))
                elif len(samples[key]) < 8:
                    (x0, y0, x1, y1), (bx0, by0, bx1, by1) = boxes[k]
                    samples[key].append((k, bp, cs, fr[y0:max(y1, by1), min(x0, bx0):max(x1, bx1)].copy()))
    print("crosstab", dict(cells))
    for k in range(4):
        print(f"  slot {k}:", {f"{b}/{c}": by_slot[(k, b, c)] for (b, c) in cells})
    rows = []
    for key in sorted(samples):
        sel = samples[key][:12]
        tiles = []
        for k, bp, cs, img in sel:
            t = cv2.resize(img, (90, 112))
            bar = np.full((16, 90, 3), 255, np.uint8)
            cv2.putText(bar, f"s{k} p{bp:.2f} c{cs:.2f}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(np.vstack([bar, t]))
        while len(tiles) < 12:
            tiles.append(np.full((128, 90, 3), 200, np.uint8))
        label = np.full((128, 130, 3), 255, np.uint8)
        cv2.putText(label, key[0], (4, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(label, key[1], (4, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        rows.append(np.hstack([label] + tiles))
    cv2.imwrite(str(a.sheet), np.vstack(rows))
    print("sheet", a.sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
