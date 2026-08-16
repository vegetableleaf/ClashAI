"""Audit the detector against recorded sessions.  `python tools/detector_audit.py [--frames 400]`

THE MEASUREMENT THAT NEEDS NO LABELS
------------------------------------
Hand-labelling frames is slow, and we do not need to. One fact is free and absolute: a unit on
OUR side can only be a card from OUR deck. Every detection tagged "mine" whose card is not in the
deck is therefore WRONG -- no judgement call, no annotation. That single check turns any recorded
session into a labelled set for the team classifier.

It is a LOWER BOUND on the error rate, not the error rate: an enemy Knight mislabelled as ours is
counted (Knight is not in this deck), but an enemy Skeletons mislabelled as ours is not, because
Skeletons IS in the deck and the mistake is invisible to this test. So whatever this reports, the
true team error is worse.

Motivated by a live session (2026-08-16) whose advisor log read "YOUR units already out: goblin
cage" and "... earthquake" -- neither in the deck, the second almost certainly our own king tower.
The same detections feed the observation canvas and the threat features the network trains on, so
if this number is bad, nothing downstream can be right.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl.config import Config          # noqa: E402
from clashrl.cards import CardDB           # noqa: E402


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="session folder (default: newest)")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--stride", type=int, default=12)
    a = ap.parse_args(argv)

    import cv2
    cfg = Config.load()
    db = CardDB(cfg)
    deck = list(db.deck_identities())
    base = lambda k: k[:-4] if str(k).endswith("_evo") else str(k)   # noqa: E731
    own = set(deck) | {base(k) for k in deck}

    root = _ROOT / "data" / "sessions"
    sess = Path(a.session) if a.session else max(
        (p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    vid = sess / "video.mp4"
    if not vid.exists():
        print("no video in %s" % sess)
        return 2
    print("session %s\ndeck: %s\n" % (sess.name, ", ".join(deck)))

    from clashrl.env import LiveMatchEnv
    env = LiveMatchEnv(cfg)

    cap = cv2.VideoCapture(str(vid))
    seen = 0
    mine_ok = mine_bad = enemy_n = 0
    bad_cards = collections.Counter()
    mine_cards = collections.Counter()
    per_frame_bad = []
    i = 0
    while seen < a.frames:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if i % a.stride:
            continue
        try:
            env._detect_enemies(frame)      # fills _last_dets_all with TEAM-TAGGED detections
        except Exception as e:  # noqa: BLE001
            if seen == 0 and i < 40:
                print("detector call failed: %s: %s" % (type(e).__name__, e))
            continue
        dets = getattr(env, "_last_dets_all", None) or []
        if not dets:
            continue
        seen += 1
        nbad = 0
        for d in dets:
            if d.team == "mine":
                if str(d.base) in own:
                    mine_ok += 1
                    mine_cards[str(d.base)] += 1
                else:
                    mine_bad += 1
                    bad_cards[str(d.base)] += 1
                    nbad += 1
            elif d.team == "enemy":
                enemy_n += 1
        per_frame_bad.append(nbad)
    cap.release()

    tot_mine = mine_ok + mine_bad
    print("frames with detections: %d   (enemy-tagged %d, mine-tagged %d)" % (seen, enemy_n, tot_mine))
    if not tot_mine:
        print("no ally-tagged detections -- cannot audit the team classifier from this session")
        return 0
    print("\nALLY-TAGGED DETECTIONS THAT CANNOT BE OURS: %d / %d = %.1f%%"
          % (mine_bad, tot_mine, 100.0 * mine_bad / tot_mine))
    print("  (a LOWER bound: an enemy card that IS in our deck is miscounted as correct)")
    frames_with_bad = sum(1 for n in per_frame_bad if n)
    print("  frames containing at least one impossible ally: %d / %d = %.1f%%"
          % (frames_with_bad, seen, 100.0 * frames_with_bad / max(1, seen)))
    print("\nmost common IMPOSSIBLE ally cards:")
    for k, n in bad_cards.most_common(10):
        print("   %-22s %5d" % (k, n))
    print("\nally cards that are at least plausible:")
    for k, n in mine_cards.most_common(10):
        print("   %-22s %5d" % (k, n))
    out = _ROOT / "data" / "detector_audit.json"
    out.write_text(json.dumps({"session": sess.name, "frames": seen,
                               "mine_ok": mine_ok, "mine_bad": mine_bad,
                               "impossible": dict(bad_cards), "plausible": dict(mine_cards)},
                              indent=1), encoding="utf-8")
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
