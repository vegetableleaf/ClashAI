"""Replay -> BC dataset: distil PRO footage into a `train-bc`-loadable `dataset.npz`.

This is the Stage-4 sub-task queued in log.txt (2026-07-29 design note) and unlocked by the
obs-canvas flip. It answers "how does a strong player play WHAT, WHEN and WHERE" and hands that
to behaviour cloning as a WARM START, before the policy ever enters the simulator.

RENDERING-INDEPENDENT BY CONSTRUCTION -- the crux of that design note
--------------------------------------------------------------------
Public footage is a DIFFERENT RENDERING than our capture (phone skin, resolution, overlays), and
image-BC clones pixels->action, so feeding the pro's pixels into the image branch transfers badly.
So we never do. The detector recovers WHAT/WHERE as STRUCTURE, and the observation is rebuilt by
OUR OWN renderer:

  * channels 0-2 (RGB) -- a CANONICAL synthetic top-down re-render (option (i) of the note), drawn
    with the same palette/lay-out as `sim/view.render_obs`, which is the distribution the PPO
    policy actually trains on. The pro's pixels are used ONLY to detect units; none of them reach
    the tensor.
  * channels 3-8 -- the SEMANTIC CANVAS (option (ii)), `detect_obs.detection_channels`, byte-for-
    byte the same builder the live env uses. Rendering-independent by definition.

Two honest caveats, both handled rather than hidden:
  * TEAM COLOUR IS UNRELIABLE on foreign footage (measured on the Hunter replays: most of the
    learn-side player's own units came back tagged `enemy`, many `unknown`). Team is therefore
    taken from the ARENA HALF a unit was FIRST SEEN in and then CARRIED by a tracker as it walks
    across the river -- geometry, not palette.
  * DETECTOR RECALL is lower on a foreign rendering, so expect FEW and NOISY samples. That is
    exactly why BC here is a light warm start and the simulator remains the teacher: see
    `train_bc`'s val split + early stopping, which exist so this small set cannot be memorised.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


def _bc_towers(cfg):
    """Static config tower anchors as interactions.Tower tuples (alive=True): the replay
    labeler does not track tower falls, so the forecast assumes standing towers."""
    mt = [(float(a[0]), float(a[1]), True) for a in (cfg.get("env", "my_towers") or [])[:3]]
    et = [(float(a[0]), float(a[1]), True) for a in (cfg.get("env", "enemy_towers") or [])[:3]]
    return mt, et, None

from . import card_threat
from . import detect_obs
from .actions import ActionSpace
from .cards import CardDB
from .replay_mine import Detection, load_detector, _VIDEO_EXTS
from .reward import _anchors
from .threats import read_threat

# Canonical palette -- mirrors sim/view.py so the re-render lands in the SIM's image distribution.
_GRASS = (25, 80, 25)
_RIVER = (120, 90, 30)
_YOU = (230, 90, 60)
_ENEMY = (60, 60, 230)

_TOWER_DIM = 6          # per-tower HP fractions (mine L/R/king, theirs L/R/king)

# Spells that may be cast ANYWHERE, including the enemy half. For these the "which half did it
# appear in" ownership rule is meaningless and the in-flight sprite is not the target, so they take
# the *_aoe (impact indicator) path instead -- see _TeamTracker.update.
# THE LOG IS DELIBERATELY EXCLUDED: its cast point is your OWN half (it rolls forward), so the half
# rule still holds for it -- and measured over two of these videos the detector emitted the_log 166
# times but the_log_aoe only twice (1%), so demanding an AOE would delete the card entirely.
# Measured AOE share for the two that ARE here: rocket 51% (48 vs 47), tornado 88% (64 vs 9).
_ANYWHERE_CAST = ("rocket", "tornado")


# ---------------------------------------------------------------------------
# Team by GEOMETRY (foreign-footage-safe), carried by a light tracker
# ---------------------------------------------------------------------------
class _TeamTracker:
    """Assign team from the half a unit was FIRST seen in, then carry it as the unit advances.

    Colour/HP-bar votes are what the live `TeamTracker` leans on, and they are measurably wrong on
    a foreign rendering. Position is not: a unit that appears in the learn-side half is the learn
    player's, and it stays theirs while it walks up the board. Tracks link by CARD IDENTITY within
    a radius, so an enemy defender meeting your push cannot steal its tag.

    GHOST MEMORY (anti-flicker). The detector DROPS units for a sample or two on this footage, and
    a dropped-then-refound unit used to look brand new -- MEASURED: one stationary X-Bow at
    (0.26, 0.51) was reported as a fresh play three separate times. Expired tracks are therefore
    kept as `ghosts` for `ghost_s` seconds and a "new" detection that lands near one REVIVES it
    instead of counting as an appearance.
    """

    def __init__(self, river_y: float, learn_bottom: bool = True, radius: float = 0.12,
                 ghost_s: float = 4.0, ghost_radius: float = 0.20, anywhere_bases=()):
        self.river_y = float(river_y)
        self.learn_bottom = bool(learn_bottom)
        self.radius = float(radius)
        self.ghost_s = float(ghost_s)
        self.ghost_radius = float(ghost_radius)
        self.anywhere = set(anywhere_bases)   # spells the half-rule cannot judge (see _ANYWHERE_CAST)
        self.tracks: List[dict] = []          # {key, x, y, team, age}
        self.ghosts: List[dict] = []          # {key, x, y, team, t} -- recently lost tracks
        self.inflight = 0                     # projectiles rejected as placements (diagnostics)

    def _key(self, d: Detection) -> str:
        """What a track links on. For anywhere-cast spells the RAW class is used so the in-flight
        projectile (`rocket`) and the impact indicator (`rocket_aoe`) stay SEPARATE tracks -- they
        share a base, and if they merged the AOE would be swallowed as 'already tracked' and the
        play would be lost. Everything else links on the base, so evo/variant naming cannot split
        one troop into two tracks."""
        return d.cls if d.base in self.anywhere else d.base

    def _side_team(self, y: float) -> str:
        own = y >= self.river_y if self.learn_bottom else y < self.river_y
        return "mine" if own else "enemy"

    def _revive(self, d: Detection):
        """A ghost of the same card near this spot => the detector merely lost it. Returns its team."""
        key = self._key(d)
        for gi, g in enumerate(self.ghosts):
            if g["key"] == key and abs(g["x"] - d.cx) + abs(g["y"] - d.gy) <= self.ghost_radius:
                self.ghosts.pop(gi)
                return g["team"]
        return None

    def update(self, dets: List[Detection], t: float) -> List[Detection]:
        """Tag every detection with a geometry-derived team; return the genuinely NEW learn-side units."""
        used, fresh = set(), []
        for d in dets:
            best, best_dist = None, self.radius
            for ti, tr in enumerate(self.tracks):
                if ti in used or tr["key"] != self._key(d):
                    continue
                dist = abs(tr["x"] - d.cx) + abs(tr["y"] - d.gy)
                if dist < best_dist:
                    best, best_dist = ti, dist
            if best is None:                                   # not on any live track
                revived = self._revive(d)                      # ...a flicker of one we just lost?
                if d.base in self.anywhere:
                    # ANYWHERE-CAST SPELL. The half rule says nothing here -- a Rocket aimed at the
                    # enemy tower LANDS IN THE TOP HALF, so the geometry rule called every one of the
                    # learn player's rockets an ENEMY card and threw the play away (measured: the
                    # rocket_aoe median y is 0.29, deep in the enemy half). Ownership is therefore
                    # left to the HAND GATE -- a direct observation instead of a guess -- which also
                    # agrees with the on-screen AOE indicator only rendering for the caster.
                    team = "mine"
                    # ...and only the *_aoe indicator marks the cast TARGET. The bare projectile is a
                    # sprite in MID-FLIGHT whose position is not where the spell was aimed (measured:
                    # in-flight rocket spans y 0.20-0.62 while its impact sits at y~0.29).
                    is_placement = d.cls.endswith("_aoe")
                    if not is_placement:
                        self.inflight += 1
                else:
                    team = revived if revived is not None else self._side_team(d.gy)
                    is_placement = True
                self.tracks.append({"key": self._key(d), "x": d.cx, "y": d.gy, "team": team, "age": 0})
                used.add(len(self.tracks) - 1)
                d.team = team
                if team == "mine" and revived is None and is_placement:
                    fresh.append(d)                            # a REAL appearance on the learn side
            else:
                tr = self.tracks[best]
                tr["x"], tr["y"], tr["age"] = d.cx, d.gy, 0
                used.add(best)
                d.team = tr["team"]                            # carry the tag across the river
        keep = []
        for ti, tr in enumerate(self.tracks):                  # age out tracks the detector lost...
            if ti in used:
                keep.append(tr)
                continue
            tr["age"] += 1
            if tr["age"] <= 3:
                keep.append(tr)
            else:                                              # ...but remember them as ghosts
                self.ghosts.append({"key": tr["key"], "x": tr["x"], "y": tr["y"],
                                    "team": tr["team"], "t": t})
        self.tracks = keep
        self.ghosts = [g for g in self.ghosts if t - g["t"] <= self.ghost_s]
        return fresh


class _HandWatch:
    """Did this card just LEAVE the pro's hand? -- the signal that a card was actually played.

    The old miner inferred a play from a unit APPEARING, which cannot tell a deploy apart from an
    enemy troop walking into the learn half or the detector re-finding something already there.
    A card leaving the tray is a direct, positive observation of a play, and the tray reader was
    verified to work on this footage (its ids matched the visible elixir costs exactly) -- unlike
    the elixir bar, which does not.

    Robust to PARTIAL reads: only a recent sighting in the tray is required, not a perfect one, so
    the frequent 2-of-4 reads still gate correctly.
    """

    def __init__(self, window_s: float = 3.0):
        self.window = float(window_s)
        self.last_in_hand: dict = {}
        self.present: set = set()

    def observe(self, t: float, hand_ids) -> None:
        self.present = {int(c) for c in hand_ids if c is not None and int(c) >= 0}
        for c in self.present:
            self.last_in_hand[c] = t

    def just_left(self, card_id: int, t: float) -> bool:
        if card_id in self.present:
            return False                                       # still in the tray -> not played
        seen = self.last_in_hand.get(int(card_id))
        return seen is not None and 0.0 < (t - seen) <= self.window


class _ElixirModel:
    """Elixir RECONSTRUCTED from the rules instead of read off the bar.

    `Vision.read_elixir` is calibrated to OUR capture (elixir.pip_xs / bar_y) and MEASURED on this
    footage it returns a constant 2 on every frame -- a dead feature that would teach the policy a
    lie. But elixir is deterministic: it regenerates at a known rate and every card has a known
    cost, and the hand gate above tells us exactly which card was played and when. So we simulate
    it, which is also rendering-independent (the same reason we re-render the image ourselves).

    Self-correcting: a play PROVES the pro could afford that card, so the estimate is raised to the
    cost before spending it. Together with the 0..10 clamp the initial offset washes out quickly.
    """

    # 1 elixir per 2.8 s in SINGLE elixir. Double/triple time cannot be located in a clip that has
    # no match-start anchor, so the single rate is used throughout -- it UNDER-estimates late-match
    # elixir, which is the safe direction (it never invents elixir the pro did not have).
    REGEN_S = 2.8

    def __init__(self, start: float = 5.0):
        self.e = float(start)

    def tick(self, dt: float) -> None:
        self.e = min(10.0, self.e + max(0.0, dt) / self.REGEN_S)

    def spend(self, cost: float) -> float:
        """Returns the elixir the pro had AT DECISION TIME, then deducts the card's cost."""
        before = max(self.e, float(cost))       # he played it, so he had at least this much
        self.e = max(0.0, before - float(cost))
        return before


