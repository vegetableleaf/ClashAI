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
        # Threshold for the colour-blind (greyed-card) retry -- see match_card. Kept separate
        # because equalised luminance scores differently from a colour match.
        self.gray_threshold = float(cfg.get("hand", "gray_threshold", default=0.5))
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
    def observe(self, frame: np.ndarray) -> np.ndarray:
        """BGR frame -> HxWx3 uint8 observation at observation.arena_size (w, h)."""
        ow, oh = self.arena_size
        return cv2.resize(frame, (int(ow), int(oh)), interpolation=cv2.INTER_AREA)

    # ---- hand-card recognition ---------------------------------------
    def hand_crop(self, frame: np.ndarray, cx: float, cy: float) -> np.ndarray:
        """Crop the card portrait around a tray-slot centre (normalized cx, cy)."""
        h, w = frame.shape[:2]
        x0, x1 = int((cx - self.card_w) * w), int((cx + self.card_w) * w)
        y0, y1 = int((cy - self.card_h) * h), int((cy + self.card_h) * h)
        return frame[max(0, y0):y1, max(0, x0):x1]

    @staticmethod
    def _shape_only(img: np.ndarray) -> np.ndarray:
        """Grayscale + CLAHE: what the card looks like with its colour thrown away.

        Clash Royale DESATURATES a card you cannot currently afford, and the templates are
        cut from affordable (full-colour) cards, so a colour match on a greyed card scores far
        below threshold. Measured over 484 tray crops from session 20260808_152522: 286 were
        greyed (mean HSV saturation < 60) and 45 % of those were not recognised at all. The
        greying changes chroma, not structure, so matching on equalised luminance recovers
        them without touching the (already reliable) colour path.
        """
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(g)

    def _gray_tpl(self, tp: np.ndarray) -> np.ndarray:
        cache = self.__dict__.setdefault("_gray_cache", {})
        key = id(tp)
        hit = cache.get(key)
        if hit is None:
            hit = cache[key] = self._shape_only(tp)
        return hit

    def match_card(self, crop: np.ndarray, top_frac: float = 1.0, tpls: list = None) -> tuple:
        """(deck_index, score) of the best-matching deck card for a slot crop; (-1, s) if none.

        ``top_frac`` < 1 matches only the top fraction of the portrait against the top of each
        template -- used for the 'next' preview, whose bottom shows a "1sec" cycle timer and an
        elixir badge the card art doesn't have. ``tpls`` selects which template set to match
        against (default: the in-hand templates; the next preview passes its own set).

        Colour first; if nothing clears the threshold, the same comparison runs on equalised
        luminance, which is what rescues a greyed-out (unaffordable) card.
        """
        tpls = self._card_tpls if tpls is None else tpls
        if not crop.size:
            return -1, -1.0

        def scan(prep):
            bi, bs = -1, -1.0
            src = prep(crop) if prep else crop
            for i, tl in enumerate(tpls):
                for tp in tl:
                    t = self._gray_tpl(tp) if prep else tp
                    c = cv2.resize(src, (t.shape[1], t.shape[0]), interpolation=cv2.INTER_AREA)
                    tt = t
                    if top_frac < 1.0:
                        th = max(1, int(round(t.shape[0] * top_frac)))
                        c, tt = c[:th], t[:th]
                    s = float(cv2.matchTemplate(c, tt, cv2.TM_CCOEFF_NORMED).max())
                    if s > bs:
                        bi, bs = i, s
            return bi, bs

        best_i, best_s = scan(None)
        if best_s >= self.match_threshold:
            return best_i, best_s
        gi, gs = scan(self._shape_only)
        if gs >= self.gray_threshold:
            return gi, gs
        return -1, max(best_s, gs)

    # A tray slot whose card has just been played shows a flat blue placeholder with a crown
    # until the next card slides in. That is not an unrecognised card, it is NO card, and
    # reporting it as "?" made the hand read look far worse than it is: of 185 unmatched crops
    # in session 20260808_152522, 37 were this placeholder. Measured separation is total --
    # every placeholder is over 75 % Clash-blue, no real card art reaches it.
    _EMPTY_BLUE = ((100, 120, 60), (120, 255, 255))
    _EMPTY_MIN_FRAC = 0.75

    def slot_is_empty(self, crop: np.ndarray) -> bool:
        """True when this tray slot is the blue placeholder rather than a card."""
        if not crop.size:
            return False
        m = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), *self._EMPTY_BLUE)
        return float((m > 0).sum()) / (crop.shape[0] * crop.shape[1]) > self._EMPTY_MIN_FRAC

    def recognize_hand(self, frame: np.ndarray) -> list:
        """Identities of the 4 hand cards as deck indices (or -1 if unrecognized).

        Needs templates/cards/<deck_key>.png -- build them from a recording with
        `run.py hand-templates` and check with `run.py verify --hand`.
        """
        return [self.match_card(self.hand_crop(frame, cx, cy))[0] for cx, cy in self.hand_slots]

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
        return self.match_card(self.next_crop(frame), top_frac=self.next_top_frac,
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


