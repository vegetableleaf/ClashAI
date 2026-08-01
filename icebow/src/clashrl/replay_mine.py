"""Stage 4 groundwork: mine EXTERNAL (pro / top-ladder) replay footage into strategy priors.

Goal (the user's request): learn from strong rocket-cycle players -- their DEFENSIVE
placements, POSITIVE ELIXIR TRADES, and when they ROCKET the enemy tower -- and use those
habits to sharpen the bot. This module is the *strategy-distillation* path: instead of
cloning someone else's pixels (which fails across renderings/decks, see log.txt Stage 4),
it distils external footage into compact, deck-agnostic PRIORS that reward shaping can lean on.

Why this is groundwork (not live yet)
-------------------------------------
Recovering "what card was played, where, against what" from a video with no mouse log
REQUIRES the board object detector (Stage 2/3). Until a trained detector exists
(``runs/detect/*/weights/best.pt``), :func:`mine_replays` has nothing to read the board
with, so it reports readiness and stops -- the schema, the detector plug-point, the miner,
and the reward-scoring hooks below are all built and unit-safe so that the day the detector
lands you can drop replay videos into ``replay_mine.replays_dir`` and run ``run.py mine-replays``.

Pieces
------
* ``BoardDetector`` / :func:`load_detector` -- the DETECTOR PLUG-POINT (wraps the same
  Ultralytics YOLO/RT-DETR weights ``detect-preview`` uses; ``.available`` is False with no
  weights so callers degrade gracefully). Team (mine vs enemy) is inferred from colour.
* :class:`StrategyPriors` -- the versioned PRIOR SCHEMA + JSON (de)serialisation and the
  reward-scoring HOOKS (:meth:`placement_bonus` / :meth:`trade_bonus` /
  :meth:`rocket_opportunity`). Pure functions -- ready for ``env`` to call at Stage 4,
  gated behind ``rewards.strategy_prior_scale`` (0 = off, the default).
* :func:`mine_replays` (``run.py mine-replays``) -- runs the detector over replay videos and
  aggregates the priors to ``data/analysis/strategy_priors.json``.

Honest caveats (told the user): elixir/tower reads are calibrated to YOUR window, so external
footage of a different rendering may misread them; and only plays of cards in YOUR deck yield
usable placement/trade priors. The strategy buckets (:func:`threat_key`) are deck-agnostic
(win_condition / siege / tank / swarm / air / spell), which is what makes the priors transfer.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import card_threat
from .reward import _anchors

__all__ = [
    "Detection", "BoardDetector", "load_detector",
    "StrategyPriors", "threat_key", "mine_replays",
]

SCHEMA_VERSION = 1
_VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov", ".webm")

# Deck-agnostic strategy buckets, most salient first (a push is classified by its
# strongest enemy unit's KB profile so priors generalise across specific cards).
_THREAT_BUCKETS = ("win_condition", "siege", "tank", "air", "swarm", "spell", "support")


# ---------------------------------------------------------------------------
# Detector plug-point
# ---------------------------------------------------------------------------
@dataclass
class Detection:
    """One detected unit/spell on the board (normalized box), team inferred from colour."""
    cls: str                       # detector class name (e.g. "hog_rider", "rocket_aoe")
    cx: float
    cy: float
    w: float
    h: float
    conf: float
    team: str = "unknown"          # "mine" | "enemy" | "unknown"
    ground_cy: Optional[float] = None   # shadow (true ground) y for FLYERS; None = ground unit (use cy)

    @property
    def base(self) -> str:
        """Base card key (strips _evo/_hero/_ability/_aoe)."""
        return card_threat.base_key(self.cls)

    @property
    def gy(self) -> float:
        """The unit's REAL grid y = its SHADOW / ground position. Flying sprites are drawn ABOVE the
        ground, so the box centre sits high; the shadow marks the true tile. Ground units fall back to
        the box centre. Use this (not ``cy``) for depth, movement prediction, and grid placement."""
        return self.cy if self.ground_cy is None else self.ground_cy

    @property
    def ground(self) -> "tuple[float, float]":
        """Normalized (x, y) of the unit ON THE GROUND -- shadow-corrected for flyers. Use for spell
        targeting + grid placement so a spell/defender aims where the flyer really is, not at its sprite."""
        return (self.cx, self.gy)


def _team_of(frame: np.ndarray, d_cx: float, d_cy: float, d_w: float, d_h: float) -> str:
    """Infer team from the dominant team-tint (blue = mine/bottom, red = enemy/top) inside the box."""
    h, w = frame.shape[:2]
    x0 = max(0, int((d_cx - d_w / 2) * w)); x1 = min(w, int((d_cx + d_w / 2) * w))
    y0 = max(0, int((d_cy - d_h / 2) * h)); y1 = min(h, int((d_cy + d_h / 2) * h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return "unknown"
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    red = (cv2.inRange(hsv, (0, 120, 90), (10, 255, 255)).sum()
           + cv2.inRange(hsv, (169, 120, 90), (179, 255, 255)).sum())
    blue = cv2.inRange(hsv, (100, 120, 90), (128, 255, 255)).sum()
    if max(red, blue) == 0:
        return "unknown"
    return "enemy" if red >= blue else "mine"


class BoardDetector:
    """Thin wrapper over an Ultralytics detector (YOLO/RT-DETR). ``available`` is False when no
    weights are found, so the miner can report readiness instead of crashing."""

    def __init__(self, model=None, names: Optional[Dict[int, str]] = None, db=None, fly_offset: float = 0.0):
        self._model = model
        self._names = names or {}
        self._db = db                      # CardDB, for the flying-unit shadow correction (None -> skip)
        self._fly_offset = float(fly_offset)   # normalized DOWNWARD shift from a flyer's sprite to its shadow

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray, conf: float = 0.3) -> List[Detection]:
        if self._model is None:
            return []
        h, w = frame.shape[:2]
        res = self._model.predict(frame, conf=conf, verbose=False)[0]
        out: List[Detection] = []
        for b in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
            bw, bh = (x2 - x1) / w, (y2 - y1) / h
            cls = self._names.get(int(b.cls[0]), str(int(b.cls[0])))
            team = _team_of(frame, cx, cy, bw, bh)
            # FLYING-UNIT SHADOW CORRECTION: a flyer's sprite is drawn above the ground, so its box
            # centre is too high -- the real tile is at its shadow, ~fly_offset below. Shift cy down so
            # depth / movement prediction / spell targeting use the true ground position.
            gcy = None
            if self._fly_offset > 0 and self._db is not None and \
                    card_threat.profile(self._db, card_threat.base_key(cls)).flying:
                gcy = min(1.0, cy + self._fly_offset)
            out.append(Detection(cls, cx, cy, bw, bh, float(b.conf[0]), team, gcy))
        return out


def load_detector(cfg, weights: Optional[str] = None) -> BoardDetector:
    """Load the trained board detector (mirrors ``detect_preview``'s YOLO/RT-DETR fallback).
    Returns an *unavailable* :class:`BoardDetector` when no weights exist yet (Stage 2/3 pending)."""
    from .detect import _resolve_weights
    wpath, _ = _resolve_weights(cfg, weights)
    if wpath is None or not Path(wpath).exists():
        return BoardDetector()
    try:
        from ultralytics import YOLO
        model = YOLO(str(wpath))
    except Exception:
        try:
            from ultralytics import RTDETR
            model = RTDETR(str(wpath))
        except Exception as exc:                       # ultralytics missing / bad weights
            print(f"[mine-replays] could not load detector ({exc}); pip install ultralytics")
            return BoardDetector()
    names = getattr(model, "names", {}) or {}
    fly_offset = float(cfg.get("observation", "flying_shadow_offset", default=0.045))
    db = None
    if fly_offset > 0:
        try:
            from .cards import CardDB
            db = CardDB(cfg)                            # to look up which detected classes are flyers
        except Exception:
            db = None
    return BoardDetector(model, {int(k): str(v) for k, v in names.items()}, db=db, fly_offset=fly_offset)


# ---------------------------------------------------------------------------
# Strategy-prior schema + reward hooks
# ---------------------------------------------------------------------------
def threat_key(db, enemy: List[Detection]) -> str:
    """Reduce the enemy units on the board to ONE deck-agnostic strategy bucket, picking the
    most strategically salient (a win condition trumps a tank trumps a swarm ...). Returns
    ``"none"`` when there is no enemy unit to react to."""
    if not enemy:
        return "none"
    best_rank, best = len(_THREAT_BUCKETS), "support"
    for d in enemy:
        p = card_threat.profile(db, d.base)
        bucket = ("win_condition" if p.win_condition else "siege" if p.siege
                  else "spell" if p.spell else "tank" if p.tank else "air" if p.flying
                  else "swarm" if p.swarm else "support")
        rank = _THREAT_BUCKETS.index(bucket)
        if rank < best_rank:
            best_rank, best = rank, bucket
    return best


@dataclass
class StrategyPriors:
    """Distilled, deck-agnostic priors from external replays + the reward-scoring hooks.

    Loaded read-only by reward shaping (Stage 4). All bonuses return ~[0, 1]; the CALLER
    multiplies by ``rewards.strategy_prior_scale`` (0 = off) so the priors never fire until
    you opt in. Empty priors (no data / no file) make every bonus 0 -- safe by construction.
    """
    # placements[threat_key][card][zone] = count
    placements: Dict[str, Dict[str, Dict[str, int]]] = field(default_factory=dict)
    # trades[threat_key][card] = {"n", "elixir_delta_sum", "positive"}
    trades: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)
    # rocket_tower launch conditions (elixir histogram + board state)
    rocket_tower: Dict[str, object] = field(default_factory=lambda: {
        "elixir_bins": [0] * 11, "board_quiet": 0, "board_pressured": 0, "n": 0})
    n_records: int = 0

    # --- reward-scoring hooks (pure; ready for env to call at Stage 4) -----
    def placement_bonus(self, tkey: str, card: str, zone: str) -> float:
        """How characteristic it is for strong players to place ``card`` in ``zone`` vs
        ``tkey`` -- the fraction of their ``(tkey, card)`` plays that landed in that zone."""
        zones = self.placements.get(tkey, {}).get(card)
        if not zones:
            return 0.0
        total = sum(zones.values())
        return zones.get(zone, 0) / total if total else 0.0

    def trade_bonus(self, tkey: str, card: str) -> float:
        """Positive when strong players win the elixir trade using ``card`` vs ``tkey`` --
        the share of those responses that were a positive (cheaper-defence) trade, in [0, 1]."""
        t = self.trades.get(tkey, {}).get(card)
        if not t or not t.get("n"):
            return 0.0
        return float(t["positive"]) / float(t["n"])

    def rocket_opportunity(self, elixir: Optional[int], board_quiet: bool) -> float:
        """How well the current moment matches when strong players ROCKET a tower: they mostly
        chip when they can afford it and the board is safe. Returns ~[0, 1]."""
        rt = self.rocket_tower
        n = int(rt.get("n", 0))
        if n <= 0:
            return 0.0
        score = 0.0
        if elixir is not None:
            bins = rt.get("elixir_bins") or [0] * 11
            e = int(np.clip(elixir, 0, 10))
            score += 0.5 * (bins[e] / n if n else 0.0)
        quiet = int(rt.get("board_quiet", 0)); press = int(rt.get("board_pressured", 0))
        denom = quiet + press
        if denom:
            share = quiet / denom
            score += 0.5 * (share if board_quiet else 1.0 - share)
        return float(np.clip(score, 0.0, 1.0))

    # --- aggregation --------------------------------------------------------
    def add_placement(self, tkey: str, card: str, zone: str) -> None:
        self.placements.setdefault(tkey, {}).setdefault(card, defaultdict(int))
        self.placements[tkey][card][zone] += 1

    def add_trade(self, tkey: str, card: str, elixir_delta: float) -> None:
        t = self.trades.setdefault(tkey, {}).setdefault(
            card, {"n": 0, "elixir_delta_sum": 0.0, "positive": 0})
        t["n"] += 1
        t["elixir_delta_sum"] += float(elixir_delta)
        if elixir_delta > 0:
            t["positive"] += 1

    def add_rocket_tower(self, elixir: Optional[int], board_quiet: bool) -> None:
        rt = self.rocket_tower
        rt["n"] = int(rt.get("n", 0)) + 1
        if elixir is not None:
            rt["elixir_bins"][int(np.clip(elixir, 0, 10))] += 1
        rt["board_quiet" if board_quiet else "board_pressured"] += 1

    # --- (de)serialisation --------------------------------------------------
    def to_json(self) -> dict:
        def _plain(d):
            return {k: {c: dict(z) for c, z in cd.items()} for k, cd in d.items()}
        return {
            "schema_version": SCHEMA_VERSION,
            "source": "replay_mine",
            "generated": datetime.now().isoformat(timespec="seconds"),
            "n_records": self.n_records,
            "placements": _plain(self.placements),
            "trades": {k: {c: dict(t) for c, t in cd.items()} for k, cd in self.trades.items()},
            "rocket_tower": dict(self.rocket_tower),
        }

    @classmethod
    def from_json(cls, data: dict) -> "StrategyPriors":
        sp = cls()
        sp.n_records = int(data.get("n_records", 0))
        for k, cd in (data.get("placements") or {}).items():
            for c, z in cd.items():
                for zone, n in z.items():
                    sp.placements.setdefault(k, {}).setdefault(c, defaultdict(int))[zone] = int(n)
        for k, cd in (data.get("trades") or {}).items():
            for c, t in cd.items():
                sp.trades.setdefault(k, {})[c] = {
                    "n": int(t.get("n", 0)),
                    "elixir_delta_sum": float(t.get("elixir_delta_sum", 0.0)),
                    "positive": int(t.get("positive", 0))}
        if data.get("rocket_tower"):
            rt = data["rocket_tower"]
            sp.rocket_tower = {
                "elixir_bins": [int(x) for x in (rt.get("elixir_bins") or [0] * 11)],
                "board_quiet": int(rt.get("board_quiet", 0)),
                "board_pressured": int(rt.get("board_pressured", 0)),
                "n": int(rt.get("n", 0))}
        return sp

    @classmethod
    def load(cls, cfg) -> "StrategyPriors":
        """Load ``data/analysis/strategy_priors.json`` if present, else empty (all bonuses 0)."""
        path = Path(cfg.path("data/analysis")) / "strategy_priors.json"
        if not path.exists():
            return cls()
        try:
            return cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return cls()


# ---------------------------------------------------------------------------
# Placement zone (relative to towers + the enemy push)
# ---------------------------------------------------------------------------
def _zone(nx: float, ny: float, enemy_centroid: Optional[Tuple[float, float]], cfg) -> str:
    """Classify WHERE a card was played, relative to the towers and the enemy push
    (a deck-agnostic version of ``analyze._placement_zone``)."""
    mine_a, enemy_a, _ = _anchors(cfg)

    def near(ax, ay, r=0.12):
        return abs(nx - ax) <= r and abs(ny - ay) <= r

    if len(enemy_a) >= 2 and (near(*enemy_a[0]) or near(*enemy_a[1])):
        return "enemy_princess"
    if len(enemy_a) >= 3 and near(*enemy_a[2]):
        return "enemy_king"
    if len(mine_a) >= 3 and near(*mine_a[2], r=0.10):
        return "my_king"
    if len(mine_a) >= 2 and (near(*mine_a[0], r=0.10) or near(*mine_a[1], r=0.10)):
        return "my_princess"
    if enemy_centroid is not None:
        cx, cy = enemy_centroid
        if abs(nx - cx) <= 0.14 and abs(ny - cy) <= 0.14:
            return "on_threat"
        if ny > cy + 0.05:
            return "behind_threat"
    lane = "left" if nx < 0.37 else "right" if nx > 0.63 else "center"
    half = "my_half" if ny >= 0.5 else "enemy_half"
    return f"{half}_{lane}"


# ---------------------------------------------------------------------------
# The miner
# ---------------------------------------------------------------------------
def _spawns(prev: Dict[str, Tuple[float, float]], now: List[Detection], learn_bottom: bool
            ) -> List[Detection]:
    """New learn-side (the imitated player's) units this frame vs the previous sampled frame --
    a coarse 'a card was just played' signal. Requires the unit on the learn-side half so
    troops merely walking into view mid-arena don't count as fresh plays."""
    out = []
    for d in now:
        if d.team != "mine":
            continue
        own_half = d.cy >= 0.5 if learn_bottom else d.cy < 0.5
        if not own_half:
            continue
        if d.cls not in prev:
            out.append(d)
    return out


def mine_replays(cfg, replays_arg=None, weights=None, conf=None, stride=None) -> None:
    """Distil strong-player replay videos into ``data/analysis/strategy_priors.json``.

    Needs a trained board detector; with none, reports readiness and the next steps (Stage 3)."""
    detector = load_detector(cfg, weights)
    replays_dir = Path(replays_arg) if replays_arg else Path(
        cfg.path(cfg.get("replay_mine", "replays_dir", default="data/replays")))
    conf = float(conf if conf is not None else cfg.get("replay_mine", "detect_conf", default=0.30))
    stride = int(stride if stride is not None else cfg.get("replay_mine", "frame_stride", default=3))
    learn_bottom = str(cfg.get("replay_mine", "learn_side", default="bottom")).lower() != "top"

    videos = sorted(p for p in replays_dir.glob("*") if p.suffix.lower() in _VIDEO_EXTS) \
        if replays_dir.exists() else []

    if not detector.available:
        staged = (f"  ({len(videos)} replay video(s) already staged.)" if videos
                  else f"  (stage videos under {replays_dir} when ready.)")
        print("[mine-replays] GROUNDWORK READY -- but no trained board detector yet.\n"
              "  This Stage-4 strategy miner needs the detector (Stage 2/3) to read external\n"
              "  footage (there is no mouse log to recover plays from). Once you have trained\n"
              "  weights at runs/detect/*/weights/best.pt:\n"
              f"    1) drop pro/top-ladder rocket-cycle replay videos into {replays_dir}\n"
              "    2) run:  python run.py mine-replays\n"
              "    3) enable the reward hooks with rewards.strategy_prior_scale > 0, then train-rl\n"
              + staged)
        return

    if not videos:
        print(f"[mine-replays] no replay videos ({'/'.join(_VIDEO_EXTS)}) under {replays_dir}")
        return

    db = card_threat.load_cards(cfg)
    from .vision import Vision
    vision = Vision(cfg)
    deck_bases = {card_threat.base_key(k) for k in getattr(vision, "deck_keys", [])}
    priors = StrategyPriors()
    records: List[dict] = []

    for video in videos:
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        prev: Dict[str, Tuple[float, float]] = {}
        n_here = 0
        fi = 0
        while fi < total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, frame = cap.read()
            if not ok:
                break
            dets = detector.detect(frame, conf)
            enemy = [d for d in dets if d.team == "enemy"]
            ecent = (float(np.mean([d.cx for d in enemy])),
                     float(np.mean([d.cy for d in enemy]))) if enemy else None
            tkey = threat_key(db, enemy)

            for sp_det in _spawns(prev, dets, learn_bottom):
                card = sp_det.base
                if deck_bases and card not in deck_bases:
                    continue                                   # only cards in YOUR deck are usable priors
                zone = _zone(sp_det.cx, sp_det.cy, ecent, cfg)
                elixir = None
                try:
                    elixir = int(vision.read_elixir(frame))
                except Exception:
                    pass
                priors.add_placement(tkey, card, zone)
                # Elixir trade = your card's cost vs the enemy push's cost (deck-agnostic proxy:
                # positive when you answer a pricier push with a cheaper card).
                atk = card_threat.profile(db, enemy[0].base).elixir if enemy else None
                dfn = card_threat.profile(db, card).elixir
                if atk is not None and dfn is not None:
                    priors.add_trade(tkey, card, float(atk) - float(dfn))
                if card == "rocket" and any(
                        card_threat.profile(db, e.base).building for e in enemy) is False:
                    # rocket while an enemy tower is the plausible target and our half is safe-ish
                    board_quiet = not any(
                        (d.cy >= 0.5 if learn_bottom else d.cy < 0.5) for d in enemy)
                    priors.add_rocket_tower(elixir, board_quiet)
                records.append({"video": video.name, "frame": fi, "t": round(fi / fps, 2),
                                "card": card, "zone": zone, "threat": tkey, "elixir": elixir})
                n_here += 1

            prev = {d.cls: (d.cx, d.cy) for d in dets if d.team == "mine"}
            fi += stride
        cap.release()
        print(f"[mine-replays] {video.name}: {n_here} play(s) mined")

    priors.n_records = len(records)
    out_dir = Path(cfg.path("data/analysis"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "strategy_priors.json").write_text(
        json.dumps(priors.to_json(), indent=2), encoding="utf-8")
    (out_dir / "strategy_records.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8")
    print(f"[mine-replays] {len(records)} plays across {len(videos)} video(s) "
          f"-> {out_dir / 'strategy_priors.json'}")
    print("[mine-replays] enable in training with rewards.strategy_prior_scale > 0, then run.py train-rl")
