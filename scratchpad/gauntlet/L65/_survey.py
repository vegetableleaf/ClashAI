"""How much mineable battle is actually in the HunterCR recordings, and where are the matches?

The owner's ruling was conditional: "if you decide those videos are good, proceed with the mining".
Whether they are good has two halves and this script measures the second one.

  1. FRAMING (settled by eye, L65): full-screen portrait phone capture, fixed camera, whole board in
     frame, card hand + next-card + elixir bar visible, tower HP and match clock visible, and the game's
     own deploy label ("Ice Wizard lvl 16") printed at the placement ring. Everything bridgeblock.mp4
     lacked. Not in question.
  2. QUANTITY, which decides whether mining is a SCALING lever or something else. 97 minutes of video
     cannot hold more than ~32 matches (a ladder match plus its menus is ~3 min), against a 1,638-replay
     corpus -- so the arithmetic matters more than the framing does.

In-battle test, deliberately model-free: every in-battle frame carries the elixir bar across the bottom
of the screen, a saturated magenta strip that no menu or replay-list screen shows. Fraction of magenta
pixels in the bottom band, thresholded, sampled every SAMPLE_S seconds. Contiguous runs separated by a
gap of >= GAP_S become matches.

This CANNOT tell a real ladder match from a spectated/replayed one, and it does not check that a match
is complete (a recording that starts mid-match still counts as one). Both would inflate the count, so
the number it returns is an UPPER bound on usable matches -- which is the direction that matters, since
the question is whether there is enough here to move a scaling curve.

usage: _survey.py [--sample-s 2] [--out <dir>]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import cv2
import numpy as np

VIDEOS = sorted(glob.glob("C:/Users/benpe/Downloads/HunterCR*.mp4"))
BAND = (0.950, 0.980)      # bottom band holding the elixir bar, as a fraction of frame height
GAP_S = 20.0               # a break this long between in-battle samples separates two matches


def magenta_frac(frame: np.ndarray) -> float:
    h = frame.shape[0]
    band = frame[int(h * BAND[0]):int(h * BAND[1])]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    # elixir bar: hue ~ 145-170 (OpenCV 0-179), high saturation, bright
    m = ((hsv[..., 0] > 140) & (hsv[..., 0] < 175) & (hsv[..., 1] > 90) & (hsv[..., 2] > 90))
    return float(m.mean())


def survey(path: str, sample_s: float, out: Path) -> dict:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps * sample_s)))
    fr, i, ts, fracs = [], 0, [], []
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                ts.append(i / fps)
                fracs.append(magenta_frac(frame))
        i += 1
    cap.release()
    fracs = np.asarray(fracs); ts = np.asarray(ts)
    # threshold: the bar occupies a wide, unmistakable slice of the band when present
    thr = 0.08
    inb = fracs > thr
    runs, start = [], None
    for k in range(len(ts)):
        if inb[k] and start is None:
            start = ts[k]
        elif not inb[k] and start is not None:
            if ts[k] - start > 5:
                runs.append((start, ts[k - 1]))
            start = None
    if start is not None:
        runs.append((start, ts[-1]))
    # merge runs separated by less than GAP_S (a brief HUD occlusion is not a match boundary)
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < GAP_S:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(list(r))
    merged = [(round(a, 1), round(b, 1)) for a, b in merged]
    battle_s = sum(b - a for a, b in merged)
    r = {"file": Path(path).name, "duration_s": round(total / fps, 1), "samples": len(ts),
         "in_battle_frac": round(float(inb.mean()), 3), "battle_s": round(battle_s, 1),
         "matches_upper_bound": len(merged), "runs": merged,
         "run_lengths_s": [round(b - a, 1) for a, b in merged]}
    print(json.dumps({k: v for k, v in r.items() if k != "runs"}), flush=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-s", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    a = ap.parse_args()
    res = [survey(p, a.sample_s, a.out) for p in VIDEOS]
    tot_m = sum(r["matches_upper_bound"] for r in res)
    tot_b = sum(r["battle_s"] for r in res)
    summary = {"videos": len(res), "matches_upper_bound": tot_m, "battle_minutes": round(tot_b / 60, 1),
               "corpus_now_icebow": 1638, "corpus_growth_pct": round(100 * tot_m / 1638, 2),
               "doublings": round(np.log2(1 + tot_m / 1638), 4),
               "pp_at_1p50_per_doubling": round(1.50 * np.log2(1 + tot_m / 1638), 3)}
    print(json.dumps(summary), flush=True)
    (a.out / "survey.json").write_text(json.dumps({"per_file": res, "summary": summary}, indent=1),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
