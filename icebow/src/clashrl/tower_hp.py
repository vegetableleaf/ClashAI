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
from typing import Any, Dict, List, Optional, Tuple

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


# --- alive / destroyed, and the king -------------------------------------------------
# A princess tower's HP number disappears for TWO different reasons and they mean opposite
# things: something is briefly covering it (the value is unknown, keep the last one) or the
# tower is GONE (the value is 0 forever). The bar itself tells them apart -- it is a solid
# block of the team's colour and it vanishes with the tower. Measured on a live frame:
# enemy boxes 6.4% pink / 0.0% blue, own boxes 7-12% blue / 0.0% pink, so a 2% floor
# separates them with a wide margin.
_BAR_MIN_COVER = 0.02
_PINK = ((150, 110, 110), (180, 255, 255))      # enemy bar; red wraps, so a second range below
_PINK2 = ((0, 110, 110), (8, 255, 255))
_BLUE = ((92, 110, 110), (118, 255, 255))       # your bar


def _widen(box: List[float], fx: float = 0.6, fy: float = 0.4) -> List[float]:
    """The digit box grown to take in the bar around it (the digit box is deliberately tight)."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    hw, hh = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
    return [cx - hw * (1 + fx), cy - hh * (1 + fy), cx + hw * (1 + fx), cy + hh * (1 + fy)]


def _team_mask(bgr: np.ndarray, mine: bool) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if mine:
        return cv2.inRange(hsv, *_BLUE)
    return cv2.bitwise_or(cv2.inRange(hsv, *_PINK), cv2.inRange(hsv, *_PINK2))


# How far to hunt for a bar that is not where the config says, as a share of frame height.
# A Windows title bar is ~30px on a 1200px-tall client, i.e. ~2.5%; 6% covers that with room
# and still cannot reach the opposite tower's bar (they are ~50% of the height apart).
_SNAP_DY = 0.06
_SNAP_MIN_ROWS = 3          # a bar is a RUN of coloured rows, not one stray line of pixels


# A real HP bar spans nearly the whole width of its own box; RED TEXT does not. Without this,
# the search found the opponent's name (drawn in red) above the left tower and reported a
# healthy-looking 95% "bar" for a tower whose actual bar it never reached -- seen on the
# 657x1198 frames, where E2 snapped correctly and E1 landed on "parejaexplosiva".
_SNAP_MIN_COLS = 0.55


def _bars(frame: np.ndarray, mine: bool) -> List[Tuple[float, float]]:
    """Centres of everything in the frame SHAPED like an HP bar, as (x, y) fractions.

    Shape is what separates a bar from the other red things on screen. A princess bar is a wide,
    flat, solidly filled rectangle; the opponent's NAME is red text of similar width but broken
    into letters, and the card tray is blue but far too tall. Measured on a 657x1198 frame, this
    returns exactly the two enemy bars and nothing else, where a colour-only search down the
    expected column returned only the player's name.
    """
    h, w = frame.shape[:2]
    m = (_team_mask(frame, mine) > 0).astype(np.uint8)
    n, _lab, stats, _cent = cv2.connectedComponentsWithStats(m, 8)
    out: List[Tuple[float, float]] = []
    min_w = max(20, int(0.05 * w))                 # a bar spans a real part of the width
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if bw < min_w or not (3 <= bh <= max(6, 0.035 * h)):
            continue
        if bw / max(bh, 1) < 3.0:                  # wide and FLAT
            continue
        if area < bw * bh * 0.4:                   # solid, not a row of letters
            continue
        out.append(((x + bw / 2) / w, (y + bh / 2) / h))
    return out


# How far a bar may sit from where config.yaml says before we refuse to believe it is the same
# tower. The two princess towers are ~0.5 of the width apart, so 0.15 cannot cross between them.
_MATCH_R = 0.15


def frame_offset(frame: np.ndarray, cfg=None) -> Tuple[float, float]:
    """ONE (dx, dy) correction for the whole frame, in frame fractions.

    The boxes in config.yaml are fractions of the WHOLE frame, which survives a change of
    resolution and does not survive a change of what is in the frame. A client captured with its
    window title bar, or with different padding around the arena, puts every bar somewhere else;
    the fractions then point at empty board, `bar_fraction` returns None, and a healthy tower is
    reported DESTROYED -- the worst possible failure, because "destroyed" is exactly what the
    policy must never get wrong.

    Measured on a 657x1198 frame: the enemy bars sit at y 0.164-0.177 while config points at
    0.091-0.156, and at x 0.199-0.314 while config points at 0.096-0.295. So it is NOT only a
    vertical shift -- an earlier vertical-only version of this failed for that reason, and a
    per-box hunt failed differently by latching onto the opponent's red name. Both were measured
    before being replaced.

    Estimated once per frame and shared by every box, because the cause is the capture geometry,
    which cannot differ between two towers in the same picture. Returns (0.0, 0.0) when nothing
    matches, i.e. when the geometry is already right or the towers really are gone.
    """
    enemy, mine_boxes = _boxes(cfg)
    dxs: List[float] = []
    dys: List[float] = []
    for boxes, is_mine in ((enemy, False), (mine_boxes, True)):
        found = _bars(frame, is_mine)
        if not found:
            continue
        for box in boxes:
            wide = _widen(box)
            cx, cy = (wide[0] + wide[2]) / 2, (wide[1] + wide[3]) / 2
            near = [(abs(fx - cx) + abs(fy - cy), fx, fy) for fx, fy in found]
            near.sort()
            d, fx, fy = near[0]
            if d > _MATCH_R:
                continue
            dxs.append(fx - cx)
            dys.append(fy - cy)
    if not dxs:
        return 0.0, 0.0
    # median: one mismatched tower cannot drag the estimate
    dxs.sort(); dys.sort()
    mid = len(dxs) // 2
    dx = dxs[mid] if len(dxs) % 2 else (dxs[mid - 1] + dxs[mid]) / 2
    dy = dys[mid] if len(dys) % 2 else (dys[mid - 1] + dys[mid]) / 2
    h, w = frame.shape[:2]
    if abs(dx) < 1.0 / w and abs(dy) < 1.0 / h:
        return 0.0, 0.0
    return dx, dy


def bar_cover(frame: np.ndarray, box: List[float], mine: bool, widen: bool = True) -> float:
    """Share of the box painted in that team's HP-bar colour. ~0 = no bar there = destroyed.

    ``widen`` grows the tight DIGIT box to take in the bar around it; pass False for a region
    that already spans the bar (the king band), where growing it would reach the player name
    and the match timer.
    """
    c = _crop(frame, _widen(box) if widen else box)
    if c.size == 0:
        return 0.0
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    if mine:
        mask = cv2.inRange(hsv, *_BLUE)
    else:
        mask = cv2.bitwise_or(cv2.inRange(hsv, *_PINK), cv2.inRange(hsv, *_PINK2))
    return float((mask > 0).sum()) / max(1, c.shape[0] * c.shape[1])


# The KING tower's number is only drawn once the king is activated (or damaged), so it is
# absent most of the match -- absent means FULL, not unknown, and definitely not zero. Its
# bar also sits at a different height per client, so instead of a hand-calibrated box this
# SEARCHES a generous central band for the digit strip. The band deliberately excludes the
# left (player name) and right (match timer) thirds, which are the only other white text up
# there and would otherwise be read as an HP value.
_KING_BANDS = {"enemy": [0.40, 0.000, 0.66, 0.060], "mine": [0.40, 0.700, 0.66, 0.760]}


# The king's NUMBER is drawn in a different style from the princesses' -- bigger, outlined,
# pink-tinted -- and the digit CNN (trained on princess crops) misreads it: on a frame that
# plainly shows 1376 it returns 7976 / 1628 / 312 depending on the crop, across every white-
# mask threshold tried. So the number is not the signal here; the BAR is. Its filled share is
# a direct, OCR-free reading of remaining HP and needs no per-glyph training at all.
_KING_BARS = {"enemy": [0.444, 0.019, 0.601, 0.032], "mine": [0.444, 0.716, 0.601, 0.729]}


def bar_fraction(frame: np.ndarray, band: List[float], mine: bool) -> Optional[float]:
    """Filled share (0..1) of an HP bar, by column. None when there is no bar there.

    A column counts as filled if any pixel in it carries the team's colour; the empty part of
    the bar is dark brown and the frame is a gold outline, so the split is unambiguous.
    """
    c = _crop(frame, band)
    if c.size == 0 or c.shape[1] < 8:
        return None
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    if mine:
        fill = cv2.inRange(hsv, *_BLUE)
    else:
        fill = cv2.bitwise_or(cv2.inRange(hsv, *_PINK), cv2.inRange(hsv, *_PINK2))
    # Anchor on the FILLED part: a bar that is drawn always has some of it (an empty one means
    # the tower is gone and the match is over). Any-dark-pixel is not an anchor -- grass shadow
    # is dark too, which made a bar-less frame look like a bar at 0 %.
    rows = (fill > 0).sum(1) > c.shape[1] * 0.10
    if not rows.any():
        return None                                   # no bar drawn -> king not activated yet
    strip = slice(int(np.argmax(rows)), int(len(rows) - np.argmax(rows[::-1])))
    f = (fill[strip] > 0).sum(0) > 0
    # the empty remainder is the bar's dark brown, not shadow: bounded hue and mid-low value
    empty = cv2.inRange(hsv[strip], (5, 60, 25), (30, 255, 110))
    e = (empty > 0).sum(0) > 0
    lo = int(np.argmax(f))
    hi = int(len(f) - np.argmax((f | e)[::-1]))        # bar ends where neither fill nor empty
    if hi - lo < 8:
        return None
    return float(f[lo:hi].sum()) / float(hi - lo)


def read_king_hp(frame: np.ndarray, cfg=None, reader: Optional["DigitReader"] = None
                 ) -> Dict[str, Tuple[Optional[int], float]]:
    """{'K_enemy': (hp, conf), 'K_mine': (hp, conf)} -- (None, 0.0) when no number is shown."""
    reader = reader or DigitReader()
    out: Dict[str, Tuple[Optional[int], float]] = {}
    for side in ("enemy", "mine"):
        key = "enemy_king_hp_band" if side == "enemy" else "my_king_hp_band"
        band = (cfg.get("env", key, default=_KING_BANDS[side]) if cfg else _KING_BANDS[side])
        crop = _crop(frame, band)
        # Two gates, because white text alone is not an HP bar: the band must actually
        # CONTAIN a bar in the team's colour, and the read must be confident. Without the
        # colour gate this fired on 5 of 121 bar-less frames with values like 6311.
        if crop.size == 0 or bar_cover(frame, band, mine=(side == "mine"), widen=False) < _BAR_MIN_COVER:
            out[f"K_{side}"] = (None, 0.0)
            continue
        hp, conf = reader.read(crop)
        out[f"K_{side}"] = (hp, conf) if (hp is not None and conf >= 0.60) else (None, 0.0)
    return out


def read_towers(frame: np.ndarray, cfg=None, reader: Optional["DigitReader"] = None
                ) -> List[Dict[str, Any]]:
    """All six towers as {name, side, hp, fill, state, box, bar}, for display and diagnosis.

    Two independent readings per tower, which is the point: the NUMBER (digit CNN, exact but
    it fails whenever a unit or a spell covers the text) and the BAR FILL (a colour ratio,
    always available while the bar is drawn, and the only reading the king has at all).

    ``state`` is the thing the old code could not express. A missing number used to be a bare
    "?", which conflated two opposite situations -- measured on session 20260808_152522, the
    enemy right princess reads nothing from frame 724 on, because it is DESTROYED (0 forever),
    while the enemy left princess reads nothing at frame 934 with its bar at 61 %, because a
    unit is standing in front of the digits. Absence of the BAR, not of the number, is what
    separates them.
    """
    reader = reader or DigitReader()
    enemy, mine = _boxes(cfg)
    out: List[Dict[str, Any]] = []
    spec = [(f"E{i+1}", b, False, f"opponent princess {i+1}") for i, b in enumerate(enemy)]
    spec += [(f"M{i+1}", b, True, f"your princess {i+1}") for i, b in enumerate(mine)]

    # Does this frame's geometry match the config at all? Ask ONCE, from the whole frame, before
    # reading anything -- a per-box hunt lets a box with no bar in reach latch onto unrelated red.
    dx = dy = 0.0
    if any(bar_fraction(frame, _widen(b), m) is None for b, m in
           [(b, False) for b in enemy] + [(b, True) for b in mine]):
        dx, dy = frame_offset(frame, cfg)

    for name, box, is_mine, label in spec:
        snapped = 0.0
        bar = _widen(box)
        fill = bar_fraction(frame, bar, is_mine)
        if fill is None and (dx or dy):
            # Nothing at the configured spot AND the frame's geometry is shifted: try the shifted
            # spot before calling a tower destroyed. A tower that is genuinely gone has no bar
            # EITHER WAY, so this cannot resurrect one.
            box2 = [box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy]
            bar2 = _widen(box2)
            fill2 = bar_fraction(frame, bar2, is_mine)
            if fill2 is not None:
                box, bar, fill = box2, bar2, fill2
                snapped = max(abs(dx), abs(dy))
        hp, conf = reader.read(_crop(frame, box))
        if fill is None:
            state, hp, conf = "destroyed", 0, 1.0
        elif hp is None:
            state = "covered"
        else:
            state = "alive"
        out.append({"name": name, "label": label, "side": "enemy" if not is_mine else "mine",
                    "hp": hp, "conf": round(float(conf), 3), "fill": fill,
                    "state": state, "box": box, "bar": bar, "kind": "princess",
                    # non-zero = this frame's geometry differs from config.yaml's and the box was
                    # moved to find the bar. Surfaced so a systematic offset is visible rather
                    # than silently compensated forever.
                    "snapped": round(snapped, 4) if snapped else 0.0})
    for side, is_mine, label in (("enemy", False, "opponent king"), ("mine", True, "your king")):
        key = "enemy_king_bar" if not is_mine else "my_king_bar"
        band = (cfg.get("env", key, default=_KING_BARS[side]) if cfg else _KING_BARS[side])
        fill = bar_fraction(frame, band, is_mine)
        # The king's number is NOT read: the digit CNN misreads that glyph style (see above).
        out.append({"name": f"K_{side}", "label": label, "side": side, "hp": None, "conf": None,
                    "fill": fill, "state": ("no_bar" if fill is None else
                                            ("destroyed" if fill <= 0.001 else "alive")),
                    "box": None, "bar": band, "kind": "king"})
    return out


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
        self.last_enemy_frac = 0.0     # raw enemy-tower HP fraction removed last step() (rocket damage)
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
        self.last_enemy_frac = 0.0
        if not self.enabled:
            return 0.0
        ef = self._update_side(frame, self.enemy_boxes, self.enemy_hp, self._enemy_cand, self.full)
        self.last_enemy_frac = ef                      # raw enemy-tower HP fraction removed this step
        self.last_enemy_chip = ef * self.scale         # ...as a reward (for the env's rocket accounting)
        return self.last_enemy_chip + self._update_my(frame)
