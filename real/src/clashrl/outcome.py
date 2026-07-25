"""Automatic 2v2 match-outcome detection from the results scoreboard.

No manual win/loss tracking needed. On the end-of-match scoreboard your team
(blue) is always shown on the BOTTOM and the enemy (red) on TOP. Each team has a
row of three crown "cushions" above its name banner; a gold crown on a cushion
means that team earned that crown. Whoever has more crowns wins.

Detection is robust to the results banners sliding in (their vertical position
varies during the animation) because it anchors to the banners themselves:

  1. locate the pink (enemy) and blue (your) name banners by colour — each is a
     near-full-width horizontal band, so a row-wise colour vote finds them;
  2. sample the three cushion cells just above each banner for gold-crown pixels;
  3. compare crown counts -> win / loss / draw.

`read_scoreboard` works on a single frame. `detect_session_outcomes` segments a
recorded session into matches and aggregates the reading across each match's
whole results window (so a mid-animation frame that misses a crown is covered by
a settled one), giving a reliable per-match win/loss record.

This is also the "results win/loss" reward signal the RL fine-tune step needs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# --- Defaults (overridable via the `outcome:` config section) -------------
# HSV ranges use OpenCV's convention: H in [0,179], S/V in [0,255].
_DEFAULTS = {
    "pink_hsv": [[150, 90, 90], [179, 255, 255]],     # enemy (red) name banner
    "blue_hsv": [[100, 120, 90], [120, 255, 255]],    # your (blue) name banner
    "gold_hsv": [[18, 120, 150], [35, 255, 255]],     # a claimed crown
    "cushion_xs": [0.25, 0.49, 0.72],   # normalized cushion centres
    "cushion_dx": 0.10,                  # half-width of a cushion cell
    "cushion_dy": 0.03,                  # half-height of the crown sample band
    # A crown sits above its banner, but the exact gap grows while the banner is
    # still sliding in, so scan several offsets and take the strongest per cell.
    "cushion_offsets": [0.06, 0.08, 0.10, 0.12, 0.14],
    "gold_frac": 0.10,                   # min gold fraction in a cell to count a crown
    "banner_min_frac": 0.45,             # a banner row must span at least this fraction of width
    "banner_min_gap": 0.15,              # min normalized gap between the two banners
    "red_y_range": [0.18, 0.52],         # plausible enemy-banner y band
    "blue_y_range": [0.50, 0.74],        # plausible your-banner y band
}


def _cfg(cfg, key):
    if cfg is None:
        return _DEFAULTS[key]
    return cfg.get("outcome", key, default=_DEFAULTS[key])


@dataclass
class Scoreboard:
    """Result of reading one frame (or an aggregated window)."""
    present: bool
    red_y: float = -1.0
    blue_y: float = -1.0
    red_crowns: int = 0
    blue_crowns: int = 0
    red_fracs: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    blue_fracs: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def outcome(self) -> Optional[str]:
        if not self.present:
            return None
        if self.blue_crowns > self.red_crowns:
            return "win"
        if self.red_crowns > self.blue_crowns:
            return "loss"
        return "draw"


def _band_row(hsv: np.ndarray, lo, hi) -> Tuple[float, float]:
    """Return (normalized y, width-fraction) of the strongest horizontal colour band."""
    mask = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    h, w = mask.shape[:2]
    frac = mask.sum(axis=1) / 255.0 / float(w)
    r = int(np.argmax(frac))
    return r / float(h), float(frac[r])


def _crown_fracs(hsv: np.ndarray, banner_y: float, cfg=None) -> Tuple[float, float, float]:
    """Gold-pixel fraction in each of the three cushion cells above a banner.

    Scans several vertical offsets above the banner (the crown-to-banner gap
    varies while the results banner is still sliding in) and keeps the strongest
    reading per cushion, so a mid-animation frame reads crowns as reliably as a
    settled one.
    """
    h, w = hsv.shape[:2]
    xs = _cfg(cfg, "cushion_xs")
    dx = float(_cfg(cfg, "cushion_dx"))
    dy = float(_cfg(cfg, "cushion_dy"))
    offsets = _cfg(cfg, "cushion_offsets")
    lo, hi = _cfg(cfg, "gold_hsv")
    gold = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    out = []
    for cx in xs:
        x0, x1 = int((cx - dx) * w), int((cx + dx) * w)
        best = 0.0
        for off in offsets:
            cy = banner_y - off
            y0, y1 = int((cy - dy) * h), int((cy + dy) * h)
            cell = gold[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
            if cell.size:
                best = max(best, float(cell.mean()) / 255.0)
        out.append(best)
    return tuple(out)  # type: ignore[return-value]


def locate_banners(hsv: np.ndarray, cfg=None):
    """Return (red_y, red_frac, blue_y, blue_frac) for the two name banners."""
    red_y, red_f = _band_row(hsv, *_cfg(cfg, "pink_hsv"))
    blue_y, blue_f = _band_row(hsv, *_cfg(cfg, "blue_hsv"))
    return red_y, red_f, blue_y, blue_f


def _banners_valid(red_y, red_f, blue_y, blue_f, cfg=None) -> bool:
    min_frac = float(_cfg(cfg, "banner_min_frac"))
    gap = float(_cfg(cfg, "banner_min_gap"))
    ry = _cfg(cfg, "red_y_range")
    by = _cfg(cfg, "blue_y_range")
    return (red_f >= min_frac and blue_f >= min_frac
            and (blue_y - red_y) >= gap
            and ry[0] <= red_y <= ry[1]
            and by[0] <= blue_y <= by[1])


def read_scoreboard(frame: np.ndarray, cfg=None) -> Scoreboard:
    """Read the results scoreboard from a single BGR frame."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red_y, red_f, blue_y, blue_f = locate_banners(hsv, cfg)
    if not _banners_valid(red_y, red_f, blue_y, blue_f, cfg):
        return Scoreboard(present=False)
    thr = float(_cfg(cfg, "gold_frac"))
    rf = _crown_fracs(hsv, red_y, cfg)
    bf = _crown_fracs(hsv, blue_y, cfg)
    return Scoreboard(
        present=True, red_y=red_y, blue_y=blue_y,
        red_crowns=sum(f >= thr for f in rf),
        blue_crowns=sum(f >= thr for f in bf),
        red_fracs=rf, blue_fracs=bf,
    )


