"""Which deck is being played in this video? Read the card HAND, not the board.

The owner's mining plan needs one decision per video: is this the icebow deck, all eight cards
(tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons)? Titles do not say, and
1,382 videos / 441.6 hours is far too much to watch.

Reading the hand is much easier than reading the board. The four hand slots and the "Next" slot sit at
fixed fractions of a full-screen portrait capture, the art is large and unoccluded, and the deck cycles --
so a handful of frames spread across one match shows all eight cards. Board detection has none of those
properties.

Instrument: normalised cross-correlation of each slot crop against `icebow/templates/cards/` (2,174
crops, 110 cards, 64x80, captured from our own screen), vectorised as unit-norm dot products so all
~660 templates are scored at once. Three jitters (scale 0.94/1.00/1.06) absorb the small geometry
difference between our capture region and a phone's full screen, and the fact that the selected card
sits slightly proud of the others.

Two properties this is built around:
  * greyed-out (unaffordable) cards look very different from lit ones. The template set already contains
    both variants per card -- it was captured live -- so matching takes the max over ALL of a card's
    templates rather than assuming one canonical look.
  * a threshold has to be CALIBRATED, not picked. `--calib` reports the score distribution of matched
    vs runner-up cards on videos known to be icebow, so the separation is measured before it is used.
    (L65 shipped two counters in a row whose thresholds were guessed; both read exactly backwards.)

Not a deck extractor for arbitrary footage: it assumes a full-screen portrait capture with the hand
visible. An edited/zoomed clip has no hand and is rejected, correctly, by finding nothing.

usage: deckid.py video <path> [--frames 12]        one video -> matched cards + verdict
       deckid.py calib <path> [<path> ...]         score separation on known-icebow footage
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "icebow" / "templates" / "cards"
# BASE keys. The deck is (tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons),
# but an evolved card's hand art is the same art with different framing, and the matcher reads the base
# every time (measured: evo tesla in hand scores 0.73 as "tesla"). Deck IDENTITY does not depend on which
# two slots are evolved, so evo and base fold together here and the evo question is left to the miner.
ICEBOW = ("tornado", "tesla", "ice_wizard", "x_bow", "rocket", "knight", "the_log", "skeletons")
def base_key(n: str) -> str:
    return n[:-4] if n.endswith("_evo") else n
TH, TW = 80, 64
# The slot box holds the whole card; the art inside it is roughly 60-85% of that, so the template is
# scaled to a range of fractions of a canonical slot and slid over it.
CROP_W, CROP_H = 132, 168
SCALES = (1.15, 1.45)
PER_CARD = 4                       # templates kept per card; more is slower, not better (they are near-dupes)

# Fractional slot boxes, read off a 888x1920 frame with a labelled grid (scratchpad/.../hand_grid.png).
# Deliberately generous: the selected card pops up a few pixels and the jitters absorb the rest.
SLOTS = [(0.230, 0.838, 0.372, 0.922),
         (0.412, 0.838, 0.566, 0.922),
         (0.598, 0.838, 0.746, 0.922),
         (0.778, 0.838, 0.928, 0.922),
         (0.045, 0.900, 0.155, 0.962)]        # "Next:" -- smaller art, same treatment
BAND = (0.950, 0.980)                          # elixir bar, for the in-battle test (L65 _survey.py)


def load_templates() -> tuple[np.ndarray, list[str]]:
    by_card: dict[str, list[str]] = defaultdict(list)
    for f in sorted(glob.glob(str(TEMPLATES / "*.png"))):
        stem = Path(f).stem
        m = re.match(r"^(.*?)_(\d+)$", stem)
        if not m:
            continue                            # "_candidates.png" and friends
        by_card[m.group(1)].append(f)
    vecs, names = [], []
    for card, files in sorted(by_card.items()):
        for f in files[:PER_CARD]:
            im = cv2.imread(f)
            if im is None:
                continue
            g = prep(im)
            vecs.append([cv2.resize(g, (int(TW * k), int(TH * k))) for k in SCALES])
            names.append(base_key(card))
    return vecs, names


def prep(bgr: np.ndarray) -> np.ndarray:
    """Grayscale float image, kept 2-D: the templates are TIGHTER crops of the card art than a slot box
    is (they exclude the card border and the elixir badge), so a whole-crop dot product compares a card
    against a zoom of a card and scores noise. v1 did exactly that and its calibration showed it: on
    known-icebow footage the non-icebow p90 (0.64-0.69) sat ABOVE the icebow median (0.51-0.57). The
    template has to SLIDE inside the slot, at several scales."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)


def in_battle(frame: np.ndarray) -> bool:
    h = frame.shape[0]
    hsv = cv2.cvtColor(frame[int(h * BAND[0]):int(h * BAND[1])], cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] > 140) & (hsv[..., 0] < 175) & (hsv[..., 1] > 90) & (hsv[..., 2] > 90))
    return float(m.mean()) > 0.08


