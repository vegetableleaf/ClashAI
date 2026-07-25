"""Computer vision: state detection, elixir reading, hand ID, spell targeting."""
from __future__ import annotations

import glob
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .states import GameState


def _to_work(frame: np.ndarray, work_width: int) -> np.ndarray:
    """Scale a frame to a fixed working width (preserving aspect ratio)."""
    h, w = frame.shape[:2]
    if w == work_width:
        return frame
    scale = work_width / float(w)
    return cv2.resize(frame, (work_width, max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA)


@dataclass
class Match:
    found: bool
    score: float
    nx: float   # normalized center x of the best match
    ny: float   # normalized center y of the best match


class Vision:
    def __init__(self, cfg):
        self.cfg = cfg
        self.work_width = int(cfg.get("capture", "work_width", default=480))
        self.templates_dir = cfg.path("templates")
        self._templates: Dict[str, np.ndarray] = {}
        self._cards: Dict[str, np.ndarray] = {}
        self._load_templates()

    # ------------------------------------------------------------------
    def _load_templates(self) -> None:
        for p in glob.glob(str(self.templates_dir / "*.png")):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                self._templates[os.path.basename(p)] = img
        for p in glob.glob(str(self.templates_dir / "cards" / "*.png")):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                self._cards[os.path.splitext(os.path.basename(p))[0]] = img

    def work(self, frame: np.ndarray) -> np.ndarray:
        return _to_work(frame, self.work_width)

    # ------------------------------------------------------------------
    def find(self, frame: np.ndarray, template_name: Optional[str], threshold: float = 0.8) -> Match:
        tmpl = self._templates.get(template_name) if template_name else None
        if tmpl is None:
            return Match(False, 0.0, 0.0, 0.0)
        work = self.work(frame)
        if work.shape[0] < tmpl.shape[0] or work.shape[1] < tmpl.shape[1]:
            return Match(False, 0.0, 0.0, 0.0)
        res = cv2.matchTemplate(work, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        th, tw = tmpl.shape[:2]
        H, W = work.shape[:2]
        cx = (maxloc[0] + tw / 2.0) / W
        cy = (maxloc[1] + th / 2.0) / H
        return Match(maxv >= threshold, float(maxv), cx, cy)

    def detect_state(self, frame: np.ndarray) -> Tuple[GameState, float]:
        """Identify the current game state via template matching (priority order)."""
        checks = [
            (GameState.MATCH_END, "match_end"),
            (GameState.IN_MATCH, "in_match"),
            (GameState.PARTY, "party_menu"),
            (GameState.HOME, "home_menu"),
        ]
        for state, key in checks:
            spec = self.cfg.get("states", key, default=None)
            if not spec:
                continue
            threshold = spec.get("threshold", 0.8)
            # A state may list one `template` or several `templates`; match on any.
            names = spec.get("templates") or [spec.get("template")]
            for name in names:
                if not name:
                    continue
                m = self.find(frame, name, threshold)
                if m.found:
                    return state, m.score
        return GameState.UNKNOWN, 0.0

    # ------------------------------------------------------------------
    def read_elixir(self, frame: np.ndarray) -> int:
        """Estimate current elixir by counting 'filled' pips on the elixir bar."""
        work = self.work(frame)
        H, W = work.shape[:2]
        hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)
        lo = np.array(self.cfg.get("elixir", "filled_hsv_lower", default=[140, 60, 120]))
        hi = np.array(self.cfg.get("elixir", "filled_hsv_upper", default=[175, 255, 255]))
        bar_y = self.cfg.get("elixir", "bar_y", default=0.965)
        xs = self.cfg.get("elixir", "pip_xs", default=[])
        py = int(bar_y * H)
        count = 0
        for nx in xs:
            px = int(nx * W)
            patch = hsv[max(0, py - 3):py + 4, max(0, px - 3):px + 4]
            if patch.size == 0:
                continue
            mask = cv2.inRange(patch, lo, hi)
            if float(mask.mean()) > 60.0:  # majority of the patch is "filled"
                count += 1
        return min(count, 10)

    # ------------------------------------------------------------------
    def identify_hand(self, frame: np.ndarray) -> List[Optional[Tuple[str, int]]]:
        """Return (card_name, cost) for each of the 4 hand slots, or None if unknown."""
        work = self.work(frame)
        H, W = work.shape[:2]
        slots = self.cfg.get("hand", "slots", default=[])
        sw, sh = self.cfg.get("hand", "slot_size", default=[0.14, 0.09])
        thr = self.cfg.get("hand", "identify_threshold", default=0.6)
        costs = {c["name"]: c["cost"] for c in self.cfg.get("deck", "cards", default=[])}
        out: List[Optional[Tuple[str, int]]] = []
        for (nx, ny) in slots:
            if not self._cards:
                out.append(None)
                continue
            x0, x1 = int((nx - sw / 2) * W), int((nx + sw / 2) * W)
            y0, y1 = int((ny - sh / 2) * H), int((ny + sh / 2) * H)
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(W, x1), min(H, y1)
            crop = work[y0:y1, x0:x1]
            best_name, best_score = None, 0.0
            for name, timg in self._cards.items():
                t = timg
                if crop.shape[0] < t.shape[0] or crop.shape[1] < t.shape[1]:
                    t = cv2.resize(t, (min(crop.shape[1], t.shape[1]), min(crop.shape[0], t.shape[0])))
                if crop.shape[0] < t.shape[0] or crop.shape[1] < t.shape[1] or t.size == 0:
                    continue
                res = cv2.matchTemplate(crop, t, cv2.TM_CCOEFF_NORMED)
                _, mv, _, _ = cv2.minMaxLoc(res)
                if mv > best_score:
                    best_score, best_name = mv, name
            if best_name is not None and best_score >= thr:
                out.append((best_name, costs.get(best_name, 99)))
            else:
                out.append(None)
        return out

    # ------------------------------------------------------------------
    def tower_target(self) -> Tuple[float, float]:
        """Randomized normalized point on the enemy king tower (uniform in a disk)."""
        cx, cy = self.cfg.get("target", "tower_center", default=[0.5, 0.14])
        r = self.cfg.get("target", "jitter_radius", default=0.04)
        ang = random.uniform(0.0, 2.0 * math.pi)
        rad = r * math.sqrt(random.uniform(0.0, 1.0))
        return cx + rad * math.cos(ang), cy + rad * math.sin(ang)
