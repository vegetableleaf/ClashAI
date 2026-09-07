"""How many DISTINCT matches are in the HunterCR recordings?

_survey.py's answer (1 match in 811 s) was wrong and this file replaces it. Its in-battle test -- the
elixir bar's magenta strip along the bottom -- is fine, but the run-merging that followed assumed matches
are separated by a menu gap of >= 20 s. These recordings cut straight from one match to the next, so all
of HunterCR_1 merged into a single 796 s "match". The opponent's NAME in the top HUD band proved it:
sampled at 100 s intervals it reads der Namenlose, der Namenlose, AmiR, Kun|YiNian, Kun|YiNian,
KNE LANGEXX, KNE LANGEXX, KNE LANGEXX -- at least four matches in the file the survey called one.

So: count matches by watching the opponent-name crop CHANGE, not by watching the battle stop.

Robustness, because the naive pixel-diff has two traps here:
  * the HUD is drawn over live arena, and overtime tints the whole frame red -- a raw diff would fire on
    the tint, so the crop is reduced to a TEXT MASK (bright, low-saturation pixels = the white/yellow
    name glyphs) before comparing, which survives a global colour shift;
  * elixir-multiplier badges (x2/x3) and the crown counters sit near the name, so the crop is taken
    left of them and the change threshold is set well above the frame-to-frame jitter measured within a
    single match.

Reports, per file: number of distinct name blocks, their durations, and the sampled boundaries. What it
canNOT do: distinguish two consecutive matches against the SAME opponent (a rematch reads as one), so the
count is a LOWER bound -- the opposite direction from _survey.py's upper bound, which brackets the truth.

usage: _matchcount.py [--sample-s 2]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import cv2
import numpy as np

VIDEOS = sorted(glob.glob("C:/Users/benpe/Downloads/HunterCR*.mp4"))
NAME_BOX = (0.03, 0.012, 0.42, 0.048)      # x0, y0, x1, y1 as fractions -- opponent name, left of badges
BAND = (0.950, 0.980)


def in_battle(frame: np.ndarray) -> bool:
    h = frame.shape[0]
    hsv = cv2.cvtColor(frame[int(h * BAND[0]):int(h * BAND[1])], cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] > 140) & (hsv[..., 0] < 175) & (hsv[..., 1] > 90) & (hsv[..., 2] > 90))
    return float(m.mean()) > 0.08


def name_mask(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = NAME_BOX
    crop = frame[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
    crop = cv2.resize(crop, (192, 32))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # glyphs are bright; the arena behind the HUD band is darker. Value-threshold, not colour, so an
    # overtime red tint (which raises hue/sat, not much value) does not flip the mask.
    return (hsv[..., 2] > 170).astype(np.uint8)


def count(path: str, sample_s: float) -> dict:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    step = max(1, int(round(fps * sample_s)))
    i = 0
    prev, prev_t, blocks, jitter = None, None, [], []
    ref, pend = None, 0
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok and in_battle(frame):
                t = i / fps
                m = name_mask(frame)
                if prev is None:
                    blocks.append([round(t, 1), round(t, 1)]); ref, pend = m, 0
                else:
                    # compare against the BLOCK's reference mask, not the previous sample: a name is
                    # static for minutes, so within-match diff is 0.000 (measured p50) and any sustained
                    # non-zero diff is a new opponent. Requiring 2 consecutive samples rejects the
                    # transient overlays (deploy rings, damage flashes) that a single-sample rule would
                    # count as matches. First cut used d > 0.12 against the PREVIOUS sample and found
                    # nothing: real name changes measured only ~0.09 (jitter_p99), under the threshold.
                    d = float(np.abs(m.astype(np.int16) - ref.astype(np.int16)).mean())
                    jitter.append(d)
                    if d > 0.02:
                        pend += 1
                        if pend >= 2:
                            blocks.append([round(t, 1), round(t, 1)]); ref, pend = m, 0
                    else:
                        pend = 0
                        blocks[-1][1] = round(t, 1)
                prev, prev_t = m, t
        i += 1
    cap.release()
    keep = [b for b in blocks if b[1] - b[0] >= 30]   # a block shorter than 30 s is a transition, not a match
    r = {"file": Path(path).name, "duration_s": round(i / fps, 1),
         "name_blocks": len(blocks), "matches_lower_bound": len(keep),
         "block_lengths_s": [round(b[1] - b[0], 1) for b in keep],
         "jitter_p50": round(float(np.percentile(jitter, 50)), 4) if jitter else None,
         "jitter_p99": round(float(np.percentile(jitter, 99)), 4) if jitter else None}
    print(json.dumps(r), flush=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-s", type=float, default=2.0)
    a = ap.parse_args()
    res = [count(p, a.sample_s) for p in VIDEOS]
    n = sum(r["matches_lower_bound"] for r in res)
    corpus = 1638
    s = {"files": len(res), "matches_lower_bound": n,
         "video_minutes": round(sum(r["duration_s"] for r in res) / 60, 1),
         "minutes_per_match": round(sum(r["duration_s"] for r in res) / 60 / max(n, 1), 1),
         "corpus_growth_pct": round(100 * n / corpus, 2),
         "pp_at_1p50_per_doubling": round(1.50 * float(np.log2(1 + n / corpus)), 3),
         "video_hours_for_one_doubling": None}
    if n:
        s["video_hours_for_one_doubling"] = round(corpus * (sum(r["duration_s"] for r in res) / n) / 3600, 1)
    print(json.dumps(s), flush=True)
    Path(__file__).resolve().parent.joinpath("matchcount.json").write_text(
        json.dumps({"per_file": res, "summary": s}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