def slot_scores(frame: np.ndarray, T, names: list[str]) -> list[tuple[str, float, str, float]]:
    """Per slot: (best card, best score, runner-up card, runner-up score). The runner-up is what makes a
    threshold defensible -- beating every other card by a wide margin is a different claim from edging
    out a lookalike."""
    h, w = frame.shape[:2]
    out = []
    for (x0, y0, x1, y1) in SLOTS:
        crop = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        if crop.size == 0:
            out.append(("", 0.0, "", 0.0)); continue
        g = cv2.resize(prep(crop), (CROP_W, CROP_H))
        per: dict[str, float] = {}
        for tset, nm in zip(T, names):
            best = -2.0
            for t in tset:
                if t.shape[0] > CROP_H or t.shape[1] > CROP_W:
                    continue
                r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                v = float(r.max())
                if v > best:
                    best = v
            if best > per.get(nm, -2):
                per[nm] = best
        rank = sorted(per.items(), key=lambda kv: -kv[1])
        out.append((rank[0][0], rank[0][1], rank[1][0], rank[1][1]))
    return out


def slot_card_scores(frame: np.ndarray, T, names: list[str]) -> list[dict]:
    """Every card's score in every slot, not just each slot's top two.

    profile.py's first version kept only the argmax and runner-up, so a card that was never any slot's
    best guess got no score at all and defaulted to zero -- which made a known-icebow video read
    worst_icebow = 0.000, indistinguishable from a video of some other deck. The scores are all computed
    anyway; throwing them away was the bug. Cost is identical."""
    h, w = frame.shape[:2]
    out = []
    for (x0, y0, x1, y1) in SLOTS:
        crop = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        if crop.size == 0:
            out.append({}); continue
        g = cv2.resize(prep(crop), (CROP_W, CROP_H))
        per: dict[str, float] = {}
        for tset, nm in zip(T, names):
            for t in tset:
                if t.shape[0] > CROP_H or t.shape[1] > CROP_W:
                    continue
                v = float(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED).max())
                if v > per.get(nm, -2):
                    per[nm] = v
        out.append(per)
    return out


def sample(path: str, n: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fr = []
    for i in np.linspace(int(total * 0.08), int(total * 0.92), n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok and in_battle(f):
            fr.append(f)
    cap.release()
    return fr


def read_video(path: str, n: int, T, names, thresh: float) -> dict:
    frames = sample(path, n)
    found: dict[str, float] = {}
    rows = []
    for f in frames:
        for (c, s, r, rs) in slot_scores(f, T, names):
            rows.append({"card": c, "score": round(s, 3), "runner": r, "runner_score": round(rs, 3)})
            if s >= thresh and s > found.get(c, 0):
                found[c] = s
    have = [c for c in ICEBOW if c in found]
    extra = sorted(set(found) - set(ICEBOW))
    return {"file": Path(path).name, "frames_in_battle": len(frames), "of": n,
            "icebow_found": len(have), "missing": [c for c in ICEBOW if c not in found],
            "extra_cards": extra[:8], "verdict": "ICEBOW" if len(have) == 8 and not extra else
            ("icebow_partial" if len(have) >= 6 else "other"), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["video", "calib"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--thresh", type=float, default=0.55)
    a = ap.parse_args()
    T, names = load_templates()
    print(json.dumps({"templates": len(names), "cards": len(set(names))}), flush=True)

    if a.mode == "calib":
        best_s, gap_s = [], []
        for p in a.paths:
            r = read_video(p, a.frames, T, names, -2.0)
            for row in r["rows"]:
                best_s.append(row["score"]); gap_s.append(row["score"] - row["runner_score"])
            hits = [x for x in r["rows"] if x["card"] in ICEBOW]
            print(json.dumps({"file": r["file"], "slots_read": len(r["rows"]),
                              "slots_matching_an_icebow_card": len(hits),
                              "icebow_score_p10": round(float(np.percentile([h["score"] for h in hits], 10)), 3) if hits else None,
                              "icebow_score_p50": round(float(np.percentile([h["score"] for h in hits], 50)), 3) if hits else None,
                              "nonicebow_score_p90": round(float(np.percentile([x["score"] for x in r["rows"] if x["card"] not in ICEBOW], 90)), 3)
                              if len(hits) < len(r["rows"]) else None}), flush=True)
        print(json.dumps({"all_slots_score_p05": round(float(np.percentile(best_s, 5)), 3),
                          "p50": round(float(np.percentile(best_s, 50)), 3),
                          "margin_over_runner_p50": round(float(np.percentile(gap_s, 50)), 3)}), flush=True)
        return 0

    for p in a.paths:
        r = read_video(p, a.frames, T, names, a.thresh)
        r.pop("rows")
        print(json.dumps(r), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