def outcome_reward(outcome: Optional[str], cfg=None) -> float:
    """Map a detected outcome to the RL terminal reward (from rewards.* config)."""
    if outcome == "win":
        return float(cfg.get("rewards", "win", default=3.0)) if cfg else 3.0
    if outcome == "loss":
        return float(cfg.get("rewards", "loss", default=-3.0)) if cfg else -3.0
    return 0.0


# --- Session-level: segment matches and aggregate over each results window --

@dataclass
class MatchOutcome:
    index: int
    start_frame: int
    end_frame: int
    red_crowns: int
    blue_crowns: int
    outcome: str
    start_s: float = 0.0
    end_s: float = 0.0
    result_frames: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_s": round(self.start_s, 1),
            "end_s": round(self.end_s, 1),
            "red_crowns": self.red_crowns,
            "blue_crowns": self.blue_crowns,
            "outcome": self.outcome,
            "result_frames": self.result_frames,
        }


@dataclass
class _Agg:
    red: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    blue: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    n: int = 0


def detect_session_outcomes(cfg, session: Path, step: int = 18,
                            debug: bool = False) -> List[MatchOutcome]:
    """Segment a recorded session into matches and detect each one's win/loss.

    Samples the video ~1 Hz, uses the scripted state detector to find in-match
    runs, then for each match aggregates the crown reading across the whole
    post-match results window (max gold per cushion) for a robust verdict.
    """
    from .vision import Vision

    session = Path(session)
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    fps = float(meta.get("fps", 12))
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        return []
    vision = Vision(cfg)
    thr = float(_cfg(cfg, "gold_frac"))

    cap = cv2.VideoCapture(str(video))
    samples: List[Tuple[int, str, Scoreboard]] = []
    idx = 0
    while True:
        if not cap.grab():
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            state = vision.detect_state(frame).name
            sb = read_scoreboard(frame, cfg)
            samples.append((idx, state, sb))
        idx += 1
    cap.release()

    # match runs = maximal spans of IN_MATCH samples
    matches: List[Tuple[int, int]] = []  # (start_sample_i, end_sample_i)
    in_run = False
    run_start = 0
    for i, (_fi, state, _sb) in enumerate(samples):
        if state == "IN_MATCH" and not in_run:
            in_run, run_start = True, i
        elif state != "IN_MATCH" and in_run:
            in_run = False
            matches.append((run_start, i - 1))
    if in_run:
        matches.append((run_start, len(samples) - 1))

    results: List[MatchOutcome] = []
    for m, (s_i, e_i) in enumerate(matches):
        # results window = samples after the match ends, up to the next match start
        next_start = matches[m + 1][0] if m + 1 < len(matches) else len(samples)
        agg = _Agg()
        for j in range(e_i + 1, next_start):
            sb = samples[j][2]
            if sb.present:
                agg.red = [max(a, b) for a, b in zip(agg.red, sb.red_fracs)]
                agg.blue = [max(a, b) for a, b in zip(agg.blue, sb.blue_fracs)]
                agg.n += 1
        if agg.n == 0:
            continue  # no scoreboard seen (e.g. recording cut off) -> skip
        red_c = sum(f >= thr for f in agg.red)
        blue_c = sum(f >= thr for f in agg.blue)
        outcome = "win" if blue_c > red_c else "loss" if red_c > blue_c else "draw"
        start_fi, end_fi = samples[s_i][0], samples[e_i][0]
        if debug:
            print(f"[outcomes] match {m}: {agg.n} scoreboard frame(s)  "
                  f"red_gold={[round(x, 3) for x in agg.red]}  "
                  f"blue_gold={[round(x, 3) for x in agg.blue]}  (thr={thr})")
        results.append(MatchOutcome(
            index=m, start_frame=start_fi, end_frame=end_fi,
            red_crowns=red_c, blue_crowns=blue_c, outcome=outcome,
            start_s=start_fi / fps, end_s=end_fi / fps, result_frames=agg.n,
        ))
    return results