# ---------------------------------------------------------------------------
# Canonical re-render (OUR renderer, never the pro's pixels)
# ---------------------------------------------------------------------------
def canonical_render(dets: List[Detection], cfg, oh: int, ow: int, river_y: float) -> np.ndarray:
    """Synthetic top-down arena rebuilt from detections, in the sim's palette and frame geometry.

    Geometry is FRAME-normalized (the same space `detect_obs.detection_channels` and the live env
    rasterize into), so the RGB and the semantic channels of one sample always agree.
    """
    img = np.zeros((int(oh), int(ow), 3), np.uint8)
    img[:, :] = _GRASS
    ry = int(np.clip(river_y, 0.0, 0.999) * oh)
    img[ry, :] = _RIVER
    mine_a, enemy_a, _ = _anchors(cfg)
    for anchors, col in ((mine_a, _YOU), (enemy_a, _ENEMY)):
        for i, (ax, ay) in enumerate(anchors or []):
            cx, cy = int(ax * ow), int(ay * oh)
            hw = 3 if i == 2 else 2                            # index 2 = king (drawn bigger)
            img[max(0, cy - hw):cy + hw + 1, max(0, cx - hw):cx + hw + 1] = col
    for d in dets:
        cx, cy = int(d.cx * ow), int(d.gy * oh)
        if 0 <= cy < oh and 0 <= cx < ow:
            img[cy, cx] = _YOU if d.team == "mine" else _ENEMY
    return img


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------
def _deck_index(deck_keys: List[str], det_cls: str) -> int:
    """Map a detector class to a DECK IDENTITY index (exact `<card>_evo` first, then the base)."""
    base = card_threat.base_key(det_cls)
    if det_cls in deck_keys:
        return deck_keys.index(det_cls)
    if base in deck_keys:
        return deck_keys.index(base)
    return -1


