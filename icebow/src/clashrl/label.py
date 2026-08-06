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

from .actions import ActionSpace
from . import card_threat
from . import interactions
from .cards import CardDB
from .threats import read_threat_window
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


def _enemy_dets(det, cfg, frame):
    """One detector pass -> whitelisted ENEMY detections. OFFLINE = single frames, so only the
    stateless colour evidence applies (HP-bar strip, else overwhelming body art); undamaged
    ambiguous units stay 'unknown' and are EXCLUDED -- sparser than live (which adds motion +
    own-play evidence via TeamTracker) but never poisoned by art-colour guesses.
    [] when the detector is unavailable -- the blocks then stay zero, same as live."""
    if det is None or frame is None:
        return []
    try:
        dets = det.detect(frame, conf=float(cfg.get("observation", "detector_conf", default=0.5)))
    except Exception:
        return []
    whitelist = set(cfg.get("observation", "detector_cards", default=[]))
    return [d for d in dets if d.team == "enemy" and d.base in whitelist]


def _interaction_block(det, db, cfg, frame):
    """OFFLINE troop-interaction block: predicted tower pressure from ALL whitelisted detections (both
    teams, colour team read). Towers are assumed ALIVE (no offline tower tracking) -- coarse but the
    same 12 dims the live env supplies. Zeros when the detector is unavailable."""
    if det is None or frame is None:
        return np.zeros(interactions.INTERACTION_DIM, np.float32)
    try:
        dets = det.detect(frame, conf=float(cfg.get("observation", "detector_conf", default=0.5)))
    except Exception:
        return np.zeros(interactions.INTERACTION_DIM, np.float32)
    whitelist = set(cfg.get("observation", "detector_cards", default=[]))
    units = [("mine" if d.team == "mine" else "enemy", d.base, d.cx, d.gy)
             for d in dets if d.team in ("mine", "enemy") and d.base in whitelist]
    mine_a = cfg.get("env", "my_towers", default=[[0.245, 0.615], [0.745, 0.615], [0.48, 0.72]])
    enemy_a = cfg.get("env", "enemy_towers", default=[[0.25, 0.205], [0.745, 0.205], [0.48, 0.11]])
    my_t = [(ax, ay, True) for ax, ay in mine_a[:3]]
    en_t = [(ax, ay, True) for ax, ay in enemy_a[:3]]
    sight = float(cfg.get("sim", "sight_range", default=0.12))
    return interactions.interaction_vector(units, my_t, en_t, db)


def _identity_blocks(det, db, cfg, opp_mem, prev_frame, frame, dt):
    """OFFLINE mirror of env._update_threat's detector path: run the detector on a frame ~dt earlier
    (for the approach-velocity feature) and on the play frame, feed the opponent memory in time order,
    and return (identity block, memory block) exactly as the live policy would have seen them."""
    horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
    prev_depth = 0.0
    d_prev = _enemy_dets(det, cfg, prev_frame)
    if d_prev:
        v_prev = card_threat.identity_threat_vector(
            [(d.base, (d.gy - 0.5) / 0.5) for d in d_prev if d.gy >= 0.5], db)
        prev_depth = float(v_prev[7])
        opp_mem.update([(d.base, d.gy) for d in d_prev], dt=dt)
    d_now = _enemy_dets(det, cfg, frame)
    ident = card_threat.identity_threat_vector(
        [(d.base, (d.gy - 0.5) / 0.5) for d in d_now if d.gy >= 0.5], db,
        prev_depth=prev_depth, dt=max(1e-3, dt), horizon=horizon)
    mem = opp_mem.update([(d.base, d.gy) for d in d_now], dt=dt)
    return ident, mem


