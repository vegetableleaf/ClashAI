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

WHY THIS DOES NOT GO THROUGH LiveMatchEnv (it used to, and measured NOTHING)
---------------------------------------------------------------------------
The first version of this tool called ``env._detect_enemies(frame)`` to reuse the live path, and
every number it produced was fiction. Two reasons, both silent:

  * ``LiveMatchEnv.__init__`` STARTS the 10 Hz perception thread, and ``_detect_enemies`` returns
    that thread's snapshot whenever it is under 2 s old -- so the frame argument was discarded and
    the audit measured the detector looking at the LIVE SCREEN. It reported classes like `ronin`
    and `royal_recruits` that appear nowhere in these sessions, and the same detection repeated
    across frames with identical coordinates and confidence, which is what gave it away.
  * team evidence is TIME-based (motion windows, track forgetting, own-play anchors) and the live
    path stamps it with ``time.time()``. Stepping a video at stride N advances video time far
    faster than wall time, so tracks that should have expired never do.

So this builds the detector and the tracker DIRECTLY, mirroring the synchronous branch of
``_detect_enemies`` with the same config values, and stamps every read with VIDEO time.
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


def _sessions(root: Path, only: str | None):
    if only:
        p = Path(only)
        return [p if p.is_absolute() or p.exists() else root / only]
    return sorted((p for p in root.iterdir() if p.is_dir() and (p / "video.mp4").exists()),
                  key=lambda p: p.name)


def _new_tally():
    return {"seen": 0, "mine_ok": 0, "mine_bad": 0, "enemy": 0, "unknown": 0, "dropped": 0,
            "bad_cards": collections.Counter(), "mine_cards": collections.Counter(),
            "unknown_cards": collections.Counter(), "frames_with_bad": 0,
            "spell_mine": 0, "spell_all": 0}


def _tally_into(t, dets, db, own, verbose_frame=None):
    if not dets:
        return
    t["seen"] += 1
    nbad = 0
    for d in dets:
        base = str(d.base)
        spell = _is_spell(db, base)
        t["spell_all"] += spell
        if d.team == "mine":
            t["spell_mine"] += spell
            if base in own:
                t["mine_ok"] += 1
                t["mine_cards"][base] += 1
            else:
                t["mine_bad"] += 1
                t["bad_cards"][base] += 1
                nbad += 1
        elif d.team == "enemy":
            t["enemy"] += 1
        else:
            t["unknown"] += 1
            t["unknown_cards"][base] += 1
    if nbad:
        t["frames_with_bad"] += 1
        if verbose_frame is not None and t["frames_with_bad"] <= 6:
            print("   frame %6d  %s" % (verbose_frame, ", ".join(
                "%s@y%.2f" % (d.base, d.gy) for d in dets
                if d.team == "mine" and str(d.base) not in own)))


