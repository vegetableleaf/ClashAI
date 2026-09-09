"""L67j: WHY does the card-tray reader fail on ~9% of live frames? Audit it on the bot's own footage.

MEASURED live (owner's 23:33 run): 19 of 205 decisions carried a hand with at least one unreadable slot
(`badhand 19/205`). Every such frame hands the model a slot encoded as "card not in my deck" -- bit 8 of the
hand one-hot, a bit set in 0.0009% of the 339,192 training rows -- and, worse, costs the affordability mask a
real option. It is the largest unfixed perception defect left.

This audits `Vision.recognize_hand` frame by frame on an overlay clip (the recorder draws detector boxes over
the ARENA; the card tray sits below it, so the tray pixels are the ones the bot actually read). Reported:

  * failure RATE per slot -- a geometry problem hits one slot, an art problem hits one card anywhere
  * the SCORE of failures against `match_threshold` -- a near-miss cluster means the threshold or the
    template set is wrong, a floor of very low scores means the crop is not the card
  * which identity the reader was closest to when it failed, so a stale template names itself
  * TEMPORAL consistency: a hand slot only changes when that card is played, so a slot that flips to -1 and
    back within a second is provably a read failure and not a real change

usage: python scratchpad/gauntlet/L67/tray_audit.py <clip.mp4> [--every 15] [--limit 400]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--every", type=int, default=15)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import cv2
    from clashrl.config import Config
    from clashrl.vision import Vision

    cfg = Config.load()
    vision = Vision(cfg)
    thr = float(cfg.get("cards", "match_threshold", default=0.5))
    keys = list(vision.deck_keys)
    print(f"threshold {thr}  deck identities {len(keys)}", flush=True)

    cap = cv2.VideoCapture(str(a.clip))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {a.clip}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)

    fail_by_slot = collections.Counter()
    near_by_slot = collections.Counter()
    fail_scores = []
    fail_closest = collections.Counter()
    seen_by_slot = collections.Counter()
    seq = [[] for _ in range(4)]
    fi = used = 0
    while used < a.limit:
        ok, fr = cap.read()
        if not ok:
            break
        fi += 1
        if fi % a.every:
            continue
        used += 1
        ids = list(vision.recognize_hand(fr))
        for si in range(4):
            cx, cy = vision.hand_slots[si]
            crop = vision.hand_crop(fr, cx, cy)
            idx, score = vision.match_card(crop) if crop.size else (-1, -1.0)
            seen_by_slot[si] += 1
            seq[si].append(int(ids[si]) if si < len(ids) else -1)
            if si < len(ids) and int(ids[si]) < 0:
                fail_by_slot[si] += 1
                fail_scores.append(float(score))
                if score >= thr - 0.15:
                    near_by_slot[si] += 1
                # what was it closest to? match_card returns -1 when under threshold, so re-rank by score
                fail_closest[keys[idx] if 0 <= idx < len(keys) else "(no candidate)"] += 1
    cap.release()

    # temporal: a slot flipping -1 and back is provably a read failure
    flips = 0
    for si in range(4):
        v = seq[si]
        for i in range(1, len(v) - 1):
            if v[i] < 0 <= v[i - 1] and v[i + 1] == v[i - 1]:
                flips += 1

    fs = np.array(fail_scores) if fail_scores else np.array([0.0])
    out = {"clip": a.clip.name, "frames": used, "threshold": thr,
           "fail_rate_overall": round(sum(fail_by_slot.values()) / max(4 * used, 1), 4),
           "fail_by_slot": {str(k): round(fail_by_slot[k] / max(seen_by_slot[k], 1), 4) for k in range(4)},
           "fail_scores": {"median": round(float(np.median(fs)), 3), "p90": round(float(np.percentile(fs, 90)), 3),
                           "frac_within_0.15_of_threshold": round(float((fs >= thr - 0.15).mean()), 3)},
           "closest_identity_when_failing": fail_closest.most_common(6),
           "isolated_flips_to_minus1": flips}
    print(json.dumps(out, indent=1), flush=True)
    if a.out:
        a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
