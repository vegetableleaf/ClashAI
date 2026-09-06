"""Does the board detector fire AT ALL on third-party gameplay video? (S2 IDM gate, precondition.)

S2's written gate is "detector-as-IDM precision/recall measured on engine ground truth before labelling
video". That sentence assumes the detector produces boxes on the video in the first place. It was trained
on OUR capture -- a 657x1198 PORTRAIT phone-screen region read at imgsz 960 -- and the video we would mine
is 640x360 LANDSCAPE, where the phone screen occupies maybe 200x360 px. That is roughly 10x fewer pixels
on the arena. If recall collapses there, video mining costs a whole re-label campaign, not a pipeline,
and we want to know that in an hour rather than after days of building.

This probe measures ONE thing on matched frame counts: detections per frame, and how many of them are
whitelist cards, on
  A) our own recorded session (the distribution the weights were fitted on)  -- the control
  B) bridgeblock.mp4, third-party gameplay video                             -- the transfer case
plus C) B upscaled to the detector's native region size, which separates "too few pixels" from
"different look" -- if upscaling recovers most of the gap it is a resolution problem (solvable by
sourcing 1080p video); if it does not, it is a domain problem (needs re-labelling).

NOT a precision/recall measurement: there is no ground truth here, only detection counts. A detector that
fires confidently on nothing real would look identical to a working one. This probe can only FALSIFY
transfer, never confirm it -- if B and C survive, the real labelled measurement still has to be run.

usage: _transfer_probe.py [--n 60] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "icebow" / "src"))

SESSION = REPO / "icebow" / "data" / "sessions" / "20260815_222309" / "video.mp4"
VIDEO = REPO / "bridgeblock.mp4"


def sample(path: Path, n: int) -> list[np.ndarray]:
    """n frames spread evenly over the middle 80% of the clip (menus live at the ends)."""
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    lo, hi = int(total * 0.1), int(total * 0.9)
    idx = np.linspace(lo, hi, n).astype(int)
    out = []
    for i in idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, fr = cap.read()
        if ok:
            out.append(fr)
    cap.release()
    return out


def run(det, frames: list[np.ndarray], label: str, conf: float, whitelist: set[str]) -> dict:
    n_det, n_white, confs, per_frame = 0, 0, [], []
    cards = Counter()
    for fr in frames:
        ds = det.detect(fr, conf=conf)
        per_frame.append(len(ds))
        n_det += len(ds)
        for d in ds:
            confs.append(float(d.conf))
            cards[str(d.cls)] += 1
            if str(getattr(d, "base", d.cls)) in whitelist:     # whitelist holds BASE keys
                n_white += 1
    r = {"arm": label, "frames": len(frames), "dets": n_det, "whitelist_dets": n_white,
         "dets_per_frame": round(n_det / max(len(frames), 1), 2),
         "whitelist_per_frame": round(n_white / max(len(frames), 1), 2),
         "frames_with_any_det": int(sum(1 for k in per_frame if k)),
         "mean_conf": round(float(np.mean(confs)), 3) if confs else None,
         "top_classes": cards.most_common(6)}
    print(json.dumps(r), flush=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    a = ap.parse_args()

    from clashrl.config import Config                       # noqa: E402
    from clashrl.replay_mine import load_detector           # noqa: E402

    cfg = Config.load(REPO / "icebow" / "config" / "config.yaml")   # dataclass: .load(), not the ctor
    det = load_detector(cfg)
    if not det.available:
        print("NO_WEIGHTS -- detector unavailable"); return 2
    wl = set(cfg.get("observation", "detector_cards", default=[]) or [])
    print(json.dumps({"whitelist": len(wl), "imgsz": det._imgsz, "conf": a.conf}), flush=True)

    res = []
    fa = sample(SESSION, a.n)
    res.append(run(det, fa, "A_own_session", a.conf, wl))
    fb = sample(VIDEO, a.n)
    res.append(run(det, fb, "B_video_native", a.conf, wl))
    # C: upscale the video frame so its HEIGHT matches our capture region's height. Separates
    # "not enough pixels" from "does not look like our screen".
    hh = fa[0].shape[0] if fa else 1198
    fc = [cv2.resize(f, (int(f.shape[1] * hh / f.shape[0]), hh), interpolation=cv2.INTER_CUBIC) for f in fb]
    res.append(run(det, fc, "C_video_upscaled", a.conf, wl))

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "transfer_probe.json").write_text(json.dumps({
        "session": str(SESSION), "video": str(VIDEO), "shapes": {
            "session": list(fa[0].shape) if fa else None, "video": list(fb[0].shape) if fb else None,
            "upscaled": list(fc[0].shape) if fc else None}, "arms": res}, indent=1), encoding="utf-8")
    print("wrote", a.out / "transfer_probe.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
