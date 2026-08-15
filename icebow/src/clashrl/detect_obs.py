"""Stage 3: board object-detector -> semantic OBSERVATION channels.

The policy today sees only the raw arena image (+ hand/elixir/threat vectors), so it must INFER
"what unit is where" from pixels. This module turns the trained detector's per-unit read into a
small stack of SEMANTIC MAP channels -- enemy/ally x ground/air/building, plus spells -- at the
arena resolution: a clean, rendering-independent "what's on the board" signal to feed PolicyNet
alongside the image (the core of Stage 3). PRELIMINARY: the channels are only as good as the
detector's mAP, so wiring them into training (observation.use_detector) should wait until the
detector is strong; `detect-obs` lets you SEE the read now.

Reuses the detector wrapper in replay_mine (load_detector / BoardDetector / Detection).
"""
from __future__ import annotations

import random
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List

import cv2
import numpy as np

from . import card_threat
from .replay_mine import Detection, load_detector

# Semantic channels fed to the policy -- the ORDER is the channel index.
CHANNELS = ("enemy_ground", "enemy_air", "enemy_building", "my_ground", "my_building", "spell")
N_CHANNELS = len(CHANNELS)
# PREDICTIVE CANVAS (2026-08-15, the obs architecture break): three extra channels per slice
# derived from the game's DETERMINISTIC mechanics (interactions.mover_forecast) rather than
# learned from pixels -- enemy units at their dead-reckoned t+dt positions, ours likewise,
# and an enemy URGENCY map (intensity = how soon each unit reaches its predicted target).
# A human reads exactly this at a glance; painting it saves the conv trunk from having to
# rediscover per-card speeds and targeting from experience.
PRED_CHANNELS = ("enemy_predicted", "my_predicted", "enemy_urgency")
N_PRED = len(PRED_CHANNELS)


def canvas_enabled(cfg) -> bool:
    """Is the detector-rendered semantic CANVAS part of the observation image?

    This is the `observation.use_detector_canvas` gate: the obs-canvas flip that `detect-eval`
    measures with its class-agnostic PRESENCE recall (the canvas only needs position + team, not
    the card's name -- that is what the separate identity block is for).
    """
    return bool(cfg.get("observation", "use_detector_canvas", default=False))


def predictive_enabled(cfg) -> bool:
    """Is the mechanics-derived PREDICTIVE canvas (see PRED_CHANNELS) part of the image?
    Requires the semantic canvas itself -- prediction extends it, never replaces it."""
    return canvas_enabled(cfg) and bool(cfg.get("observation", "use_predictive_canvas",
                                                default=False))


def predictive_dt(cfg) -> float:
    return max(1e-3, float(cfg.get("observation", "predictive_canvas_dt_s", default=1.0)))


def eta_horizon(cfg) -> float:
    return max(0.5, float(cfg.get("observation", "eta_horizon_s", default=8.0)))


def canvas_stack_len(cfg) -> int:
    """How many semantic-canvas SNAPSHOTS the image branch carries. 1 = a single canvas (today).

    A single canvas is a SNAPSHOT: it says where every unit is, never where it is GOING. Stacking
    the last N canvases at a fixed spacing lets the conv trunk read MOTION straight off the channel
    deltas -- the cheap alternative to an explicit per-unit velocity channel, which would depend on
    cross-frame box association (a much harder ask than the class-agnostic PRESENCE recall the
    canvas is gated on: a unit missed on one frame is simply absent from that slice).
    """
    if not canvas_enabled(cfg):
        return 1
    return max(1, int(cfg.get("observation", "canvas_stack", default=1)))


def canvas_stack_dt(cfg) -> float:
    """Seconds BETWEEN stacked canvas snapshots.

    Sampled on a FIXED clock rather than 'the last N observations' because neither producer ticks
    evenly: live perception is a ceiling (`observation.perception_hz`, ~5-10 Hz depending on what
    else holds the GPU) and the act loop wakes early on a new-enemy event, so consecutive decisions
    can be 0.3-1.0 s apart. Sampling by TIME keeps the implied motion scale constant, so a stack
    means the same thing in the sim, live, and a mined replay.
    """
    return max(1e-3, float(cfg.get("observation", "canvas_stack_dt_s", default=0.5)))


def obs_in_channels(cfg) -> int:
    """Channel count of the policy's IMAGE branch: 3 (RGB arena) + the semantic canvas when on.

    Every PolicyNet construction site reads this so sim, live play and all three trainers agree;
    the value is also stamped into each checkpoint as `in_ch` so `play` rebuilds the right net.
    """
    per_slice = N_CHANNELS + (N_PRED if predictive_enabled(cfg) else 0)
    return 3 + (per_slice * canvas_stack_len(cfg) if canvas_enabled(cfg) else 0)


