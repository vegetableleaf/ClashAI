"""Tower HP chip-damage reward via a small digit-CNN OCR.

Each princess tower prints its remaining HP in white digits on its health bar.
This module reads those numbers and turns **partial** HP loss (chip damage that
doesn't destroy the tower) into a reward -- complementing the tower-destruction
latch (`reward.TowerTracker`) and the win/loss terminal reward. Chipping the
enemy princess is the whole point of a rocket-cycle deck, so it's the key signal.

Why it's reliable despite ~92% per-digit OCR: tower HP is piecewise-constant and
monotonically decreasing, so the tracker only accepts a new (lower) value once it
is read on N consecutive frames (**consensus**). Transient misreads differ
frame-to-frame and never reach consensus; the true value (stable across frames)
does. Net effect: near-zero false damage events, at the cost of occasionally
missing a hit during heavy occlusion (the destruction latch covers the kill).

The number crops are tight around each princess tower's HP so the white mask
picks up only the digits, not the tower structure/troops around them. They're
calibrated for the standard Princess Tower; a different **tower troop**
(Cannoneer / Dagger Duchess / Royal Chef) places its bar at a different height,
so its number would fall outside these boxes -- recalibrate the boxes (and, if
needed, re-collect crops and retrain) from a recording that has that tower type.

The CNN weights ship as ``hp_digits.npz`` next to this file. If torch or the
model is unavailable the tracker degrades to a no-op (0 reward), so RL still runs
on win/loss + destruction rewards alone.
"""
from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

_WEIGHTS = pathlib.Path(__file__).with_name("hp_digits.npz")
_DW, _DH = 16, 20                # per-digit crop size the CNN expects
_STRIP_W = 56                    # width the number strip is normalised to before slicing
_WHITE_LO, _WHITE_HI = (0, 0, 180), (179, 95, 255)   # HSV white-text mask

# Princess-tower HP-number crops as normalized (x0, y0, x1, y1), crown excluded.
_DEFAULT_ENEMY_BOXES = [[0.196, 0.160, 0.300, 0.193], [0.700, 0.160, 0.804, 0.193]]
_DEFAULT_MY_BOXES = [[0.203, 0.622, 0.307, 0.653], [0.703, 0.622, 0.807, 0.653]]


def _white_mask(bgr: np.ndarray) -> np.ndarray:
    return cv2.inRange(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), _WHITE_LO, _WHITE_HI)


def _digit_band(crop: np.ndarray, pad: int = 2) -> Optional[Tuple[int, int]]:
    """Row range spanning the HP digits inside a (possibly tall) box.

    Lets the box be tall enough to cover several tower types (whose HP bars sit at
    different heights) without the digits getting squished: the digits are bright,
    near-white and form the row with the most such pixels, so we lock onto the
    brightest row and grow a band while the white count stays high. A moderate white
    threshold keeps tan/blue tower structure out while still catching the blue-tinted
    HP digits on YOUR (blue-bar) towers. Returns (y0, y1) rows, or None.
    """
    strict = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (0, 0, 190), (179, 110, 255))
    rowsum = (strict > 0).sum(1).astype(float)
    if rowsum.max() < 6:
        return None
    peak = int(np.argmax(rowsum))
    thr = max(3.0, 0.35 * rowsum.max())
    top = peak
    while top > 0 and rowsum[top - 1] >= thr:
        top -= 1
    bot = peak
    while bot < len(rowsum) - 1 and rowsum[bot + 1] >= thr:
        bot += 1
    return max(0, top - pad), min(crop.shape[0], bot + pad + 1)