def label_session(cfg, session: Path, debug: bool = False, det=None, db=None, wide: bool = False) -> int:
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
    gw, gh = cfg.get("action", "grid", default=[18, 32])
    aspace = ActionSpace(cfg)                          # box-anchored tile grid (same mapping the policy uses)

    plays = _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot)

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vision = Vision(cfg)
    obs, acts, hands, nexts, elixirs, threats = [], [], [], [], [], []
    skipped = 0
    # Stage-3 WIDE threats: identity + opponent-memory blocks from the detector, run OFFLINE over the
    # recording at ~the live act cadence (a frame ~ident_dt before each play gives the velocity read).
    opp_mem = card_threat.OpponentMemory(db) if wide else None
    ident_dt = float(cfg.get("play", "act_period", default=1.5))
    prev_play_t = None
    dbg_dir = session / "labeled"
    if debug:
        dbg_dir.mkdir(exist_ok=True)

    for k, p in enumerate(plays):
        fi = bisect.bisect_left(frame_times, p["t"])
        fi = max(0, min(fi, max(total - 1, 0)))
        prev_frame = None
        if wide:
            if prev_play_t is None or (p["t"] - prev_play_t) > 30.0:
                opp_mem.reset()                          # long gap = a new match / fresh opponent read
            prev_play_t = p["t"]
            fj = bisect.bisect_left(frame_times, p["t"] - ident_dt)
            fj = max(0, min(fj, max(total - 1, 0)))
            if fj < fi:
                cap.set(cv2.CAP_PROP_POS_FRAMES, fj)
                ok, pf = cap.read()
                prev_frame = pf if ok else None
        # read the enemy threat over the short window ending at the play (motion + projectile),
        # so the dataset carries the same threat vector the live env feeds the policy.
        thr, frame = read_threat_window(cap, fi, frame_times, cfg)
        if frame is None:
            continue
        # identity of the played card: recognize the hand, take the selected slot
        hand_ids = vision.recognize_hand(frame)
        card = hand_ids[p["slot"]] if 0 <= p["slot"] < len(hand_ids) else -1
        if card < 0:                         # can't identify the card -> can't label by identity
            skipped += 1
            continue
        obs.append(cv2.resize(frame, (int(ow), int(oh)), interpolation=cv2.INTER_AREA))
        gx, gy = aspace.coords_to_grid(p["nx"], p["ny"])
        acts.append([card, gx, gy, p["slot"]])
        hands.append(vision.hand_multihot(hand_ids))
        nexts.append(vision.next_onehot(vision.recognize_next(frame)))
        elixirs.append([vision.read_elixir(frame) / 10.0])
        if wide:
            ident, mem = _identity_blocks(det, db, cfg, opp_mem, prev_frame, frame, ident_dt)
            parts = [thr.vector(), ident, mem]
            if bool(cfg.get("observation", "use_interactions", default=False)):
                parts.append(_interaction_block(det, db, cfg, frame))
            threats.append(np.concatenate(parts).astype(np.float32))
        else:
            threats.append(thr.vector())
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
            elixirs=np.asarray(elixirs, dtype=np.float32),
            threats=np.asarray(threats, dtype=np.float32),
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
    # Stage 3: when the detector obs is ON, the dataset carries the WIDE threat vector (base 16 +
    # identity 10 + memory 8 = 34) built by running the trained detector OFFLINE over the recordings --
    # the same signal the live policy sees, so train-bc no longer narrows a 34-dim policy to 16.
    wide = bool(cfg.get("observation", "use_detector", default=False))
    det = db = None
    if wide:
        db = CardDB(cfg)
        try:
            from .replay_mine import load_detector
            d = load_detector(cfg)
            det = d if getattr(d, "available", False) else None
        except Exception:
            det = None
        print(f"[label] wide threats (base+identity+memory): detector "
              + ("loaded" if det is not None else "UNAVAILABLE -> identity/memory blocks stay zero"))
    total = sum(label_session(cfg, Path(s), debug=debug, det=det, db=db, wide=wide) for s in sessions)
    print(f"[label] done: {total} samples across {len(sessions)} session(s)")
