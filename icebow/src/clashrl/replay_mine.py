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
from typing import Dict, List, Optional, Sequence, Tuple

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
    bar_vote: Optional[str] = None      # team from the HP-bar strip ABOVE the unit (None = no bar visible)
    body_vote: Optional[str] = None     # LAST-RESORT team hint from overwhelming body-art colour

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


def _team_masks(bgr: np.ndarray) -> "tuple[np.ndarray, np.ndarray]":
    """Boolean (red, blue) masks of saturated team colours in a BGR crop."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    red = (cv2.inRange(hsv, (0, 120, 90), (10, 255, 255)) > 0) \
        | (cv2.inRange(hsv, (169, 120, 90), (179, 255, 255)) > 0)
    blue = cv2.inRange(hsv, (100, 120, 90), (128, 255, 255)) > 0
    return red, blue


def _colour_counts(bgr: np.ndarray) -> "tuple[int, int]":
    """(red_pixels, blue_pixels) of saturated team colours in a BGR crop."""
    red, blue = _team_masks(bgr)
    return int(red.sum()), int(blue.sum())


def _bar_vote(frame: np.ndarray, d_cx: float, d_cy: float, d_w: float, d_h: float,
              multi: bool = False) -> Optional[str]:
    """Team from the HP-BAR / level-badge UI that Clash Royale draws over a unit's head. This is
    the only RELIABLE colour cue -- and it only exists once the unit has TAKEN DAMAGE (undamaged
    units show no team UI at all), so returning None ('no bar visible') is common and correct.

    Geometry is messy: the bar can float ABOVE the box or OVERLAP its top (tall sprites; boxes
    grown to include it), and a MULTI-UNIT card's box (Royal Recruits / 3M / minions -- ``multi``,
    from the KB unit count) contains SEVERAL bars at each unit's head, anywhere inside -- including
    SPLIT deploys where one box holds only part of the formation. So: singles scan from above the
    box into its top quarter; multi-unit boxes scan from above down through the WHOLE box.

    Because those windows contain unit ART, votes only count pixels inside BAR-SHAPED connected
    components: wide relative to a SINGLE unit's on-screen bar (near-constant scale, deliberately
    NOT a fraction of the box width -- one split-off recruit's bar still qualifies in a wide box),
    THIN, and flat (width >= 2.5x height). Art blobs (shoulders, helmets) are thick and fail the
    aspect test. Still requires a clear pixel count + a 2:1 colour majority over qualifying bars."""
    H, W = frame.shape[:2]
    xw = d_w * (0.4 if not multi else 0.48)
    x0 = max(0, int((d_cx - xw) * W)); x1 = min(W, int((d_cx + xw) * W))
    yb = d_cy - d_h / 2                                  # box top
    y0 = max(0, int((yb - d_h * 0.45) * H))
    y_end = (yb + d_h * 0.25) if not multi else (yb + d_h)   # multi: bars sit at every unit's head
    y1 = min(H, max(y0 + 1, int(y_end * H)))
    if x1 - x0 < 3 or y1 - y0 < 2:
        return None
    red_m, blue_m = _team_masks(frame[y0:y1, x0:x1])
    min_w = max(6, round(0.012 * W))                     # a single unit's bar width (absolute scale)
    max_h = max(5, round(0.007 * H))                     # bars are THIN at this render scale
    counts = []
    for mask in (red_m, blue_m):
        total = 0
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            cw, ch = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
            if cw >= min_w and ch <= max_h and cw >= 2.5 * ch:   # wide + thin + flat = bar-shaped
                total += int(stats[i, cv2.CC_STAT_AREA])
        counts.append(total)
    red, blue = counts
    hi, lo = max(red, blue), min(red, blue)
    if hi < 15 or hi < 2 * max(1, lo):
        return None
    return "enemy" if red > blue else "mine"


def _body_vote(frame: np.ndarray, d_cx: float, d_cy: float, d_w: float, d_h: float) -> Optional[str]:
    """LAST-RESORT team hint from the unit BODY (central ~60% of the box). Body art colours are
    exactly what used to misfire (a blue-ish enemy Knight read 'mine'; the team-colourless Log was
    a coin flip; rage/freeze tints flipped verdicts), so this only votes on an OVERWHELMING 3:1
    majority with a real pixel count -- anything weaker abstains and the tracker's motion/side
    evidence decides instead."""
    h, w = frame.shape[:2]
    cw, ch = d_w * 0.6, d_h * 0.6
    x0 = max(0, int((d_cx - cw / 2) * w)); x1 = min(w, int((d_cx + cw / 2) * w))
    y0 = max(0, int((d_cy - ch / 2) * h)); y1 = min(h, int((d_cy + ch / 2) * h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    red, blue = _colour_counts(frame[y0:y1, x0:x1])
    hi, lo = max(red, blue), min(red, blue)
    if hi < 25 or hi < 3 * max(1, lo):
        return None
    return "enemy" if red > blue else "mine"


def own_card_bases(db) -> List[str]:
    """Every BASE key our deck can legitimately put on the board, for :class:`TeamTracker`'s veto.

    Detections carry base keys (``knight``), the deck carries identities (``knight``, ``knight_evo``),
    so the evolved forms are folded down. One definition, shared by env.py and play.py, because two
    copies of "what counts as ours" would drift and the veto would silently start rejecting our own
    units in one path and not the other.
    """
    out = set()
    for k in (db.deck_identities() if db is not None else []):
        out.add(str(k))
        out.add(card_threat.base_key(str(k)))
    return sorted(out)


class TeamTracker:
    """LIVE team verdicts by EVIDENCE FUSION over short unit tracks, replacing the old colour-only
    guess. Colour was the weakest possible signal: the HP bar (the one reliable team colour) only
    exists AFTER a unit takes damage, so undamaged units were judged by their ART colours (a blue-ish
    enemy Knight read 'mine'), and the Log has no team UI at all (wood-brown pixels = a coin flip).

    Evidence per track, strongest first (a stronger verdict STICKS -- weaker later evidence can't flip it):

    1. OWN-PLAY ANCHOR -- a detection of the SAME base card near a card you just played is 'mine'
       (ground truth; spells included, so your own rolling Log is claimed at the cast point).
    2. MOTION -- net y displacement since first seen: units march TOWARD the enemy (up = 'mine',
       down = 'enemy'). Near-deterministic for one-way movers like the Log, and tornado pulls agree
       (an enemy dragged toward you still moves down). Buildings/idle units simply abstain.
    3. HP-BAR MAJORITY -- accumulated bar-strip votes (:func:`_bar_vote`) once the unit has a bar.
    4. FIRST-SEEN SIDE -- born deep in a half = that side's unit... UNLESS that half's princess
       tower is down: taking a tower opens a deploy POCKET on the loser's side of that lane, so
       the prior is gated per-lane via :meth:`set_towers` (anywhere-cards like the Miner and
       graveyard-style spawns are excluded from this prior entirely).
    5. BODY ART -- only an overwhelming 3:1 colour majority (:func:`_body_vote`), the last resort.

    The SIM doesn't need this (ground-truth teams); it's for live play / train-rl / the monitor overlay
    so the identity/memory blocks aren't polluted by your own units being read as enemy threats."""

    #: bases that may legally APPEAR deep inside either half (burrowers / grave spawns) -> no side prior
    NO_SIDE_PRIOR = frozenset({"miner", "goblin_drill", "skeletons"})

    def __init__(self, spawn_radius: float = 0.10, spawn_window_s: float = 2.5,
                 track_radius: float = 0.12, forget_s: float = 4.5,
                 enemy_window_s: Optional[float] = None, motion_min: float = 0.05,
                 deep_mine_y: float = 0.62, deep_enemy_y: float = 0.38,
                 own_cards: Optional[Sequence[str]] = None):
        # DECK VETO -- a hard constraint, not another piece of evidence. A unit on OUR side can only
        # be a card from OUR deck, so a "mine" verdict for a card we do not own is wrong BY
        # CONSTRUCTION, whatever the colour/motion/side evidence said. Every rank above can produce
        # it: the side prior tags an enemy Earthquake landing on our tower "mine" (it is born deep in
        # our half and never moves), a bar strip drawn over OUR units votes "mine" for the enemy spell
        # covering them, and the own-play anchor claims anything near a play recorded without a base.
        #
        # MEASURED over the three recorded sessions at the live 10 Hz cadence: 158 of 1482 ally-tagged
        # detections (10.7%) named a card outside this deck. This turns all of them into "enemy",
        # which is what they are. It CANNOT fix the mirror case -- an enemy Knight or Skeletons read
        # as ours passes the check, since those are in the deck -- so the residual error is real but
        # invisible to this rule and to the audit that motivated it.
        self.own_cards = frozenset(str(c) for c in own_cards) if own_cards else None
        self.spawn_radius = float(spawn_radius)
        self.spawn_window_s = float(spawn_window_s)
        # ENEMY-side plays (a Miner / anything you drop on THEIR half) linger at their target, so they get
        # a LONGER spawn window; YOUR-half plays keep the short one so an enemy ENGAGING your fresh defender
        # (near its spawn) isn't hidden as 'mine' for long.
        self.enemy_window_s = float(enemy_window_s) if enemy_window_s is not None else float(spawn_window_s)
        self.track_radius = float(track_radius)
        self.forget_s = float(forget_s)
        self.motion_min = float(motion_min)        # net |dy| that counts as marching (not jitter/knockback)
        self.deep_mine_y = float(deep_mine_y)      # first seen BELOW this -> deep in MY half
        self.deep_enemy_y = float(deep_enemy_y)    # first seen ABOVE this -> deep in ENEMY half
        self.reset()

    def reset(self) -> None:
        self._plays: list = []     # recent own plays: (x, y, t, base)
        self._tracks: list = []    # dicts: x, y, x0, y0, base, t, team, rank, bm, be
        self._pocket_my = [False, False]      # [L, R]: MY princess down -> ENEMY pocket in that lane of MY half
        self._pocket_enemy = [False, False]   # [L, R]: ENEMY princess down -> MY pocket in that lane of THEIRS

    def set_towers(self, mine_alive, enemy_alive) -> None:
        """Feed the tower-destruction latches (``TowerTracker``): a fallen PRINCESS opens the deploy
        pocket in front of it, voiding the first-seen-side prior for that lane -- an enemy dropped in
        the pocket on YOUR half must not be presumed 'mine' (and vice versa on their half)."""
        self._pocket_my = [not bool(a) for a in list(mine_alive)[:2]] or [False, False]
        self._pocket_enemy = [not bool(a) for a in list(enemy_alive)[:2]] or [False, False]

    def record_play(self, x: float, y: float, t: float, base: Optional[str] = None) -> None:
        """Register a card YOU just played at normalized (x, y): the matching unit that appears there is
        yours. ``base`` (the card's base key) restricts the anchor to detections of the SAME card, so an
        enemy answer dropped onto your spawn -- or into a pocket right on top of it -- isn't claimed."""
        self._plays.append((float(x), float(y), float(t), base))

    @staticmethod
    def _in_lane(x: float, pockets) -> bool:
        """Is normalized x inside an OPEN pocket lane? (lanes overlap through the centre to be safe)"""
        return (x < 0.55 and pockets[0]) or (x > 0.45 and pockets[1])

    def _claim(self, team: str, base: str) -> str:
        """Apply the deck veto: a card we do not own is the OPPONENT'S, whatever the evidence said.

        Symmetric on purpose. It rescues the "mine" mistakes this was written for, and it also
        resolves "unknown" -- which is not a harmless abstention, because the two consumers read it
        in contradictory ways: ``detect_obs._channel_of`` paints anything that is not "mine" into an
        ENEMY channel, while ``interactions`` drops it entirely. So the same unit is simultaneously
        an enemy to the observation canvas and nonexistent to the tower-pressure block, and the SIM
        the policy trains on has ground-truth teams and never produces the category at all.
        """
        if team != "enemy" and self.own_cards is not None and str(base) not in self.own_cards:
            return "enemy"
        return team

    def _verdict(self, d, trk) -> "tuple[str, int]":
        """Best (team, rank) for a linked det+track from the evidence available NOW (1 = strongest)."""
        net = trk["y"] - trk["y0"]
        if net <= -self.motion_min:
            return "mine", 2                        # marching UP, toward the enemy
        if net >= self.motion_min:
            return "enemy", 2                       # marching DOWN, toward me
        if trk["bm"] != trk["be"]:
            return ("mine" if trk["bm"] > trk["be"] else "enemy"), 3
        if d.base not in self.NO_SIDE_PRIOR:
            if trk["y0"] >= self.deep_mine_y and not self._in_lane(trk["x0"], self._pocket_my):
                return "mine", 4
            if trk["y0"] <= self.deep_enemy_y and not self._in_lane(trk["x0"], self._pocket_enemy):
                return "enemy", 4
        if d.body_vote:
            return d.body_vote, 5
        return "unknown", 9

    def tag(self, dets, t: float):
        """Fuse the evidence into ``d.team`` for every detection. Tracks BRIDGE detector misses: a unit
        not seen this read is carried for ``forget_s`` (position frozen) instead of being dropped, so one
        missed read doesn't reset a verdict (a Miner at the red enemy tower used to flip to 'enemy' that
        way). Linking is identity-aware (same base, nearest within ``track_radius``), which keeps a long
        memory from leaking a verdict onto a different unit answering it. Mutates + returns ``dets``."""
        self._plays = [p for p in self._plays                     # enemy-side plays (y<0.5) linger longer
                       if t - p[2] <= (self.enemy_window_s if p[1] < 0.5 else self.spawn_window_s)]
        prev = [tr for tr in self._tracks if t - tr["t"] <= self.forget_s]
        sr2, tr2 = self.spawn_radius ** 2, self.track_radius ** 2
        live = []
        for d in dets:
            dx, dy = d.cx, d.gy
            trk, best = None, tr2                                 # link: nearest UNUSED same-base track
            for cand in prev:
                d2 = (dx - cand["x"]) ** 2 + (dy - cand["y"]) ** 2
                if cand["base"] == d.base and d2 <= best:
                    trk, best = cand, d2
            if trk is not None:
                prev.remove(trk)
                trk["x"], trk["y"], trk["t"] = dx, dy, t
            else:
                trk = {"x": dx, "y": dy, "x0": dx, "y0": dy, "base": d.base, "t0": t,
                       "t": t, "team": "unknown", "rank": 9, "bm": 0, "be": 0}
            if d.bar_vote == "mine":
                trk["bm"] += 1
            elif d.bar_vote == "enemy":
                trk["be"] += 1
            # OWN-PLAY ANCHOR (rank 1): same base near a recent own play -> ground-truth 'mine'
            if trk["rank"] > 1 and any(
                    (pb is None or pb == d.base) and (dx - px) ** 2 + (dy - py) ** 2 <= sr2
                    for px, py, _, pb in self._plays):
                trk["team"], trk["rank"] = self._claim("mine", d.base), 1
            else:
                team, rank = self._verdict(d, trk)
                if rank <= trk["rank"]:                           # stronger/equal evidence -> (re)decide
                    trk["team"], trk["rank"] = self._claim(team, d.base), rank
            d.team = trk["team"]
            live.append(trk)
        # GAP BRIDGING: carry forward recent tracks NOT matched this read; they age out after forget_s.
        self._tracks = live + prev
        return dets

    def enemy_tracks(self, now: float, with_base: bool = False):
        """[(x, y, vx, vy)] for RECENT enemy tracks: current position + LIFETIME-average velocity
        (normalized/s, from the first-seen point -- smooth, jitter-proof, right for marching troops).
        Young tracks (<0.5s of history) report zero velocity; speeds are clamped to sane troop pace
        so a bad link jump can't produce a wild lead. Feeds the spell-intercept aim assist.

        ``with_base`` appends the track's CARD NAME, which an aim assist needs whenever the spell
        cannot hit everything: the Log rolls along the ground and must not be aimed at a Minion
        Horde it would pass straight under. Off by default so the existing callers are untouched.
        """
        out = []
        for tr in self._tracks:
            if tr["team"] != "enemy" or now - tr["t"] > self.forget_s:
                continue
            dt = tr["t"] - tr.get("t0", tr["t"])
            vx = vy = 0.0
            if dt >= 0.5:
                vx = max(-0.12, min(0.12, (tr["x"] - tr["x0"]) / dt))
                vy = max(-0.12, min(0.12, (tr["y"] - tr["y0"]) / dt))
            out.append((tr["x"], tr["y"], vx, vy, tr.get("base"))
                       if with_base else (tr["x"], tr["y"], vx, vy))
        return out


class BoardDetector:
    """Thin wrapper over an Ultralytics detector (YOLO/RT-DETR). ``available`` is False when no
    weights are found, so the miner can report readiness instead of crashing."""

    def __init__(self, model=None, names: Optional[Dict[int, str]] = None, db=None, fly_offset: float = 0.0,
                 conf_by_card: Optional[Dict[str, float]] = None, imgsz: int = 960,
                 arena_box: Optional[Sequence[float]] = None):
        self._model = model
        # PLAYFIELD GATE. The detector sees the WHOLE captured window, which includes the card tray
        # and the HUD, and it happily names the ART ON THE CARDS IN YOUR HAND. Those boxes then flow
        # into the board pipeline as if they were units standing on the grass -- and because the tray
        # sits at the bottom of the frame, the team tracker's "born deep in my half" prior tags them
        # MINE. MEASURED over the three recorded sessions at the live 10 Hz cadence: 50 of 3761
        # detections (1.3%) land outside the playfield, and they account for 39 of the 158 impossible
        # ally detections (25%) -- mother_witch_hog x22, barbarian_barrel x10, elixir_blob x9 (the
        # elixir bar itself). None of them is a unit. `None` keeps every box, for labelling/eval tools
        # that want the raw output.
        self._arena_box = tuple(float(v) for v in arena_box) if arena_box else None
        self._names = names or {}
        self._db = db                      # CardDB, for the flying-unit shadow correction (None -> skip)
        self._fly_offset = float(fly_offset)   # normalized DOWNWARD shift from a flyer's sprite to its shadow
        # PER-CLASS confidence gates (base card key -> gate). One global threshold assumes every class
        # is calibrated the same way, and measurement says they are not: on board-16 hog_rider sat at
        # precision 1.00 at the 0.40 gate (clearly over-gated -- it was throwing away correct boxes for
        # nothing) while tesla/x_bow gain no recall below 0.40 and only lose precision. Detection runs
        # at the LOWEST gate in play and each box is then judged against its own class's threshold, so
        # lowering one card costs nothing anywhere else. Empty = the single global gate, as before.
        self._conf_by_card = {str(k): float(v) for k, v in (conf_by_card or {}).items()}
        # Inference resolution. MUST match what the weights were trained at -- see detect().
        self._imgsz = int(imgsz)

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray, conf: float = 0.3) -> List[Detection]:
        if self._model is None:
            return []
        h, w = frame.shape[:2]
        floor = min([float(conf)] + list(self._conf_by_card.values())) if self._conf_by_card else float(conf)
        # PASS imgsz EXPLICITLY. ultralytics' predict() defaults to 640 regardless of what the model
        # was TRAINED at, and every board-* generation here trains at 960. This is the single choke
        # point every live path goes through (env.py, play.py, perception.py, label.py, detect_obs.py),
        # so the whole bot was reading the arena at two thirds of the resolution it was fitted for --
        # while `detect_eval` passed imgsz=960 explicitly, so NO measurement in this project ever saw
        # it. MEASURED on board-16 over the frozen 241-frame subset:
        #     imgsz 640  presence R 0.660   whitelist R 0.657   612 dets
        #     imgsz 960  presence R 0.709   whitelist R 0.730   656 dets
        # i.e. the live detector was giving up 7.3pp of whitelist recall for nothing -- and since the
        # obs-canvas flip gate is whitelist >= 0.70, the gate was being judged on a number the live
        # system never actually achieved (0.730 measured vs 0.657 delivered).
        res = self._model.predict(frame, conf=floor, imgsz=self._imgsz, verbose=False)[0]
        out: List[Detection] = []
        for b in res.boxes:
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
            bw, bh = (x2 - x1) / w, (y2 - y1) / h
            cls = self._names.get(int(b.cls[0]), str(int(b.cls[0])))
            base = card_threat.base_key(cls)
            if float(b.conf[0]) < self._conf_by_card.get(base, float(conf)):
                continue                   # below THIS class's gate (variants share the base's gate)
            # STATELESS colour evidence: the HP-bar scan (reliable, often absent) and the
            # overwhelming-body-art fallback. The preliminary team from these alone is what OFFLINE
            # single-frame consumers get; live paths run TeamTracker.tag() on top (motion/plays/pockets).
            c = self._db.get(base) if self._db is not None else None
            multi = bool(c and int(c.get("count") or 1) > 1)     # multi-unit card -> bars all through the box
            bar = _bar_vote(frame, cx, cy, bw, bh, multi=multi)
            body = _body_vote(frame, cx, cy, bw, bh)
            team = bar or body or "unknown"
            # FLYING-UNIT SHADOW CORRECTION: a flyer's sprite is drawn above the ground, so its box
            # centre is too high -- the real tile is at its shadow, ~fly_offset below. Shift cy down so
            # depth / movement prediction / spell targeting use the true ground position.
            gcy = None
            if self._fly_offset > 0 and self._db is not None and \
                    card_threat.profile(self._db, card_threat.base_key(cls)).flying:
                gcy = min(1.0, cy + self._fly_offset)
            # OFF THE PLAYFIELD = not a unit. Gated on the GROUND position (shadow-corrected), which
            # is the one that means "which tile is it standing on"; a flyer drawn high over the top
            # of the arena still belongs to the board.
            if self._arena_box is not None:
                ax0, ay0, ax1, ay1 = self._arena_box
                if not (ax0 <= cx <= ax1 and ay0 <= (cy if gcy is None else gcy) <= ay1):
                    continue
            out.append(Detection(cls, cx, cy, bw, bh, float(b.conf[0]), team, gcy, bar, body))
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
    try:                                # flyer shadow correction + multi-unit (bar-scan) counts
        from .cards import CardDB
        db = CardDB(cfg)
    except Exception:
        db = None
    return BoardDetector(model, {int(k): str(v) for k, v in names.items()}, db=db, fly_offset=fly_offset,
                         conf_by_card=cfg.get("observation", "detector_conf_by_card", default=None),
                         imgsz=int(cfg.get("detect", "imgsz", default=960)),
                         arena_box=cfg.get("env", "arena_region", default=None))


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
