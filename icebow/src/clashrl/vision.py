"""Vision for the learning bot.

Three jobs:
  - observe(): turn a captured BGR frame into the policy's observation (the
    downscaled arena image), matching how the labeler built the training data.
  - recognize_hand(): identify the 4 cards currently in the hand tray (by deck
    index) so the policy can act on card IDENTITY, not tray slot.
  - detect_state(): scripted-navigation screen detection via template matching
    (reused from trol, same templates), so the bot can queue/exit autonomously.

Reward detection (tower HP / crowns) is added with the RL fine-tune step.
"""
from __future__ import annotations

import glob
import os
import time

import cv2
import numpy as np

from .states import GameState


class Vision:
    def __init__(self, cfg):
        self.cfg = cfg
        self.arena_size = cfg.get("observation", "arena_size", default=[64, 96])
        self.work_width = int(cfg.get("capture", "work_width", default=480))
        self.templates_dir = cfg.path("templates")
        self._templates: dict = {}
        for p in glob.glob(str(self.templates_dir / "*.png")):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                self._templates[os.path.basename(p)] = img

        # --- hand-card recognition (identity-based actions) ---------------
        self.hand_slots = cfg.get("hand", "slots", default=[])
        self.card_w = float(cfg.get("hand", "card_w", default=0.055))
        self.card_h = float(cfg.get("hand", "card_h", default=0.045))
        self.match_threshold = float(cfg.get("hand", "match_threshold", default=0.5))
        # the "next card" preview sits left of the tray and is drawn smaller
        self.next_slot = cfg.get("hand", "next_slot", default=[])
        self.next_card_w = float(cfg.get("hand", "next_card_w", default=self.card_w * 0.72))
        self.next_card_h = float(cfg.get("hand", "next_card_h", default=self.card_h * 0.72))
        # match only the top fraction of the next-card crop (its bottom carries a "1sec" cycle
        # timer the saved templates don't have); 1.0 = whole crop
        self.next_top_frac = float(cfg.get("hand", "next_top_frac", default=1.0))
        cards_tpl = cfg.path(cfg.get("hand", "templates_dir", default="templates/cards"))
        self.next_templates_dir = cfg.path(cfg.get("hand", "next_templates_dir", default="templates/next"))
        try:
            from .cards import CardDB
            self.deck_keys = CardDB(cfg).deck_identities()
        except Exception:  # noqa: BLE001
            self.deck_keys = []
        # One template list per deck card. A card's templates are any file whose
        # stem is the deck key or the key followed by "_<suffix>" -- so multiple
        # appearances are supported: musketeer.png, musketeer_2.png, musketeer_evo.png,
        # ... all count as Musketeer. Longest-key match keeps keys that contain
        # underscores unambiguous (ice_wizard vs ice_spirit). The 'next' preview is a
        # smaller, blue-tinted rendering that does NOT match the in-hand crops, so it gets
        # its OWN template set under templates/next/ (built the same way, from that slot).
        self._card_tpls = self._load_templates(cards_tpl)
        self._next_tpls = self._load_templates(self.next_templates_dir)
        # HAND-READER SLOT CACHE (2026-08-13). recognize_hand's cost grows with the per-card
        # template variants (~20 x 10 identities x 4 slots ~= 800 small matchTemplates per call)
        # and MEASURED 1.28-1.78 s/call under a training-day CPU load -- the single largest term
        # in the live decision loop, bigger than the act period itself. A tray slot's pixels only
        # change when its card changes (play / cycle-in) or its affordability tint shifts, so each
        # slot caches a small grayscale thumb of its last crop + the matched id, and re-matches
        # ONLY when the thumb actually moved. Conservative by construction: ANY visible change
        # (selection glow, affordability tint, mid-slide animation) re-runs the full match for
        # that slot -- the cache can only skip work on a visually IDENTICAL slot, so accuracy is
        # unchanged by design. hand.cache_diff <= 0 disables it (the old always-match behaviour).
        self.cache_diff = float(cfg.get("hand", "cache_diff", default=3.5))
        self.cache_ttl = float(cfg.get("hand", "cache_ttl_s", default=4.0))   # max staleness; bounds ANY
        self._slot_cache: dict = {}     # slot index -> (thumb int16, matched id, cached-at time)
        self._next_cache = None         # (thumb, id, t) for the next-preview slot; same contract

    def _load_templates(self, tdir) -> list:
        """[per deck key] BGR templates whose filename stem is the key (or key_<suffix>)."""
        tpls = [[] for _ in self.deck_keys]
        by_len = sorted(range(len(self.deck_keys)), key=lambda i: len(self.deck_keys[i]), reverse=True)
        for p in sorted(glob.glob(str(tdir / "*.png"))):
            stem = os.path.splitext(os.path.basename(p))[0]
            for i in by_len:
                k = self.deck_keys[i]
                if stem == k or stem.startswith(k + "_"):
                    img = cv2.imread(p, cv2.IMREAD_COLOR)
                    if img is not None:
                        tpls[i].append(img)
                    break
        return tpls

    # ---- policy observation ------------------------------------------
    def set_board_warp(self, warp) -> None:
        """Install the tower-anchored BoardWarp so the RGB observation is BOARD-TRUE.

        Without it the whole frame (UI bars included) was resized into the canvas, so the board
        occupied ~60% of the image, squashed and shifted, while the SIM's RGB is a board-true
        render filling the canvas -- a permanent train/serve mismatch on the RGB channels and a
        driver of the live cell-head collapse (2026-08-14). The remap grid is cached per frame
        size; identity warps (the sim) short-circuit to the plain resize."""
        self._board_warp = warp
        self._warp_maps = None

    def observe(self, frame: np.ndarray) -> np.ndarray:
        """BGR frame -> HxWx3 uint8 observation at observation.arena_size (w, h). With a board
        warp installed, each output pixel samples the frame at the warped BOARD position, so the
        image is geometrically the same picture the sim renders."""
        ow, oh = self.arena_size
        warp = getattr(self, "_board_warp", None)
        if warp is None or not getattr(warp, "ok", False):
            return cv2.resize(frame, (int(ow), int(oh)), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]
        maps = getattr(self, "_warp_maps", None)
        if maps is None or maps[0].shape != (int(oh), int(ow)):
            xs = np.empty((int(oh), int(ow)), np.float32)
            ys = np.empty((int(oh), int(ow)), np.float32)
            for r in range(int(oh)):
                by = (r + 0.5) / oh
                for c in range(int(ow)):
                    fx, fy = warp.board_to_frame((c + 0.5) / ow, by)
                    xs[r, c] = fx * (w - 1)
                    ys[r, c] = fy * (h - 1)
            self._warp_maps = (xs, ys)
            maps = self._warp_maps
        return cv2.remap(frame, maps[0], maps[1], interpolation=cv2.INTER_AREA,
                         borderMode=cv2.BORDER_REPLICATE)

    # ---- hand-card recognition ---------------------------------------
    def hand_crop(self, frame: np.ndarray, cx: float, cy: float) -> np.ndarray:
        """Crop the card portrait around a tray-slot centre (normalized cx, cy)."""
        h, w = frame.shape[:2]
        x0, x1 = int((cx - self.card_w) * w), int((cx + self.card_w) * w)
        y0, y1 = int((cy - self.card_h) * h), int((cy + self.card_h) * h)
        return frame[max(0, y0):y1, max(0, x0):x1]

    def match_card(self, crop: np.ndarray, top_frac: float = 1.0, tpls: list = None) -> tuple:
        """(deck_index, score) of the best-matching deck card for a slot crop; (-1, s) if none.

        ``top_frac`` < 1 matches only the top fraction of the portrait against the top of each
        template -- used for the 'next' preview, whose bottom shows a "1sec" cycle timer and an
        elixir badge the card art doesn't have. ``tpls`` selects which template set to match
        against (default: the in-hand templates; the next preview passes its own set).
        """
        best_i, best_s = -1, -1.0
        tpls = self._card_tpls if tpls is None else tpls
        if crop.size:
            for i, tl in enumerate(tpls):
                for tp in tl:
                    c = cv2.resize(crop, (tp.shape[1], tp.shape[0]), interpolation=cv2.INTER_AREA)
                    t = tp
                    if top_frac < 1.0:
                        th = max(1, int(round(tp.shape[0] * top_frac)))
                        c, t = c[:th], tp[:th]
                    s = float(cv2.matchTemplate(c, t, cv2.TM_CCOEFF_NORMED).max())
                    if s > best_s:
                        best_i, best_s = i, s
        return (best_i if best_s >= self.match_threshold else -1), best_s

    @staticmethod
    def _thumb(crop: np.ndarray) -> np.ndarray:
        """Small COLOR fingerprint of a slot crop (change detector for the slot cache).
        Colour, not grayscale: card art can shift hue with little luminance change, and a
        grayscale thumb slept through exactly such flips in the equivalence test."""
        return cv2.resize(crop, (32, 24), interpolation=cv2.INTER_AREA).astype(np.int16)

    def recognize_hand(self, frame: np.ndarray) -> list:
        """Identities of the 4 hand cards as deck indices (or -1 if unrecognized).

        Needs templates/cards/<deck_key>.png -- build them from a recording with
        `run.py hand-templates` and check with `run.py verify --hand`.
        Slots whose pixels have not changed since the last call return their cached id
        (see the slot-cache note in __init__); a changed slot is fully re-matched.
        """
        out = []
        for si, (cx, cy) in enumerate(self.hand_slots):
            crop = self.hand_crop(frame, cx, cy)
            if not crop.size:
                out.append(-1)
                continue
            if self.cache_diff <= 0:
                out.append(self.match_card(crop)[0])
                continue
            now = time.time()
            th = self._thumb(crop)
            hit = self._slot_cache.get(si)
            if (hit is not None and hit[0].shape == th.shape
                    and now - hit[2] < self.cache_ttl
                    and float(np.abs(hit[0] - th).mean()) < self.cache_diff):
                out.append(hit[1])
                continue
            idx, score = self.match_card(crop)
            # Cache only CONFIDENT results, and only for cache_ttl seconds. A score hovering near
            # match_threshold flips between lookalikes on pixel noise (measured: one slot
            # oscillating across four identities on pre-update footage); caching one of those
            # noise samples would freeze it. Ambiguous slots therefore re-match on every call --
            # bit-identical to the uncached reader by determinism -- a clean -1 (no card) caches
            # safely, and the TTL bounds ANY residual staleness (slow drift the thumb undersees)
            # at a few seconds regardless.
            if idx < 0 or score >= self.match_threshold + 0.15:
                self._slot_cache[si] = (th, idx, now)
            else:
                self._slot_cache.pop(si, None)
            out.append(idx)
        return out

    def hand_multihot(self, hand_ids: list) -> np.ndarray:
        """[n_cards] float multi-hot of which deck cards are currently in hand."""
        v = np.zeros(max(1, len(self.deck_keys)), dtype=np.float32)
        for i in hand_ids:
            if 0 <= i < len(v):
                v[i] = 1.0
        return v

    def next_crop(self, frame: np.ndarray) -> np.ndarray:
        """Crop the next-card preview portrait (empty array if next_slot isn't configured)."""
        if not self.next_slot:
            return frame[0:0, 0:0]
        cx, cy = self.next_slot
        h, w = frame.shape[:2]
        x0, x1 = int((cx - self.next_card_w) * w), int((cx + self.next_card_w) * w)
        y0, y1 = int((cy - self.next_card_h) * h), int((cy + self.next_card_h) * h)
        return frame[max(0, y0):y1, max(0, x0):x1]

    def recognize_next(self, frame: np.ndarray) -> int:
        """Deck index of the card in the 'next' preview slot (left of the hand), or -1.

        The next card is what rotates into the tray once you play one; feeding it to the
        policy lets it plan cycles (e.g. hold a cheap card to line up the counter that's
        coming). The preview is a smaller, blue-tinted rendering that does NOT match the
        in-hand templates, so it needs its OWN set under templates/next/ -- build it with
        ``run.py hand-templates`` (it dumps next-preview candidates too) and calibrate
        ``hand.next_slot`` with ``run.py verify --hand``.
        """
        if not self.next_slot or not any(self._next_tpls):
            return -1
        crop = self.next_crop(frame)
        if not crop.size:
            return -1
        if self.cache_diff > 0:
            now = time.time()
            th = self._thumb(crop)
            hit = self._next_cache
            if (hit is not None and hit[0].shape == th.shape
                    and now - hit[2] < self.cache_ttl
                    and float(np.abs(hit[0] - th).mean()) < self.cache_diff):
                return hit[1]
            idx, score = self.match_card(crop, top_frac=self.next_top_frac, tpls=self._next_tpls)
            if idx < 0 or score >= self.match_threshold + 0.15:     # confident-only + TTL, as in recognize_hand
                self._next_cache = (th, idx, now)
            else:
                self._next_cache = None
            return idx
        return self.match_card(crop, top_frac=self.next_top_frac,
                               tpls=self._next_tpls)[0]

    def next_onehot(self, next_id: int) -> np.ndarray:
        """[n_cards] float one-hot of the next (preview) card; all-zero if unknown."""
        v = np.zeros(max(1, len(self.deck_keys)), dtype=np.float32)
        if 0 <= next_id < len(v):
            v[next_id] = 1.0
        return v

    # ---- scripted-navigation state detection -------------------------
    def _work(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w == self.work_width:
            return frame
        scale = self.work_width / float(w)
        return cv2.resize(frame, (self.work_width, max(1, int(round(h * scale)))),
                          interpolation=cv2.INTER_AREA)

    def _find(self, frame: np.ndarray, template_name, threshold: float, region=None) -> bool:
        tmpl = self._templates.get(template_name) if template_name else None
        if tmpl is None:
            return False
        work = self._work(frame)
        if region:                      # normalized [x0, y0, x1, y1] search window
            h, w = work.shape[:2]
            x0, y0, x1, y1 = region
            work = work[max(0, int(y0 * h)):min(h, int(round(y1 * h))),
                        max(0, int(x0 * w)):min(w, int(round(x1 * w)))]
        if work.shape[0] < tmpl.shape[0] or work.shape[1] < tmpl.shape[1]:
            return False
        res = cv2.matchTemplate(work, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, _ = cv2.minMaxLoc(res)
        return maxv >= threshold

    def detect_state(self, frame: np.ndarray) -> GameState:
        """Template state detection. A state's ``templates`` list may mix plain filenames
        (state-level threshold, whole-frame search) and dict entries with their OWN
        ``threshold``/``region`` -- used to keep a risky auxiliary template (the strict
        OVERTIME banner) isolated from the proven primary one."""
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
            thr_default = spec.get("threshold", 0.8)
            for entry in (spec.get("templates") or [spec.get("template")]):
                if isinstance(entry, dict):
                    name = entry.get("template")
                    thr = float(entry.get("threshold", thr_default))
                    region = entry.get("region")
                else:
                    name, thr, region = entry, thr_default, None
                if name and self._find(frame, name, thr, region):
                    return state
        return GameState.UNKNOWN

    def locate(self, frame: np.ndarray, template_name, threshold: float):
        """Normalized (cx, cy) centre of the best match of a template, or None if it
        doesn't clear ``threshold``. Lets navigation tap a button *where it actually is*
        (robust to it shifting with a seasonal layout) instead of a fixed coordinate."""
        tmpl = self._templates.get(template_name) if template_name else None
        if tmpl is None:
            return None
        work = self._work(frame)
        if work.shape[0] < tmpl.shape[0] or work.shape[1] < tmpl.shape[1]:
            return None
        res = cv2.matchTemplate(work, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, ml = cv2.minMaxLoc(res)
        if maxv < threshold:
            return None
        cx = (ml[0] + tmpl.shape[1] / 2.0) / work.shape[1]
        cy = (ml[1] + tmpl.shape[0] / 2.0) / work.shape[0]
        return cx, cy


    def match_end_is_dc(self, frame: np.ndarray) -> bool:
        """True if the teammate-disconnected results screen is showing (button choice)."""
        spec = self.cfg.get("states", "match_end", default={}) or {}
        threshold = spec.get("threshold", 0.8)
        names = spec.get("templates") or [spec.get("template")]
        return any(name and "_dc" in name and self._find(frame, name, threshold) for name in names)

    # ---- elixir reading (your bar; ported from trol) ------------------
    def read_elixir(self, frame: np.ndarray) -> int:
        """Estimate your current elixir (0-10) by counting filled pips on the bar.

        Only YOUR elixir is on screen; the opponent's is hidden (that's why a true
        elixir-trade needs identifying the cards they play). Coordinates/HSV come
        from the `elixir` config, reused from the trol calibration.
        """
        work = self._work(frame)
        h, w = work.shape[:2]
        hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)
        lo = np.array(self.cfg.get("elixir", "filled_hsv_lower", default=[140, 60, 120]))
        hi = np.array(self.cfg.get("elixir", "filled_hsv_upper", default=[175, 255, 255]))
        bar_y = float(self.cfg.get("elixir", "bar_y", default=0.965))
        xs = self.cfg.get("elixir", "pip_xs", default=[])
        py = int(bar_y * h)
        count = 0
        for nx in xs:
            px = int(nx * w)
            patch = hsv[max(0, py - 3):py + 4, max(0, px - 3):px + 4]
            if patch.size == 0:
                continue
            if float(cv2.inRange(patch, lo, hi).mean()) > 60.0:
                count += 1
        return min(count, 10)