class CanvasStack:
    """Fixed-dt history of semantic canvases -> the MOTION half of the observation image.

    ``push`` the newest canvas with its timestamp each time an observation is built; ``stacked``
    returns ``[oh, ow, N_CHANNELS * n]`` ordered NEWEST FIRST, so channels 0..5 stay exactly the
    canvas a 1-deep stack would have produced and the older slices are appended behind it.

    Slices are picked by NEAREST TIMESTAMP to ``t - k*dt`` rather than by position, which is what
    makes an uneven producer safe. Before enough history exists every slot resolves to the newest
    canvas, so a match opens with ZERO apparent motion instead of a phantom velocity.

    Dtype-agnostic: the sim renders uint8 channels and the live path converts through
    ``channels_to_uint8``, so the stack simply concatenates whatever it was given.
    """

    def __init__(self, n: int, dt: float, maxlen: int = 64):
        self.n = max(1, int(n))
        self.dt = max(1e-3, float(dt))
        self._buf: deque = deque(maxlen=max(2, int(maxlen)))

    def reset(self) -> None:
        """Drop all history -- call at MATCH START so motion never bridges two matches."""
        self._buf.clear()

    def push(self, canvas: np.ndarray, t: float) -> np.ndarray:
        """Record ``canvas`` at time ``t`` and return the stacked view ending at it."""
        self._buf.append((float(t), canvas))
        return self.stacked(t)

    def stacked(self, t: float | None = None) -> np.ndarray:
        """The stacked canvas ending at ``t`` (default: the newest pushed timestamp)."""
        if not self._buf:
            raise ValueError("CanvasStack.stacked() before any push()")
        newest_t, newest = self._buf[-1]
        if self.n == 1:
            return newest                      # identical to the un-stacked canvas (no copy, no cost)
        t = newest_t if t is None else float(t)
        slices = [newest]
        for k in range(1, self.n):
            slices.append(self._nearest(t - k * self.dt))
        return np.concatenate(slices, axis=2)

    def _nearest(self, target: float) -> np.ndarray:
        best, best_d = self._buf[-1][1], None
        for et, ec in self._buf:
            d = abs(et - target)
            if best_d is None or d < best_d:
                best, best_d = ec, d
        return best


def channels_to_uint8(channels: np.ndarray) -> np.ndarray:
    """Semantic channels ([0,1] float) -> uint8 0..255.

    The observation is ONE uint8 stack that every consumer divides by 255, so the canvas is stored
    on the same scale as the image rather than as a second float array -- that keeps the replay
    buffers, the .npz datasets and `to_obs_t` untouched.
    """
    return np.clip(channels * 255.0, 0.0, 255.0).astype(np.uint8)

# channel -> BGR colour, for the human-readable preview only
_VIZ = {0: (40, 40, 255), 1: (0, 165, 255), 2: (0, 0, 130),
        3: (255, 140, 40), 4: (150, 70, 0), 5: (0, 255, 255)}


def _channel_of(d: Detection, db) -> int:
    """Map a detection to a semantic channel by TEAM + coarse ROLE (from the card KB)."""
    p = card_threat.profile(db, d.base)
    mine = d.team == "mine"
    if p.spell or d.cls.endswith("_aoe"):
        return 5                                     # spell / AOE (team-agnostic)
    if p.kind == "building" or p.siege:
        return 4 if mine else 2                      # building / siege
    if mine:
        return 3                                     # my troop (air or ground)
    return 1 if p.flying else 0                      # enemy air vs ground


def detection_channels(dets: List[Detection], db, oh: int, ow: int, warp=None) -> np.ndarray:
    """Render detections into an [oh, ow, N_CHANNELS] float32 map: each unit a filled ellipse of its
    confidence in its channel; overlaps take the max."""
    ch = np.zeros((oh, ow, N_CHANNELS), np.float32)
    for d in dets:
        k = _channel_of(d, db)
        if warp is not None:                       # live: frame coords -> BOARD coords, so the
            bx, by = warp.frame_to_board(d.cx, d.gy)   # canvas matches the sim's board-true one
        else:
            bx, by = d.cx, d.gy
        cx, cy = int(bx * ow), int(by * oh)   # flyers rasterized at their SHADOW (true ground tile)
        rx, ry = max(1, int(d.w * ow / 2)), max(1, int(d.h * oh / 2))
        layer = np.zeros((oh, ow), np.float32)
        cv2.ellipse(layer, (cx, cy), (rx, ry), 0, 0, 360, float(min(1.0, d.conf)), -1)
        ch[:, :, k] = np.maximum(ch[:, :, k], layer)
    return ch