def _tower_block(use_tower: bool) -> np.ndarray:
    """Tower HP fractions. A replay gives no reliable per-tower HP read, so they are reported FULL.
    Stated plainly because it is an approximation: BC learns placement/selection from these frames,
    not tower-race arithmetic, and the sim (which has ground truth) is what teaches the latter."""
    return np.ones(_TOWER_DIM, np.float32) if use_tower else np.zeros(0, np.float32)


def _mine_one(args) -> int:
    """Worker entry: mine ONE video in its own process (Windows-spawn safe -- module-level,
    picklable args only). Returns the sample count so the parent can total them."""
    cfg_path, video, kw = args
    from .config import Config
    build_replay_bc(Config.load(cfg_path), replays=video, jobs=1, **kw)
    return 0


def build_replay_bc(cfg, replays=None, weights=None, conf=None, stride=None, out=None,
                    min_hand: int = 2, limit: int = 0, preview: bool = False,
                    jobs: int = 1) -> None:
    """Mine replay videos into per-video `dataset.npz` files that `train-bc --data` can load.

    ``jobs`` > 1 mines that many VIDEOS CONCURRENTLY, one process each. The videos are fully
    independent (separate captures, trackers and output dirs), and a single video's pipeline
    is one core's worth of decode + detector, so on a 16-core box this is close to linear in
    wall-clock until the video count runs out.
    """
    from .vision import Vision

    _jobs = max(1, int(jobs))
    _dir = Path(replays) if replays else Path(
        cfg.path(cfg.get("replay_mine", "replays_dir", default="data/replays")))
    if _jobs > 1 and _dir.is_dir():
        import multiprocessing as mp
        _vids = sorted(p for p in _dir.glob("*") if p.suffix.lower() in _VIDEO_EXTS)
        if len(_vids) > 1:
            n = min(_jobs, len(_vids))
            kw = dict(weights=weights, conf=conf, stride=stride, out=out,
                      min_hand=min_hand, limit=limit, preview=preview)
            print(f"[replay-bc] {len(_vids)} videos across {n} parallel job(s) "
                  f"-- each video is one process (decode + detector are per-core)", flush=True)
            ctx = mp.get_context("spawn")
            with ctx.Pool(n) as pool:
                pool.map(_mine_one, [(None, str(v), kw) for v in _vids])
            print("[replay-bc] all jobs done -- per-video dataset.npz files are in place")
            return

    detector = load_detector(cfg, weights)
    if not detector.available:
        print("[replay-bc] no trained board detector -- this needs one to recover plays from video "
              "(there is no mouse log). Train/pin one under runs/detect/*/weights/best.pt first.")
        return

    replays_dir = Path(replays) if replays else Path(
        cfg.path(cfg.get("replay_mine", "replays_dir", default="data/replays")))
    if replays_dir.is_file() and replays_dir.suffix.lower() in _VIDEO_EXTS:
        videos = [replays_dir]                     # a worker was handed ONE video
        replays_dir = replays_dir.parent
    else:
        videos = sorted(p for p in replays_dir.glob("*") if p.suffix.lower() in _VIDEO_EXTS) \
            if replays_dir.exists() else []
    if not videos:
        print(f"[replay-bc] no replay videos ({'/'.join(_VIDEO_EXTS)}) under {replays_dir}")
        return

    conf = float(conf if conf is not None else cfg.get("replay_mine", "detect_conf", default=0.30))
    stride = int(stride if stride is not None else cfg.get("replay_mine", "frame_stride", default=30))
    learn_bottom = str(cfg.get("replay_mine", "learn_side", default="bottom")).lower() != "top"
    out_root = Path(out) if out else Path(cfg.path("data/replay_bc"))

    db = CardDB(cfg)
    kb = card_threat.load_cards(cfg)
    vision = Vision(cfg)
    aspace = ActionSpace(cfg)
    deck_keys = list(getattr(vision, "deck_keys", []) or db.deck_identities())
    n_cards = len(deck_keys)
    # Per-identity elixir cost -- the other half of the deterministic elixir reconstruction.
    card_cost = [float(db.elixir(k) or db.elixir(card_threat.base_key(k)) or 0.0) for k in deck_keys]
    ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
    gw, gh = cfg.get("action", "grid", default=[18, 24])
    river_y = float(cfg.get("action", "deploy_top", default=0.44))
    use_detector_blocks = bool(cfg.get("observation", "use_detector", default=False))
    use_interactions = bool(cfg.get("observation", "use_interactions", default=False))
    use_tower = bool(cfg.get("observation", "use_tower_hp", default=True))
    use_canvas = detect_obs.canvas_enabled(cfg)

    # the identity/interaction blocks are built by the SAME offline helpers `label` uses, so a
    # replay-mined sample carries the exact threat layout a recorded/live sample does.
    from .label import _identity_blocks, _interaction_block

    total = 0
    for video in videos:
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f"[replay-bc] cannot open {video.name}")
            continue
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dt = max(1e-3, stride / fps)
        tracker = _TeamTracker(river_y, learn_bottom, anywhere_bases=_ANYWHERE_CAST)
        hand_watch = _HandWatch()
        elixir_model = _ElixirModel()
        # Canvas motion history for THIS video. Fed on every scanned frame (not just plays) so the
        # older slices exist when a play lands; frame stride is the sampling clock.
        canvas_stack = detect_obs.CanvasStack(detect_obs.canvas_stack_len(cfg),
                                              detect_obs.canvas_stack_dt(cfg))
        opp_mem = card_threat.OpponentMemory(kb) if use_detector_blocks else None
        obs, acts, hands, nexts, elixirs, threats = [], [], [], [], [], []
        skipped_card = skipped_hand = skipped_gate = skipped_flicker = 0
        prev_frame = None
        prev_hand_vec = None
        dbg_dir = out_root / video.stem / "preview"
        if preview:
            dbg_dir.mkdir(parents=True, exist_ok=True)

        fi = 0
        # SEQUENTIAL SCAN, NEVER SEEK (2026-08-15). This loop used to
        # `cap.set(CAP_PROP_POS_FRAMES, fi)` before every read: on a long-GOP h264 file each
        # seek re-decodes from the nearest keyframe, MEASURED at 137 ms per call -- 121.7 s of
        # 887 calls, i.e. 88% of the miner's entire runtime, to advance 15 frames. Reading
        # forward and `grab()`ing the skipped frames (decode-free) does the same job ~5x
        # faster. `pos` tracks the true decoder position so the stride is exact.
        pos = 0
        while fi < n_frames:
            while pos < fi:                               # skip WITHOUT decoding
                if not cap.grab():
                    break
                pos += 1
            ok, frame = cap.read()
            pos += 1
            if not ok:
                break
            t_now = fi / fps
            dets = detector.detect(frame, conf)
            if use_canvas:                                    # keep the motion history warm every frame
                chf = detect_obs.detection_channels(dets, db, int(oh), int(ow))
                if detect_obs.predictive_enabled(cfg):
                    # Replay footage has no measured warp; frame space approximates board
                    # space here (the 18:32 aspect assumption interactions already makes).
                    mt, et, _k = _bc_towers(cfg)
                    units = [((d.team if d.team in ("mine", "enemy") else "enemy"), d.base,
                              d.cx, d.gy) for d in dets if d.team in ("mine", "enemy")]
                    pred = detect_obs.predictive_channels(units, mt, et, db, int(oh), int(ow),
                                                          dt_s=detect_obs.predictive_dt(cfg),
                                                          horizon_s=detect_obs.eta_horizon(cfg))
                    chf = np.concatenate([chf, pred], axis=2)
                if detect_obs.hp_enabled(cfg):
                    items = [((d.team if d.team in ("mine", "enemy") else "enemy"), d.base,
                              d.cx, d.gy, detect_obs.read_hp_frac(frame, d))
                             for d in dets if d.team in ("mine", "enemy")]
                    chf = np.concatenate(
                        [chf, detect_obs.hp_channels(items, int(oh), int(ow))], axis=2)
                canvas_stack.push(detect_obs.channels_to_uint8(chf), t_now)
            fresh = tracker.update(dets, t_now)               # geometry-tagged teams + real appearances
            hand_ids = vision.recognize_hand(frame)           # the PRO's real tray (same card art)
            hand_watch.observe(t_now, hand_ids)               # ...before gating, so `present` is current
            hand_vec_now = np.asarray(vision.hand_multihot(hand_ids), np.float32)
            elixir_model.tick(dt)
            for sp in fresh:
                card = _deck_index(deck_keys, sp.cls)
                if card < 0:                                  # not a card in OUR deck -> unusable
                    skipped_card += 1
                    continue
                # THE GATE: a unit appearing is not a play -- a card LEAVING THE TRAY is. This is
                # what rejects the detector re-finding a unit already on the board and the enemy
                # troops that merely walk across the river into the learn half.
                if not hand_watch.just_left(card, t_now):
                    skipped_gate += 1
                    continue
                # The hand the pro DECIDED from is the one BEFORE the card left it.
                base_vec = prev_hand_vec if prev_hand_vec is not None else hand_vec_now
                if int((base_vec > 0.5).sum()) < int(min_hand):
                    skipped_hand += 1                         # too little of the tray read to learn
                    continue                                  # "which card among these" from
                hand_vec = base_vec.copy()
                hand_vec[card] = 1.0                          # the played card is in hand by proof
                # --- observation: OUR canonical render + the semantic canvas (never his pixels) ---
                img = canonical_render(dets, cfg, int(oh), int(ow), river_y)
                if use_canvas:
                    img = np.concatenate([img, canvas_stack.stacked(t_now)], axis=2)
                # --- threat vector: identical layout to label/live/sim ---
                parts = [read_threat(frame, cfg).vector()]
                if use_detector_blocks:
                    ident, mem = _identity_blocks(detector, kb, cfg, opp_mem, prev_frame, frame, dt)
                    parts += [ident, mem]
                if use_interactions:
                    parts.append(_interaction_block(detector, kb, cfg, frame))
                if use_tower:
                    parts.append(_tower_block(True))
                gx, gy = aspace.coords_to_grid(sp.cx, sp.gy)
                obs.append(img)
                acts.append([card, int(gx), int(gy)])
                hands.append(hand_vec)
                nexts.append(vision.next_onehot(vision.recognize_next(frame)))
                elixirs.append([elixir_model.spend(card_cost[card]) / 10.0])
                threats.append(np.concatenate(parts).astype(np.float32))
                if preview and len(obs) <= 40:
                    vis = frame.copy()
                    H, W = vis.shape[:2]
                    for d in dets:
                        col = _ENEMY if d.team == "enemy" else _YOU
                        cv2.circle(vis, (int(d.cx * W), int(d.gy * H)), 10, col, 2)
                    cv2.drawMarker(vis, (int(sp.cx * W), int(sp.gy * H)), (0, 255, 255),
                                   cv2.MARKER_TILTED_CROSS, 34, 3)
                    cv2.putText(vis, f"{deck_keys[card]} -> cell ({gx},{gy})  t={t_now:.1f}s", (8, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.imwrite(str(dbg_dir / f"play_{len(obs):03d}.png"), vis)
                if limit and len(obs) >= limit:
                    break
            prev_frame = frame
            prev_hand_vec = hand_vec_now
            if limit and len(obs) >= limit:
                break
            fi += stride
        cap.release()

        if obs:
            dst = out_root / video.stem
            dst.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                dst / "dataset.npz",
                obs=np.asarray(obs, dtype=np.uint8),
                acts=np.asarray(acts, dtype=np.int64),
                hands=np.asarray(hands, dtype=np.float32),
                nexts=np.asarray(nexts, dtype=np.float32),
                elixirs=np.asarray(elixirs, dtype=np.float32),
                threats=np.asarray(threats, dtype=np.float32),
                grid=np.asarray([int(gw), int(gh)], dtype=np.int64),
                deck=np.asarray(deck_keys),
            )
            total += len(obs)
        extra = []
        if skipped_gate:
            extra.append(f"{skipped_gate} no hand-drop (flicker / lane-walkers)")
        if tracker.inflight:
            extra.append(f"{tracker.inflight} spell in-flight (not the target)")
        if skipped_card:
            extra.append(f"{skipped_card} not-in-deck")
        if skipped_hand:
            extra.append(f"{skipped_hand} tray unread")
        tail = f"  (rejected: {', '.join(extra)})" if extra else ""
        print(f"[replay-bc] {video.name}: {len(obs)} sample(s){tail}", flush=True)

    print(f"[replay-bc] {total} sample(s) -> {out_root}")
    if total:
        print(f"[replay-bc] next:  run.py train-bc --data {out_root.name and out_root} --val-frac 0.2")
        print("[replay-bc] BC here is a WARM START, not the teacher -- the val split + early stop "
              "keep this small, detector-noisy set from being memorised; the sim still refines it.")
