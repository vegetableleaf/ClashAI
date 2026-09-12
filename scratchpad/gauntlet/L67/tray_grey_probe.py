"""L67w P1 probe: can the tap path tell a GREYED (unaffordable) tray card from a coloured one, independent of the
card art? Measured on the owner's overlay clips (the bot's own captured frames, re-encoded).

For every sampled frame and each of the 4 tray slots (the tray reader's own slot centres, config hand.slots) it
measures two things:
  card_sat     mean HSV saturation over the tray reader's card crop (card_w / card_h half sizes)
  badge_pink   fraction of MAGENTA pixels in a box around the elixir-cost badge at the card's bottom centre --
               the drop is pink when the card is affordable and grey when it is not, whatever the art
and prints both histograms. A contact sheet of crops sampled across the badge_pink range is written so the
threshold is chosen by eye, not guessed.

usage: python tray_grey_probe.py --clips <clip.mp4> [...] --sheet <png> [--every 1.0]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "icebow" / "src"))


def slot_boxes(w, h, slots, card_w, card_h):
    out = []
    for cx, cy in slots:
        card = (int((cx - card_w) * w), int((cy - card_h) * h), int((cx + card_w) * w), int((cy + card_h) * h))
        badge = (int((cx - 0.03) * w), int((cy + 0.015) * h), int((cx + 0.03) * w), int((cy + 0.06) * h))
        out.append((card, badge))
    return out


def measures(frame, boxes):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    res = []
    for (cx0, cy0, cx1, cy1), (bx0, by0, bx1, by1) in boxes:
        c = hsv[cy0:cy1, cx0:cx1]
        b = hsv[by0:by1, bx0:bx1]
        card_sat = float(c[..., 1].mean()) / 255.0 if c.size else float("nan")
        # OpenCV hue is 0-179: magenta/pink ~ 140-170, saturated and bright enough to not be shadow
        pink = ((b[..., 0] >= 140) & (b[..., 0] <= 172) & (b[..., 1] >= 90) & (b[..., 2] >= 90)) if b.size else np.zeros(1, bool)
        res.append((card_sat, float(pink.mean())))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", type=Path, required=True)
    ap.add_argument("--sheet", type=Path, required=True)
    ap.add_argument("--every", type=float, default=1.0)
    a = ap.parse_args()
    from clashrl.config import Config
    cfg = Config.load()
    slots = cfg.get("hand", "slots")
    card_w, card_h = float(cfg.get("hand", "card_w")), float(cfg.get("hand", "card_h"))
    rows, crops = [], []
    rng = np.random.default_rng(0)
    for clip in a.clips:
        cap = cv2.VideoCapture(str(clip))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, int(round(fps * a.every)))
        for fi in range(0, n, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, fr = cap.read()
            if not ok:
                continue
            h, w = fr.shape[:2]
            boxes = slot_boxes(w, h, slots, card_w, card_h)
            for k, (cs, bp) in enumerate(measures(fr, boxes)):
                rows.append((cs, bp))
                if rng.random() < 0.02:
                    (x0, y0, x1, y1), (bx0, by0, bx1, by1) = boxes[k]
                    y1e = max(y1, by1)
                    crops.append((bp, cs, fr[y0:y1e, min(x0, bx0):max(x1, bx1)].copy()))
    R = np.asarray(rows)
    print(f"slot samples {len(R)} from {len(a.clips)} clips")
    for name, col, edges in (("badge_pink", 1, [0, .01, .03, .06, .1, .15, .2, .3, .4, .6, 1.01]),
                             ("card_sat", 0, [0, .1, .15, .2, .25, .3, .35, .4, .5, .6, 1.01])):
        hist, _ = np.histogram(R[:, col], bins=edges)
        print(name, " ".join(f"[{edges[i]:.2f},{edges[i+1]:.2f}):{hist[i]}" for i in range(len(hist))))
    # contact sheet: up to 6 crops per badge_pink bin, labelled
    bins = [(0, .01), (.01, .05), (.05, .1), (.1, .2), (.2, .4), (.4, 1.01)]
    tiles = []
    for lo, hi in bins:
        sel = [c for c in crops if lo <= c[0] < hi][:8]
        row = []
        for bp, cs, img in sel:
            t = cv2.resize(img, (96, 120))
            bar = np.full((18, 96, 3), 255, np.uint8)
            cv2.putText(bar, f"p{bp:.2f} s{cs:.2f}", (2, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
            row.append(np.vstack([bar, t]))
        while len(row) < 8:
            row.append(np.full((138, 96, 3), 200, np.uint8))
        label = np.full((138, 110, 3), 255, np.uint8)
        cv2.putText(label, f"pink {lo:.2f}-{hi:.2f}", (4, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.hstack([label] + row))
    cv2.imwrite(str(a.sheet), np.vstack(tiles))
    print("sheet", a.sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
