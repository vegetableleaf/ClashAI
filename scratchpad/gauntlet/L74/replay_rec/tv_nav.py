"""TV Royale navigation: screen classifier + a PURE decision function (no I/O here). L74 replay_rec.

Screens (900x1600 MuMu frames; templates from tv_templates.py in icebow/data/replay_rec/templates/):
  replay_controls  the replay viewer with its controls shown (rp_close / rp_pause); `speed` = x0.5 / x1 / x4 label
  tv_list / tv_channels / main / popup_x / loading / conn_lost / content_update / results  (tv_* need the capture
                   pass, see tv_templates.TV_SCREENS; main etc. come from ladder_nav.Classifier)
  unknown          anything else -- including the replay with its controls hidden (the READER says "in a replay")
Taps: only the allowlisted navigation targets below (`allowed`), never the Shop tab / profiles / deck copy. Any
screen the plan has no rule for -> wait, and after UNKNOWN_S -> STOP. Speed: tap the speed button until the label
reads x4 (cycle measured 10-08: x1 -> x0.5 ... x4; x2 not captured), then the reader's tick rate confirms it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
LIVE = HERE.parents[1] / "L68" / "live_reader"
sys.path.insert(0, str(LIVE))
TEMPLATES = HERE.parents[3] / "icebow" / "data" / "replay_rec" / "templates"

# Harvest order (lead 2026-10-08): top Ranked tiers first, then the highest arenas. Each needs a `tvch_<name>`
# template of its row in the channel list (capture pass). Names follow the Ranked leagues (June 2025 notes).
CHANNELS = ["ultimate_champion", "royal_champion", "grand_champion", "champion", "master_iii", "master_ii",
            "master_i", "arena_top"]
TARGETS = {                                   # fixed tap rectangles (900x1600), measured on the 10-08 captures
    "rp_close": (10, 635, 100, 725),          # the replay viewer's X (leaves the replay)
    "rp_speed": (10, 870, 100, 965),          # cycles the playback speed
    "rp_show": (430, 540, 470, 580),          # neutral arena point: shows the hidden replay controls
}
TAP_TEMPLATES = {"tv_entry", "tv_channel_btn", "tv_row_play", "rp_exit"} | {f"tvch_{c}" for c in CHANNELS}
FORBIDDEN = {"shop_tab": (0, 1440, 170, 1600)}
UNKNOWN_S = 20.0
SPEED_TAPS_MAX = 5
FAST_TICKS_PER_S = 60.0                       # 4x = ~80 game ticks / s (device 10-08: 73.1 incl. reader gaps)


def _inside(pt, r) -> bool:
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


class Classifier:
    def __init__(self, tdir: Path = TEMPLATES):
        man = json.loads((tdir / "manifest.json").read_text())["templates"]
        self.man = man
        self.t = {n: cv2.imread(str(tdir / e["file"])) for n, e in man.items()}
        from ladder_nav import Classifier as LadderC
        self.ladder = LadderC()

    def find(self, img, n):
        e, t = self.man[n], self.t[n]
        r = e["region"]
        _, s, _, loc = cv2.minMaxLoc(cv2.matchTemplate(img[r[1]:r[3], r[0]:r[2]], t, cv2.TM_CCOEFF_NORMED))
        return float(s), (r[0] + loc[0] + t.shape[1] / 2, r[1] + loc[1] + t.shape[0] / 2)

    def classify(self, img) -> dict:
        if img is None or img.shape[:2] != (1600, 900):
            return {"screen": "nograb", "scores": {}}
        sc, hit = {}, {}
        for n, e in self.man.items():
            s, c = self.find(img, n)
            sc[n] = round(s, 3)
            if s >= e["threshold"]:
                hit[n] = c
        if "rp_close" in hit or "rp_pause" in hit:
            speed = next((n[4:] for n in ("spd_x4", "spd_x1", "spd_x05") if n in hit), None)
            return {"screen": "replay_controls", "speed": speed, "hits": hit, "scores": sc}
        if "rp_exit" in hit:
            return {"screen": "replay_end", "hits": hit, "scores": sc}
        if "tv_channels_hdr" in hit:
            return {"screen": "tv_channels", "hits": hit, "scores": sc}
        if "tv_list_hdr" in hit:
            return {"screen": "tv_list", "hits": hit, "rows": self.rows(img), "scores": sc}
        r = self.ladder.classify(img)
        if r["screen"] == "main" and "tv_entry" in hit:
            r["hits"] = hit
        return {**r, "scores": {**r.get("scores", {}), **sc}}

    def rows(self, img) -> list:
        """Play buttons of replay rows that are NOT watched (watched rows turn grey: TV_Royale wiki), top first."""
        if "tv_row_play" not in self.man:
            return []
        e, t = self.man["tv_row_play"], self.t["tv_row_play"]
        r = e["region"]
        res = cv2.matchTemplate(img[r[1]:r[3], r[0]:r[2]], t, cv2.TM_CCOEFF_NORMED)
        out = []
        for y, x in zip(*((res >= e["threshold"]).nonzero())):
            c = (r[0] + x + t.shape[1] / 2, r[1] + y + t.shape[0] / 2)
            if any(abs(c[1] - o[1]) < t.shape[0] for o in out):
                continue
            patch = cv2.cvtColor(img[r[1] + y:r[1] + y + t.shape[0], r[0] + x:r[0] + x + t.shape[1]], cv2.COLOR_BGR2HSV)
            if float(patch[..., 1].mean()) > 60:          # saturated = not greyed out
                out.append(c)
        return sorted(out, key=lambda c: c[1])


def allowed(target: str, pt, man: dict | None = None) -> bool:
    """A tap is allowed only inside its target's rectangle (fixed TARGETS, or a tap template's search region)."""
    if any(_inside(pt, r) for r in FORBIDDEN.values()):
        return False
    if target in TARGETS:
        return _inside(pt, TARGETS[target])
    return target in TAP_TEMPLATES and man is not None and target in man and _inside(pt, man[target]["region"])


def missing_templates(man: dict) -> list[str]:
    need = ["tv_entry", "tv_list_hdr", "tv_channel_btn", "tv_channels_hdr", "tv_row_play", "rp_exit",
            "rp_close", "spd_x4"] + [f"tvch_{c}" for c in CHANNELS[:1]]
    return [n for n in need if n not in man]


def centre(r) -> tuple[int, int]:
    return round((r[0] + r[2]) / 2), round((r[1] + r[3]) / 2)


def decide(st: dict, scr: dict, reader: dict, now: float) -> tuple:
    """-> ("tap", target, (x, y)) | ("wait", why) | ("start_record",) | ("stop", why) | ("next_channel",) | ("done",).

    st (mutated): phase in to_tv / pick_channel / pick_replay / replay / exit, channel index, speed_taps, last_known.
    reader: {"in_replay": bool, "ended": reason or None, "ticks_per_s": float or None, "recording": bool}."""
    s = scr["screen"]
    if s in ("conn_lost", "content_update"):
        return ("stop", s)
    if s not in ("unknown", "nograb"):
        st["last_known"] = now
    elif now - st.setdefault("last_known", now) > UNKNOWN_S and not reader.get("in_replay"):
        return ("stop", "unknown_screen")
    ph = st.setdefault("phase", "to_tv")
    hits = scr.get("hits", {})
    if ph == "replay":
        if reader.get("ended"):
            st["phase"] = "exit"
            return ("wait", "replay_ended")
        if not reader.get("in_replay"):
            return ("wait", "replay_loading")
        if st.get("fast"):
            return ("wait", "recording")
        if (reader.get("ticks_per_s") or 0) >= FAST_TICKS_PER_S:
            st["fast"] = True
            return ("wait", "speed_confirmed")
        if s == "replay_controls":
            if scr.get("speed") == "x4":
                return ("wait", "speed_x4_label")          # the tick rate confirms on the next frames
            if st.get("speed_taps", 0) >= SPEED_TAPS_MAX:
                return ("wait", "speed_unconfirmed")       # recording at any speed is still valid data
            st["speed_taps"] = st.get("speed_taps", 0) + 1
            return ("tap", "rp_speed", centre(TARGETS["rp_speed"]))
        return ("tap", "rp_show", centre(TARGETS["rp_show"]))
    if ph == "exit":
        if s == "tv_list":
            st.update(phase="pick_replay", fast=False, speed_taps=0)
            return ("wait", "back_on_list")
        if "rp_exit" in hits:
            return ("tap", "rp_exit", hits["rp_exit"])
        if s == "replay_controls":
            return ("tap", "rp_close", centre(TARGETS["rp_close"]))
        return ("wait", "end_screen")
    if s == "popup_x":
        return ("wait", "popup")                           # never closed blind: a TV screen may carry a red X
    if s == "main":
        if "tv_entry" not in hits:
            return ("stop", "no_tv_entry_template")
        return ("tap", "tv_entry", hits["tv_entry"])
    if s == "tv_list":
        if ph in ("to_tv", "pick_channel"):
            st["phase"] = "pick_channel"
            if "tv_channel_btn" in hits:
                return ("tap", "tv_channel_btn", hits["tv_channel_btn"])
            return ("stop", "no_channel_button")
        rows = scr.get("rows") or []
        if not rows:
            st["phase"] = "pick_channel"
            st["channel"] = st.get("channel", 0) + 1
            return ("done",) if st["channel"] >= len(CHANNELS) else ("next_channel",)
        if not reader.get("recording"):
            return ("start_record",)                       # the recorder runs BEFORE the replay starts (tick 0)
        st.update(phase="replay", fast=False, speed_taps=0)
        return ("tap", "tv_row_play", rows[0])
    if s == "tv_channels":
        name = f"tvch_{CHANNELS[st.get('channel', 0)]}"
        if name in hits:
            st["phase"] = "pick_replay"
            return ("tap", name, hits[name])
        return ("stop", f"channel_not_found:{name}")
    return ("wait", s)