def _audit_one(sess: Path, cfg, db, own, frames: int, stride: int, verbose: bool):
    """Read the VIDEO through the detector, and score TWO pipelines on the identical detections.

    One detector pass feeds both arms, so the before/after is a controlled A/B rather than two
    runs over two different frame slices:

      BEFORE -- the pipeline as it was: every box the detector emits, team by evidence fusion alone.
      AFTER  -- the playfield gate (a box outside ``env.arena_region`` is not a unit) plus the deck
                veto in TeamTracker ('mine' must name a card we own).

    The AFTER arm's impossible-ally count is ZERO BY CONSTRUCTION -- the veto is defined to make it
    so, and a metric cannot validate the rule that defines it. What the comparison does show is how
    much work the rule is doing, and the BEFORE arm remains the honest measure of the underlying
    classifier. The residual (an enemy Knight or Skeletons read as ours) is invisible to both.
    """
    import copy
    import cv2
    from clashrl.replay_mine import load_detector, TeamTracker, own_card_bases
    from clashrl.env import _DetHold

    det = load_detector(cfg)
    if not det.available:
        print("no detector weights -- nothing to audit")
        return None
    box = det._arena_box                    # applied here, so ONE detector pass can feed both arms
    det._arena_box = None
    conf = float(cfg.get("observation", "detector_conf", default=0.75))

    def _tracker(own_cards):
        return TeamTracker(
            own_cards=own_cards,
            spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
            spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
            enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
            track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)),
            forget_s=float(cfg.get("observation", "team_forget_s", default=4.5)),
            motion_min=float(cfg.get("observation", "team_motion_min", default=0.05)),
            deep_mine_y=float(cfg.get("observation", "team_deep_mine_y", default=0.62)),
            deep_enemy_y=float(cfg.get("observation", "team_deep_enemy_y", default=0.38)))

    hold_s = float(cfg.get("observation", "det_hold_s", default=0.45))
    arms = {"BEFORE": [_tracker(None), _DetHold(hold_s), _new_tally()],
            "AFTER":  [_tracker(own_card_bases(db)), _DetHold(hold_s), _new_tally()]}

    cap = cv2.VideoCapture(str(sess / "video.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    i = 0
    while arms["BEFORE"][2]["seen"] < frames:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if i % stride:
            continue
        t = i / fps                                   # VIDEO time, not wall clock
        try:
            raw = det.detect(frame, conf=conf)
        except Exception as e:                        # noqa: BLE001
            if not arms["BEFORE"][2]["seen"]:
                print("detector call failed: %s: %s" % (type(e).__name__, e))
                return None
            continue
        for name, (tracker, hold, tally) in arms.items():
            dets = [copy.copy(d) for d in raw]        # tag() mutates .team -- the arms must not share
            if name == "AFTER" and box is not None:
                keep = [d for d in dets
                        if box[0] <= d.cx <= box[2] and box[1] <= d.gy <= box[3]]
                tally["dropped"] += len(dets) - len(keep)
                dets = keep
            tracker.tag(dets, t)                      # towers assumed alive: no pocket gating offline
            _tally_into(tally, hold.merge(dets, t), db, own, i if verbose and name == "BEFORE" else None)
    cap.release()
    return {k: v[2] for k, v in arms.items()}


def _is_spell(db, base: str) -> bool:
    c = db.get(base)
    return bool(c) and str(c.get("type", "")).lower() == "spell"


def _arm_line(label: str, t: dict) -> None:
    tot_mine = t["mine_ok"] + t["mine_bad"]
    total = tot_mine + t["enemy"] + t["unknown"]
    print("  %-7s %5d detections (mine %4d, enemy %4d, unknown %3d)   impossible allies %4d = %.1f%%"
          % (label, total, tot_mine, t["enemy"], t["unknown"], t["mine_bad"],
             100.0 * t["mine_bad"] / max(1, tot_mine)))


def _report(name: str, arms: dict) -> None:
    before, after = arms["BEFORE"], arms["AFTER"]
    print("\n== %s ==   %d frames with detections" % (name, before["seen"]))
    _arm_line("BEFORE", before)
    _arm_line("AFTER", after)
    if after["dropped"]:
        print("           playfield gate dropped %d boxes off the arena (card tray / HUD)"
              % after["dropped"])
    if not before["mine_bad"]:
        return
    print("  frames with >=1 impossible ally, BEFORE: %d / %d = %.1f%%"
          % (before["frames_with_bad"], before["seen"],
             100.0 * before["frames_with_bad"] / max(1, before["seen"])))
    for title, key, t in (("most common IMPOSSIBLE ally cards (BEFORE)", "bad_cards", before),
                          ("ally cards that are at least plausible (AFTER)", "mine_cards", after),
                          ("UNKNOWN-team cards (canvas SKIPS these since 553fe5c; before that they were painted as ENEMY) (AFTER)",
                           "unknown_cards", after)):
        if not t[key]:
            continue
        print("  %s:" % title)
        for k, n in t[key].most_common(8):
            print("     %-22s %5d" % (k, n))


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="session folder (default: ALL sessions)")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--stride", type=int, default=12)
    ap.add_argument("--verbose", action="store_true", help="print offending frames")
    a = ap.parse_args(argv)

    cfg = Config.load()
    db = CardDB(cfg)
    deck = list(db.deck_identities())
    base = lambda k: k[:-4] if str(k).endswith("_evo") else str(k)   # noqa: E731
    own = set(deck) | {base(k) for k in deck}
    print("deck: %s\n" % ", ".join(deck))

    root = _ROOT / "data" / "sessions"
    sessions = _sessions(root, a.session)
    if not sessions:
        print("no sessions with a video under %s" % root)
        return 2

    out = {}
    total = {"BEFORE": _new_tally(), "AFTER": _new_tally()}
    for sess in sessions:
        arms = _audit_one(sess, cfg, db, own, a.frames, a.stride, a.verbose)
        if arms is None:
            continue
        _report(sess.name, arms)
        for name, t in arms.items():
            for k, v in t.items():
                total[name][k] += v          # Counters merge with +=, ints add
        out[sess.name] = {name: {k: (dict(v) if isinstance(v, collections.Counter) else v)
                                 for k, v in t.items()} for name, t in arms.items()}

    if len(out) > 1:
        _report("ALL SESSIONS", total)
    dst = _ROOT / "data" / "detector_audit.json"
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote %s" % dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