def outcomes_summary(outcomes: List[MatchOutcome]) -> str:
    w = sum(o.outcome == "win" for o in outcomes)
    l = sum(o.outcome == "loss" for o in outcomes)
    d = sum(o.outcome == "draw" for o in outcomes)
    return f"{len(outcomes)} matches: {w}W-{l}L" + (f"-{d}D" if d else "")


# --- CLI driver -----------------------------------------------------------

def _latest_session(root: Path) -> Optional[Path]:
    found = [p for p in root.glob("*") if (p / "meta.json").exists()]
    return max(found, key=lambda p: p.name) if found else None


def outcomes(cfg, session_arg: Optional[str] = None, do_all: bool = False,
             debug: bool = False) -> None:
    """Detect and report win/loss for one session or all of them.

    Writes each session's verdicts to `outcomes.json` and prints the record, so
    you never have to track wins/losses by hand.
    """
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if do_all:
        sessions = sorted(p for p in root.glob("*") if (p / "meta.json").exists())
    else:
        one = Path(session_arg) if session_arg else _latest_session(root)
        sessions = [one] if one else []
    if not sessions:
        print(f"[outcomes] no sessions under {root}")
        return

    grand_w = grand_l = grand_d = 0
    for session in sessions:
        res = detect_session_outcomes(cfg, Path(session), debug=debug)
        (Path(session) / "outcomes.json").write_text(
            json.dumps([o.to_dict() for o in res], indent=2), encoding="utf-8")
        print(f"[outcomes] {Path(session).name}: {outcomes_summary(res)}")
        for o in res:
            print(f"           match {o.index}  {o.start_s:6.1f}s  "
                  f"blue {o.blue_crowns} - {o.red_crowns} red  -> {o.outcome.upper()}")
        grand_w += sum(o.outcome == "win" for o in res)
        grand_l += sum(o.outcome == "loss" for o in res)
        grand_d += sum(o.outcome == "draw" for o in res)

    if len(sessions) > 1:
        total = grand_w + grand_l + grand_d
        wr = (grand_w / total * 100.0) if total else 0.0
        print(f"[outcomes] TOTAL across {len(sessions)} sessions: "
              f"{grand_w}W-{grand_l}L" + (f"-{grand_d}D" if grand_d else "")
              + f"  ({wr:.0f}% win rate)")
