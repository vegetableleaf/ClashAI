"""Turn recorded sessions into an (observation, action) dataset for behaviour cloning.

Pairs your logged mouse clicks into card plays -- a hand-slot select followed by
an arena placement (tap-tap or press-drag-release) -- and grabs the frame at the
moment of selection as the observation. This v1 focuses on the (observation,
action) core; match segmentation and win/loss labeling come next.

Action per play: (slot 0-3, placement grid cell) plus the raw normalized (nx, ny).
Observation: the game frame at selection time, downscaled to observation.arena_size.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path

import cv2
import numpy as np

from .vision import Vision


def _latest_session(root: Path):
    found = [p for p in root.glob("*") if (p / "meta.json").exists()]
    return max(found, key=lambda p: p.name) if found else None


def _load(session: Path):
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    events = [json.loads(ln) for ln in
              (session / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    return meta, events, video


def _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot):
    """Walk the click stream and emit {t, slot, nx, ny} for each detected card play."""
    left, top, w, h = region

    def norm(x, y):
        return (x - left) / w, (y - top) / h

    def which_slot(nx, ny):
        if ny < a_bot:                       # above the tray -> not a slot select
            return None
        for i, (sx, _sy) in enumerate(slots):
            if abs(nx - sx) <= click_r:
                return i
        return None

    def on_arena(nx, ny):
        return a_top <= ny < a_bot

    plays = []
    sel_slot = None
    sel_t = None
    for e in events:
        if e.get("type") != "click":
            continue
        nx, ny = norm(e["x"], e["y"])
        if sel_slot is not None and sel_t is not None and e["t"] - sel_t > pair_timeout:
            sel_slot = None                  # timed out waiting for a placement
        slot = which_slot(nx, ny)
        if e["pressed"]:
            if slot is not None:
                sel_slot, sel_t = slot, e["t"]
            elif sel_slot is not None and on_arena(nx, ny):   # tap-tap placement
                plays.append({"t": sel_t, "slot": sel_slot, "nx": nx, "ny": ny})
                sel_slot = None
        else:                                # release: handles press-drag-release
            if sel_slot is not None and on_arena(nx, ny):
                plays.append({"t": sel_t, "slot": sel_slot, "nx": nx, "ny": ny})
                sel_slot = None
    return plays


def label_session(cfg, session: Path, debug: bool = False) -> int:
    meta, events, video = _load(session)
    if video is None:
        print(f"[label] no video in {session}")
        return 0
    region = meta["region"]
    frame_times = meta["frame_times"]
    left, top, w, h = region

    slots = cfg.get("hand", "slots", default=[])
    click_r = float(cfg.get("hand", "click_radius", default=0.06))
    pair_timeout = float(cfg.get("label", "pair_timeout", default=3.0))
    a_top = float(cfg.get("label", "arena_top", default=0.10))
    a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
    ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
    gw, gh = cfg.get("action", "grid", default=[8, 12])

    plays = _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot)

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vision = Vision(cfg)
    obs, acts, hands, nexts = [], [], [], []
    skipped = 0
    dbg_dir = session / "labeled"
    if debug:
        dbg_dir.mkdir(exist_ok=True)

    for k, p in enumerate(plays):
        fi = bisect.bisect_left(frame_times, p["t"])
        fi = max(0, min(fi, max(total - 1, 0)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        # identity of the played card: recognize the hand, take the selected slot
        hand_ids = vision.recognize_hand(frame)
        card = hand_ids[p["slot"]] if 0 <= p["slot"] < len(hand_ids) else -1
        if card < 0:                         # can't identify the card -> can't label by identity
            skipped += 1
            continue
        obs.append(cv2.resize(frame, (int(ow), int(oh)), interpolation=cv2.INTER_AREA))
        gx = min(int(gw) - 1, max(0, int(p["nx"] * gw)))
        gy = min(int(gh) - 1, max(0, int(p["ny"] * gh)))
        acts.append([card, gx, gy, p["slot"]])
        hands.append(vision.hand_multihot(hand_ids))
        nexts.append(vision.next_onehot(vision.recognize_next(frame)))
        if debug:
            f = frame.copy()
            sx, sy = slots[p["slot"]]
            name = vision.deck_keys[card] if card < len(vision.deck_keys) else f"card{card}"
            cv2.circle(f, (int(sx * w), int(sy * h)), 42, (255, 0, 0), 3)          # selected card
            cv2.drawMarker(f, (int(p["nx"] * w), int(p["ny"] * h)),
                           (0, 0, 255), cv2.MARKER_TILTED_CROSS, 32, 3)            # placement
            cv2.putText(f, f"play {k}: {name} -> cell ({gx},{gy})", (8, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imwrite(str(dbg_dir / f"play_{k:03d}.png"), f)
    cap.release()

    if obs:
        np.savez_compressed(
            session / "dataset.npz",
            obs=np.asarray(obs, dtype=np.uint8),
            acts=np.asarray(acts, dtype=np.float32),
            hands=np.asarray(hands, dtype=np.float32),
            nexts=np.asarray(nexts, dtype=np.float32),
            grid=np.asarray([int(gw), int(gh)], dtype=np.int64),
            deck=np.asarray(vision.deck_keys),
        )
    extra = f"  ({skipped} plays skipped: card not recognized)" if skipped else ""
    print(f"[label] {session.name}: {len(plays)} plays -> {len(obs)} samples{extra}"
          + (f"  (debug frames in {dbg_dir.name}/)" if debug else ""))
    return len(obs)


def label(cfg, session_arg=None, do_all=False, debug=False) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if do_all:
        sessions = sorted(p for p in root.glob("*") if (p / "meta.json").exists())
    else:
        one = Path(session_arg) if session_arg else _latest_session(root)
        sessions = [one] if one else []
    if not sessions:
        print(f"[label] no sessions under {root}")
        return
    total = sum(label_session(cfg, Path(s), debug=debug) for s in sessions)
    print(f"[label] done: {total} samples across {len(sessions)} session(s)")