def predictive_channels(units, my_towers, enemy_towers, db, oh: int, ow: int,
                        confs=None, dt_s: float = 1.0, horizon_s: float = 8.0) -> np.ndarray:
    """Render interactions.mover_forecast into [oh, ow, N_PRED] float32: channel 0 = enemy
    units at their PREDICTED t+dt positions, 1 = ours likewise, 2 = enemy URGENCY painted at
    the CURRENT position (brightness = closeness-in-time to its target). ``units`` are
    interactions.Unit tuples ALREADY in this canvas's coordinate space (board-true for
    sim/live, frame for BC replays), with towers in the same space."""
    from . import interactions
    ch = np.zeros((oh, ow, N_PRED), np.float32)
    if not units:
        return ch
    fc = interactions.mover_forecast(units, my_towers, enemy_towers, db,
                                     dt_s=dt_s, horizon_s=horizon_s)
    rx, ry = max(1, int(ow / 18.0 * 0.55)), max(1, int(oh / 32.0 * 0.7))
    for i, ((team, base, x, y), (px, py, urg)) in enumerate(zip(units, fc)):
        conf = float(confs[i]) if confs is not None else 1.0
        k = 1 if team == "mine" else 0
        layer = np.zeros((oh, ow), np.float32)
        cv2.ellipse(layer, (int(px * ow), int(py * oh)), (rx, ry), 0, 0, 360,
                    float(min(1.0, conf)), -1)
        ch[:, :, k] = np.maximum(ch[:, :, k], layer)
        if team != "mine" and urg > 0.0:
            layer = np.zeros((oh, ow), np.float32)
            cv2.ellipse(layer, (int(x * ow), int(y * oh)), (rx, ry), 0, 0, 360,
                        float(min(1.0, urg * conf)), -1)
            ch[:, :, 2] = np.maximum(ch[:, :, 2], layer)
    return ch


def board_channels(frame, detector, db, oh: int, ow: int, conf: float = 0.3) -> np.ndarray:
    """Run the detector on a frame -> semantic channels (zeros if the detector is unavailable, so
    callers degrade gracefully to the image-only observation)."""
    if detector is None or not getattr(detector, "available", False):
        return np.zeros((oh, ow, N_CHANNELS), np.float32)
    return detection_channels(detector.detect(frame, conf=conf), db, oh, ow)


def channels_to_bgr(channels: np.ndarray) -> np.ndarray:
    channels = channels[:, :, :N_CHANNELS]          # preview draws the semantic 6 only
    """Composite the semantic channels into one BGR image for a human preview."""
    oh, ow = channels.shape[:2]
    out = np.zeros((oh, ow, 3), np.float32)
    for k, col in _VIZ.items():
        out = np.maximum(out, channels[:, :, k][:, :, None] * np.array(col, np.float32))
    return out.astype(np.uint8)


def detect_obs_preview(cfg, session_arg=None, count=12, weights=None, conf=0.3) -> None:
    """SHOW the Stage-3 read: run the trained detector on random in-match frames, render the semantic
    channels, and save `frame | channel-map` images to runs/detect/obs_preview/. This is the exact
    board representation Stage 3 would feed the policy (once observation.use_detector is turned on)."""
    from .cards import CardDB
    from .vision import Vision

    detector = load_detector(cfg, weights)
    if not detector.available:
        print("[detect-obs] no trained detector found -- train first:  python tools/detect/train.py")
        return
    db = CardDB(cfg)
    vision = Vision(cfg)
    ow, oh = cfg.get("observation", "arena_size", default=[64, 96])   # obs is [oh, ow, 3]

    root = Path(cfg.path(cfg.get("record", "out_dir", default="data/sessions")))
    if session_arg and Path(session_arg).exists():
        sessions = [Path(session_arg)]
    elif session_arg:
        sessions = [root / session_arg]
    else:
        sessions = sorted(d for d in root.iterdir() if (d / "meta.json").exists())
    videos = [next((s / n for n in ("video.mp4", "video.avi") if (s / n).exists()), None) for s in sessions]
    videos = [v for v in videos if v is not None]
    if not videos:
        print("[detect-obs] no session videos found")
        return

    out_dir = Path(cfg.path("runs/detect")) / "obs_preview" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random()
    saved = 0
    tries = 0
    while saved < count and tries < count * 20:
        tries += 1
        vid = rng.choice(videos)
        cap = cv2.VideoCapture(str(vid))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, rng.randrange(max(1, total)))
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None or vision.detect_state(frame).name != "IN_MATCH":
            continue
        dets = detector.detect(frame, conf=conf)
        ch = detection_channels(dets, db, int(oh), int(ow))
        viz = channels_to_bgr(ch)
        fh, fw = frame.shape[:2]
        viz_big = cv2.resize(viz, (int(fh * ow / oh), fh), interpolation=cv2.INTER_NEAREST)
        combo = np.hstack([frame, viz_big])
        cv2.putText(combo, f"{len(dets)} detections   (frame | Stage-3 semantic channels)", (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imwrite(str(out_dir / f"obs_{saved:02d}.png"), combo)
        saved += 1
    print(f"[detect-obs] saved {saved} preview(s) to {out_dir}")
    print("[detect-obs] channels: red=enemy-ground orange=enemy-air darkred=enemy-building "
          "blue=my-ground darkblue=my-building yellow=spell")