def _slice_digits(wm: np.ndarray, gray: np.ndarray, n: int) -> Optional[List[np.ndarray]]:
    """Split the number strip into ``n`` digit crops at the ``n-1`` deepest column valleys."""
    col = (wm > 0).sum(0).astype(float)
    cols = np.where(col > 0)[0]
    if len(cols) < n:
        return None
    c0, c1 = int(cols.min()), int(cols.max()) + 1
    ext = col[c0:c1]
    if c1 - c0 < 3 * n // 2:
        return None
    if n == 1:
        splits: List[int] = []
    else:
        min_sep = max(2, len(ext) // (n + 1))
        chosen: List[int] = []
        for i in np.argsort(ext):           # shallowest columns first = inter-digit gaps
            if all(abs(int(i) - c) >= min_sep for c in chosen):
                chosen.append(int(i))
            if len(chosen) == n - 1:
                break
        splits = sorted(chosen)
    bounds = [0] + splits + [len(ext)]
    out = []
    for i in range(n):
        a, b = c0 + bounds[i], c0 + bounds[i + 1]
        out.append(cv2.resize(gray[:, a:max(b, a + 1)], (_DW, _DH), interpolation=cv2.INTER_AREA))
    return out


class DigitReader:
    """Loads the digit CNN once and reads an HP number from a tower-number crop.

    Torch is imported lazily so importing this module never hard-requires it.
    ``ok`` is False when torch or the weights are missing -- callers should treat
    the reader as unavailable and skip HP shaping.
    """

    def __init__(self, weights: pathlib.Path = _WEIGHTS):
        self.ok = False
        self._torch = None
        self._net = None
        try:
            import torch
            import torch.nn as nn
        except Exception:
            return
        if not weights.exists():
            return
        dh, dw = _DH, _DW

        class DigitNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.f = nn.Sequential(
                    nn.Conv2d(1, 24, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                    nn.Conv2d(24, 48, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                    nn.Flatten(), nn.Linear(48 * (dh // 4) * (dw // 4), 96), nn.ReLU(),
                    nn.Linear(96, 10))

            def forward(self, x):
                return self.f(x)

        data = np.load(weights)
        net = DigitNet()
        net.load_state_dict({k: torch.tensor(data[k]) for k in net.state_dict()})
        net.eval()
        self._torch = torch
        self._net = net
        self.ok = True

    def read(self, crop: np.ndarray) -> Tuple[Optional[int], float]:
        """Return (hp_value, confidence) for a number crop, or (None, 0) if unreadable."""
        if not self.ok or crop.size == 0:
            return None, 0.0
        torch = self._torch
        band = _digit_band(crop)                 # tolerate a tall box: crop to the digit rows
        if band is not None:
            crop = crop[band[0]:band[1]]
        wm_full = _white_mask(crop)
        wm = cv2.resize(wm_full, (_STRIP_W, _DH), interpolation=cv2.INTER_AREA)
        gray = cv2.bitwise_and(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY),
                               cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), mask=wm_full)
        gray = cv2.resize(gray, (_STRIP_W, _DH), interpolation=cv2.INTER_AREA)
        cols = np.where(wm.sum(0) > 0)[0]
        if len(cols) < 8 or not (20 <= cols.max() - cols.min() <= 54):
            return None, 0.0
        best: Tuple[Optional[int], float] = (None, -1.0)
        for n in (4, 3):                     # princess HP is 3 or 4 digits; pick the confident split
            digs = _slice_digits(wm, gray, n)
            if digs is None:
                continue
            with torch.no_grad():
                batch = torch.tensor(np.array(digs, np.float32)[:, None] / 255.0)
                p = torch.softmax(self._net(batch), 1)
            conf = float(p.max(1).values.mean())
            val = int("".join(str(int(i)) for i in p.argmax(1).cpu().numpy()))
            if conf > best[1]:
                best = (val, conf)
        return best


def _boxes(cfg) -> Tuple[List[List[float]], List[List[float]]]:
    if cfg is None:
        return _DEFAULT_ENEMY_BOXES, _DEFAULT_MY_BOXES
    enemy = cfg.get("env", "enemy_tower_hp_boxes", default=_DEFAULT_ENEMY_BOXES)
    mine = cfg.get("env", "my_tower_hp_boxes", default=_DEFAULT_MY_BOXES)
    return enemy, mine


def _crop(frame: np.ndarray, box: List[float]) -> np.ndarray:
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    return frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def read_tower_hp(frame: np.ndarray, cfg=None, reader: Optional[DigitReader] = None) -> Dict[str, Tuple[Optional[int], float]]:
    """Read every princess-tower HP number in a frame -> {label: (hp, conf)} (for verify/debug)."""
    reader = reader or DigitReader()
    enemy, mine = _boxes(cfg)
    out: Dict[str, Tuple[Optional[int], float]] = {}
    for i, box in enumerate(enemy):
        out[f"E{i + 1}"] = reader.read(_crop(frame, box))
    for i, box in enumerate(mine):
        out[f"M{i + 1}"] = reader.read(_crop(frame, box))
    return out


class TowerHpTracker:
    """Consensus + monotonic HP tracker that emits the chip-damage reward.

    Reward per step = HP lost since the last confirmed value. Chipping an **enemy**
    princess is positive (a full tower's chip = ``rewards.hp_scale``). Losing HP on
    **your** princess is negative and GRADUAL: it accumulates to at most
    ``|rewards.lose_own_tower|`` per tower (the env tops it up to the full amount when the
    tower is destroyed), so chip damage on your tower costs PROPORTIONALLY instead of a
    flat hit only when it falls.
    """

    def __init__(self, cfg=None, reader: Optional[DigitReader] = None):
        self.cfg = cfg
        self.enabled = bool(cfg.get("env", "hp_reward", default=True)) if cfg else True
        self.full = float(cfg.get("env", "hp_full", default=3052.0)) if cfg else 3052.0
        # YOUR princess towers can be a different level than the enemy's, so they have a
        # different full HP; seed + normalise each side by its own full (defaults to hp_full).
        self.my_full = float(cfg.get("env", "my_hp_full", default=self.full)) if cfg else self.full
        self.consensus = int(cfg.get("env", "hp_consensus", default=2)) if cfg else 2
        self.min_conf = float(cfg.get("env", "hp_min_conf", default=0.55)) if cfg else 0.55
        self.max_chip = float(cfg.get("env", "hp_max_chip", default=1500.0)) if cfg else 1500.0
        self.scale = float(cfg.get("rewards", "hp_scale", default=1.0)) if cfg else 1.0
        # Defence penalty for YOUR princess HP loss is GRADUAL, accumulating to at most this
        # magnitude per tower (== |lose_own_tower|) and topped up to it on destruction -- so
        # chip damage costs proportionally rather than a flat hit only when the tower falls.
        self.lose_mag = abs(float(cfg.get("rewards", "lose_own_tower", default=-3.0))) if cfg else 3.0
        self.last_enemy_chip = 0.0     # + enemy-tower chip from the last step() (env rocket accounting)
        self.enemy_boxes, self.my_boxes = _boxes(cfg)
        self.reader = reader if reader is not None else (DigitReader() if self.enabled else None)
        if not (self.reader and self.reader.ok):
            self.enabled = False
        self.reset()

    def reset(self) -> None:
        # princess towers start at full HP -- seed there so a low first misread can't lock in
        self.enemy_hp = [self.full] * len(self.enemy_boxes)
        self.my_hp = [self.my_full] * len(self.my_boxes)
        self._enemy_cand: List[Tuple[Optional[int], int]] = [(None, 0)] * len(self.enemy_boxes)
        self._my_cand: List[Tuple[Optional[int], int]] = [(None, 0)] * len(self.my_boxes)
        self._my_applied = [0.0] * len(self.my_boxes)   # defence penalty already charged per my tower

    def _update_side(self, frame, boxes, hp, cand, full: float) -> float:
        """Enemy OFFENCE chip: + fraction of a tower's HP lost since the last confirmed read."""
        reward = 0.0
        for i, box in enumerate(boxes):
            val, conf = self.reader.read(_crop(frame, box))
            if val is None or conf < self.min_conf:
                continue
            cv, cc = cand[i]
            cand[i] = (val, cc + 1) if val == cv else (val, 1)
            if cand[i][1] < self.consensus:
                continue
            if val < hp[i] and (hp[i] - val) <= self.max_chip:
                reward += (hp[i] - val) / full
                hp[i] = val
        return reward

    def _update_my(self, frame) -> float:
        """DEFENCE: penalise YOUR princess HP loss GRADUALLY, accumulating to at most
        ``lose_mag`` per tower (absolute reward units, independent of hp_scale)."""
        reward = 0.0
        for i, box in enumerate(self.my_boxes):
            val, conf = self.reader.read(_crop(frame, box))
            if val is None or conf < self.min_conf:
                continue
            cv, cc = self._my_cand[i]
            self._my_cand[i] = (val, cc + 1) if val == cv else (val, 1)
            if self._my_cand[i][1] < self.consensus:
                continue
            if val < self.my_hp[i] and (self.my_hp[i] - val) <= self.max_chip:
                frac = (self.my_hp[i] - val) / self.my_full
                self.my_hp[i] = val
                pen = min(frac * self.lose_mag, max(0.0, self.lose_mag - self._my_applied[i]))
                self._my_applied[i] += pen
                reward -= pen
        return reward

    def on_my_tower_destroyed(self, i: int) -> float:
        """Top-up when YOUR princess tower ``i`` is latched destroyed: the part of the full
        -lose_mag that gradual chip hasn't already charged (covers a tower bursted faster than
        its HP could be read, or read while hp_reward is off). Returns a <= 0 reward."""
        if not (0 <= i < len(self._my_applied)):
            return 0.0
        rem = max(0.0, self.lose_mag - self._my_applied[i])
        self._my_applied[i] = self.lose_mag
        return -rem

    def step(self, frame: np.ndarray) -> float:
        """Chip-damage reward since the last step (0 if disabled): the enemy offence chip
        (scaled by hp_scale) minus YOUR gradual defence penalty (accumulating to lose_mag)."""
        self.last_enemy_chip = 0.0
        if not self.enabled:
            return 0.0
        e = self._update_side(frame, self.enemy_boxes, self.enemy_hp, self._enemy_cand, self.full) * self.scale
        self.last_enemy_chip = e                       # remember the offence chip for the env's rocket accounting
        return e + self._update_my(frame)
