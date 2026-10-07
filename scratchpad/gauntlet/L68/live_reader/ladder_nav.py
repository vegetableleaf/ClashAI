"""Between-match navigation for live_play.py --ladder: re-queue Trophy Road (ladder) matches, and open the daily-win
chests after the day's 4th win (owner 2026-10-02).

Screens (template matching on `adb exec-out screencap` frames vs scratchpad/gauntlet/L70/ladder_nav/templates):
  results  "Play Again" + "OK" buttons; who won = the y of the "WINNER!" banner (top half = opponent).
  main     the yellow Battle button. "Daily Bonus" under it = the game still pays a daily-win bonus today.
  popup_x  any popup with the red X close button (promos like "Upgrade your Pass Royale" -- never its GO! button).
  modes    the Game Modes sheet (opened by a stray tap) -> its close arrow.
  trophy_road  the Trophy Road rewards screen the game opens at a milestone: Collect (free reward), then its OK.
           A green "Choose" button (a pick-one-of-two card reward, owner 2026-10-07) is tapped too -> choose_reward.
  choose_reward  "Choose your reward": two card tiles side by side -> tap ONE at random (seeded, logged). From the
           Choose tap until the next known screen, an unrecognised screen is never tapped through: after
           FLOW_UNKNOWN_S the run STOPs with a TROPHY_ROAD_ALERT and a Discord alert carrying the screenshot.
           Both are colour/shape features in RELATIVE coordinates (built from the owner's phone screenshots, a
           different resolution than MuMu): see reward_cards() / green_buttons() / blue_ok().
  conn_lost  "Connection lost" dialog: "Another device is connecting" -> STOP the run (never kick the owner's phone);
           any other connection loss -> RELOAD.
  loading  the Clash Royale logo screen (app start / battle loading).
Policy: after a results screen tap Play Again, EXCEPT after the day's 4th win (counted here, persisted in
ladder_state.json): tap OK, tap through the chest-opening screens until the main screen is stable, tap Battle. The
win count is re-synced from the main screen whenever we are on it: no "Daily Bonus" -> 4 done; "Daily Bonus" back
after 4 -> the game's day rolled over -> 0. While the day's bonus is used up, every PROBE_S one results screen goes
via OK -> main (instead of Play Again) only to look for that rollover.
Inputs: only the allowlisted TARGETS below, built by command_for(); never the Shop tab. Unknown screens are tapped
through at one fixed neutral point (reward / chest screens are "tap to continue"), at most TAP_MAX times a transition.

    # watch and log the taps it WOULD make (never taps); navigate by hand:
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/live_play.py --ladder --nav-dry-run
"""
from __future__ import annotations

import json
import random
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parents[1] / "L70" / "ladder_nav" / "templates"
STATE = HERE / "ladder_state.json"
DAILY_WINS = 4

TARGETS = {                                     # rectangle the tap point must lie in (900x1600 frame)
    "play_again": (180, 1390, 440, 1515),
    "results_ok": (460, 1390, 720, 1515),
    "battle": (300, 1150, 610, 1340),
    "close_x": (560, 60, 900, 600),
    "modes_close": (380, 200, 520, 290),
    "tap_through": (440, 440, 460, 460),
    "collect": (0, 150, 900, 1480),             # Trophy Road: claim a free reward (green Collect)
    "bottom_ok": (340, 1490, 560, 1595),        # Trophy Road: close (blue OK in the bottom bar)
    "choose": (0, 150, 900, 1480),              # Trophy Road: green Choose (a pick-one-of-two card reward)
    "reward_card": (0, 60, 900, 1100),          # "Choose your reward": one of the two card tiles
    "reload": (100, 700, 400, 1100),            # "Connection lost" dialog, NOT the another-device kind        # neutral point: top-centre art on every popup seen so far
}
FORBIDDEN = {"shop_tab": (0, 1440, 170, 1600)}
SWIPES = {"tr_scroll": (450, 1150, 450, 550, 700)}   # Trophy Road: slow drag up = show LOWER (already reached) rewards
TAP_THROUGH_PT = (450, 450)
ALERT = "TROPHY_ROAD_ALERT"                     # stop-reason prefix: the runner posts the screenshot to Discord
WEBHOOK = HERE.parents[3] / "icebow" / "data" / "discord_webhook.txt"   # git-ignored secret: never printed


class NavViolation(RuntimeError):
    pass


def _inside(pt, r) -> bool:
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


def command_for(target: str, pt) -> str:
    """The ONLY builder of an `input` command in this module."""
    if target in SWIPES:
        if pt is not None:
            raise NavViolation(f"{target} is a fixed swipe")
        return "input swipe {} {} {} {} {}".format(*SWIPES[target])
    if target not in TARGETS:
        raise NavViolation(f"target {target!r} is not allowlisted")
    x, y = round(pt[0]), round(pt[1])
    if not _inside((x, y), TARGETS[target]) or any(_inside((x, y), f) for f in FORBIDDEN.values()):
        raise NavViolation(f"{target} tap {(x, y)} outside its region or inside a forbidden rectangle")
    return f"input tap {x} {y}"


def _boxes(mask, min_w: float, min_h: float) -> list:
    """Outer contours of a binary mask -> [(x, y, w, h, fill)]; fill = convex-hull area / bounding-box area
    (~1 for a solid or outlined rectangle, also when its outline has a gap)."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        x, y, w, h = cv2.boundingRect(c)
        if w >= min_w and h >= min_h:
            out.append((x, y, w, h, cv2.contourArea(cv2.convexHull(c)) / (w * h)))
    return out


def _framed(mask, b) -> tuple:
    """How completely a box is outlined -> (top, bottom, left, right): per side (corners excluded, they are rounded),
    the fraction of positions with a set pixel within 3 % of the box width of that edge. ~1 for a card frame side."""
    x, y, w, h = b[:4]
    t = max(3, round(0.03 * w))
    s = mask[y:y + h, x:x + w].astype(bool)
    c0, c1, r0, r1 = int(0.15 * w), int(0.85 * w), int(0.15 * h), int(0.85 * h)
    return tuple(float(v.mean()) for v in (s[:t, c0:c1].any(0), s[-t:, c0:c1].any(0),
                                           s[r0:r1, :t].any(1), s[r0:r1, -t:].any(1)))


def _range(hsv, h, s, v):
    """HSV box mask (OpenCV units: H 0-179)."""
    return cv2.inRange(hsv, (h[0], s[0], v[0]), (h[1], s[1], v[1])) > 0


def _closed(mask):
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))


# Colour ranges measured on the owner's phone screenshots and the MuMu trophy_road.png (2026-10-07):
#   reward-choice background tiles H 103-111 S 160-210 V 95-180; title text H 98-101 S 145-155 V 249-255;
#   card-tile frame V 36-118 (dark on the outer sides, lit by the glow on the two inner sides);
#   Choose / Collect green H 56-63 S 90-160 V 227-255; bottom OK blue H 103-106 V 248-255.
BG_BLUE = ((100, 116), (110, 255), (50, 215))
TITLE_BLUE = ((92, 106), (90, 210), (225, 255))
BUTTON_GREEN = ((50, 70), (80, 255), (200, 255))
OK_BLUE = ((98, 110), (120, 255), (220, 255))


def reward_cards(img, hsv) -> list | None:
    """"Choose your reward" -> [left card centre, right card centre] or None. Relative-coordinate shape test: two
    dark-framed card tiles of equal size side by side, centred, in the top 60 %; light-blue title text just above
    them; nothing but the blue tile background below them (the one-card chest / reward screens fail the pair).
    Each tile's frame must be dark along its top, bottom and OUTER side (the inner sides are lit by the glow)."""
    H, W = img.shape[:2]
    dark = hsv[..., 2] < 60
    tiles = []
    for b in _boxes(dark, 0.2 * W, 0.2 * W):
        if b[2] <= 0.42 * W and 1.1 <= b[3] / b[2] <= 1.4 and b[4] >= 0.85 and b[1] + b[3] < 0.6 * H:
            tiles.append((*b[:4], _framed(dark, b)))
    tiles.sort()
    for i, a in enumerate(tiles):
        for b in tiles[i + 1:]:
            gap = b[0] - (a[0] + a[2])
            if not (abs(a[1] - b[1]) <= 0.02 * H and abs(a[2] - b[2]) <= 0.1 * a[2] and abs(a[3] - b[3]) <= 0.1 * a[3]
                    and 0 <= gap <= 0.15 * W and abs(a[0] + b[0] + b[2] - W) <= 0.1 * W   # pair centred on W/2
                    and min(a[4][0], a[4][1], a[4][2], b[4][0], b[4][1], b[4][3]) >= 0.9):
                continue
            top, bottom = a[1], max(a[1] + a[3], b[1] + b[3])
            title = _range(hsv[max(0, top - int(0.12 * H)):max(0, top - int(0.01 * H)), a[0]:b[0] + b[2]], *TITLE_BLUE)
            below = _range(hsv[bottom + int(0.12 * H):int(0.95 * H)], *BG_BLUE)
            if title.size and title.mean() >= 0.015 and below.size and below.mean() >= 0.85:
                return [(a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)]
    return None


def green_buttons(hsv) -> list:
    """Centres of solid green buttons (Trophy Road Collect / Choose shape: about 0.19 W x 0.1 W)."""
    W = hsv.shape[1]
    return [(x + w / 2, y + h / 2) for x, y, w, h, f in _boxes(_closed(_range(hsv, *BUTTON_GREEN)), 0.1 * W, 0.04 * W)
            if w <= 0.26 * W and 1.5 <= w / h <= 2.3 and f >= 0.85]


def blue_ok(hsv) -> bool:
    """The Trophy Road's centred blue OK button in the bottom 20 % of the frame."""
    H, W = hsv.shape[:2]
    y0 = int(0.8 * H)
    return any(0.13 * W <= w <= 0.28 * W and 1.8 <= w / h <= 3.2 and f >= 0.85 and abs(x + w / 2 - W / 2) <= 0.06 * W
               for x, y, w, h, f in _boxes(_closed(_range(hsv[y0:], *OK_BLUE)), 0.13 * W, 0.03 * W))


class Classifier:
    def __init__(self, tdir: Path = TEMPLATES):
        man = json.loads((tdir / "manifest.json").read_text())["templates"]
        self.t = {n: (cv2.imread(str(tdir / e["file"])), e) for n, e in man.items()}

    def find(self, img, n):
        """-> (score, centre) of template n in its search region."""
        t, e = self.t[n]
        r = e["region"]
        sub = img[r[1]:r[3], r[0]:r[2]]
        _, s, _, loc = cv2.minMaxLoc(cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED))
        return float(s), (r[0] + loc[0] + t.shape[1] / 2, r[1] + loc[1] + t.shape[0] / 2)

    def classify(self, img) -> dict:
        if img is None or img.shape[:2] != (1600, 900):     # a failed grab is NOT an unknown screen: never a tap
            return {"screen": "nograb", "why": "no 900x1600 frame", "scores": {}}
        hit, sc = {}, {}
        for n, (_, e) in self.t.items():
            s, c = self.find(img, n)
            sc[n] = round(s, 3)
            if s >= e["threshold"]:
                hit[n] = c
        if "conn_lost" in hit:                          # a system dialog over everything: check it first
            return {"screen": "conn_lost", "other_device": "another_device" in hit, "reload": hit.get("reload"),
                    "scores": sc}
        if "play_again" in hit and "results_ok" in hit:
            w = hit.get("winner")
            won = None if w is None else w[1] > 600            # loss: banner at y ~174 above the opponent's name
            return {"screen": "results", "play_again": hit["play_again"], "ok": hit["results_ok"], "won": won,
                    "scores": sc}
        if "red_x" in hit:
            return {"screen": "popup_x", "x": hit["red_x"], "scores": sc}
        if "modes_hdr" in hit:
            return {"screen": "modes", "scores": sc}
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        cards = reward_cards(img, hsv)
        if cards:                                       # "Choose your reward": two cards, pick one
            return {"screen": "choose_reward", "cards": cards, "scores": sc}
        col = hit.get("collect")                        # a green button that is not the Collect hit = Choose
        choose = next((g for g in green_buttons(hsv) if col is None or max(abs(g[0] - col[0]), abs(g[1] - col[1])) > 30),
                      None)
        if "bottom_ok" in hit or "collect" in hit or (choose and blue_ok(hsv)):   # Trophy Road: Collect / Choose, OK
            return {"screen": "trophy_road", "collect": col, "choose": choose, "ok": hit.get("bottom_ok"), "scores": sc,
                    "sig": cv2.resize(cv2.cvtColor(img[150:1450], cv2.COLOR_BGR2GRAY), (45, 65),
                                      interpolation=cv2.INTER_AREA)}
        if "battle" in hit:
            return {"screen": "main", "battle": hit["battle"], "bonus": "daily_bonus" in hit, "scores": sc,
                    "sig": cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (45, 80), interpolation=cv2.INTER_AREA)}
        if "logo" in hit:
            return {"screen": "loading", "scores": sc}
        return {"screen": "unknown", "scores": sc}


def load_state(path: Path = STATE) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"wins_today": 0, "last_main_t": 0.0, "W": 0, "L": 0, "D": 0}


class LadderNav:
    """Pure planner for ONE transition (results -> ... -> battle loading). No I/O; time passed in."""
    UNKNOWN_S, TRANSITION_S, HANDOFF_S, TAP_WAIT_S, TAP_MAX, STABLE_N, PROBE_S = 60.0, 300.0, 3.0, 2.5, 40, 3, 1800.0
    TR_SWIPES = 8                                 # Trophy Road scan: at most this many drags down the tree
    CHOOSE_MAX, FLOW_UNKNOWN_S, CARD_WAIT_S = 3, 10.0, 8.0   # reward choice: Choose taps; unknown / stuck limits

    def __init__(self, t0: float, state: dict, rng: random.Random | None = None):
        self.t0, self.st = t0, state
        self.rng = rng or random.Random()
        self.choose_flow = False                  # Choose tapped / choice screen seen, no known screen since
        self.chooses = 0                          # Choose taps this transition
        self.pick: int | None = None              # 0 = left card, 1 = right card (drawn once per choice screen)
        self.picked_at: float | None = None       # when the card was tapped
        self.committed = False                    # Play Again / Battle tapped: the next unknown/loading = handoff
        self.via_main = False                     # OK tapped: chests / probe until a stable main screen
        self.counted = False                      # this transition's results screen already scored
        self.unknown_since: float | None = None
        self.results_since: float | None = None
        self.nograb_since: float | None = None
        self.tr_swipes, self.tr_sig, self.tr_sig_before = 0, None, None
        self.taps, self.main_n, self.main_sig = 0, 0, None

    def plan(self, scr: dict, now: float) -> tuple:
        """-> ("act", target, point) | ("wait", why) | ("handoff", why) | ("stop", why)."""
        if now - self.t0 > self.TRANSITION_S:
            return ("stop", f"transition over {self.TRANSITION_S:.0f} s")
        s = scr["screen"]
        if s == "nograb":                         # Codex review F1/F2: no blind tap or handoff on a failed grab
            self.nograb_since = self.nograb_since if self.nograb_since is not None else now
            return ("stop", "screenshots failing for 60 s") if now - self.nograb_since > 60 else ("wait", "no screenshot")
        self.nograb_since = None
        if s in ("unknown", "loading"):
            self.unknown_since = self.unknown_since if self.unknown_since is not None else now
            idle = now - self.unknown_since
            if self.choose_flow:                  # owner 2026-10-07: never tap blind inside the reward choice
                if idle > self.FLOW_UNKNOWN_S:
                    return ("stop", f"{ALERT}: {s} screen for {self.FLOW_UNKNOWN_S:.0f} s after the trophy-road "
                                    f"Choose / card tap -- not tapping blind")
                return ("wait", f"{s} (trophy-road reward choice)")
            if self.committed and idle >= self.HANDOFF_S:
                return ("handoff", "menus left after Battle / Play Again: battle loading")
            if s == "unknown" and not self.committed and idle >= self.TAP_WAIT_S:
                if self.taps >= self.TAP_MAX:
                    return ("stop", f"{self.TAP_MAX} tap-throughs and still no known screen")
                return ("act", "tap_through", TAP_THROUGH_PT)
            if idle > self.UNKNOWN_S:
                return ("stop", f"{s} screen for {self.UNKNOWN_S:.0f} s")
            return ("wait", s)
        self.unknown_since = None
        if s != "main":
            self.main_n, self.main_sig = 0, None
        if s == "choose_reward":   # owner 2026-10-07: "the model can randomly choose" -- one random card, tapped once
            self.choose_flow = True
            if self.picked_at is None:
                self.pick = self.rng.randrange(2) if self.pick is None else self.pick
                return ("act", "reward_card", scr["cards"][self.pick])
            if now - self.picked_at > self.CARD_WAIT_S:
                return ("stop", f"{ALERT}: still on 'Choose your reward' {self.CARD_WAIT_S:.0f} s after tapping the "
                                f"{('left', 'right')[self.pick]} card")
            return ("wait", "reward card tapped")
        self.choose_flow, self.pick, self.picked_at = False, None, None   # a known screen: the choice is over
        if s == "conn_lost":   # owner's phone took the account: never kick it -- pause the run (live_play: STOP + Discord)
            if scr["other_device"]:
                return ("stop", "ANOTHER_DEVICE: the account was opened on another device (Connection lost)")
            return ("act", "reload", scr["reload"]) if scr["reload"] else ("wait", "connection lost: no RELOAD seen")
        if s == "popup_x":
            return ("act", "close_x", scr["x"])
        if s == "modes":
            return ("act", "modes_close", (450, 245))
        if s == "trophy_road":   # owner 2026-10-02: collect EVERY collectible reward (lower ones may be off-screen)
            if scr["collect"]:
                return ("act", "collect", scr["collect"])
            if scr.get("choose"):
                if self.chooses >= self.CHOOSE_MAX:
                    return ("stop", f"{ALERT}: Choose tapped {self.CHOOSE_MAX} times and the trophy road is still shown")
                return ("act", "choose", scr["choose"])
            self.tr_sig = scr.get("sig")
            unmoved = (self.tr_sig is not None and self.tr_sig_before is not None
                       and float(np.abs(self.tr_sig.astype(int) - self.tr_sig_before).mean()) < 2.0)
            if self.tr_swipes < self.TR_SWIPES and not unmoved:
                return ("act", "tr_scroll", None)
            return ("act", "bottom_ok", scr["ok"]) if scr["ok"] else ("wait", "trophy road: no OK button visible")
        if s == "results":
            if self.committed:
                return ("wait", "Play Again tapped: waiting for the queue")
            if not self.counted:
                self.results_since = self.results_since if self.results_since is not None else now
                if scr["won"] is None and now - self.results_since < 8.0:
                    return ("wait", "results: WINNER banner not read yet")
                self.counted = True
                key = {True: "W", False: "L", None: "D"}[scr["won"]]
                self.st[key] = self.st.get(key, 0) + 1
                if scr["won"]:
                    self.st["wins_today"] = self.st.get("wins_today", 0) + 1
                    if self.st["wins_today"] == DAILY_WINS:
                        self.via_main = True      # the day's 4th win: OK -> open the chests on the main screen
                if self.st.get("wins_today", 0) >= DAILY_WINS and now - self.st.get("last_main_t", 0) > self.PROBE_S:
                    self.via_main = True          # bonus used up: look at the main screen for the day's rollover
            return ("act", "results_ok", scr["ok"]) if self.via_main else ("act", "play_again", scr["play_again"])
        # main: wait until it is stable (chest / crown animations finished), then re-sync the count and queue
        if self.committed:
            return ("wait", "Battle tapped: waiting for the queue")
        sig = scr["sig"].astype(int)
        same = self.main_sig is not None and float(np.abs(sig - self.main_sig).mean()) < 2.0
        self.main_sig, self.main_n = sig, (self.main_n + 1 if same else 1)
        if self.main_n < self.STABLE_N:
            return ("wait", f"main screen settling ({self.main_n}/{self.STABLE_N})")
        w = self.st.get("wins_today", 0)
        if not scr["bonus"] and w < DAILY_WINS:
            self.st["wins_today"] = DAILY_WINS    # the game says today's bonus wins are done
        elif scr["bonus"] and w >= DAILY_WINS:
            self.st["wins_today"] = 0             # rollover: a new day's bonus
        self.st["last_main_t"] = now
        return ("act", "battle", scr["battle"])

    def acted(self, target: str, now: float) -> None:
        if target in ("play_again", "battle"):
            self.committed = True
        elif target == "tr_scroll":
            self.tr_swipes += 1
            self.tr_sig_before = self.tr_sig
        elif target == "tap_through":
            self.taps += 1
            self.unknown_since = now              # wait TAP_WAIT_S again before the next one
        elif target == "choose":
            self.chooses += 1
            self.choose_flow = True
        elif target == "reward_card":
            self.picked_at = now


def discord_alert(text: str, png: Path | None) -> bool:
    """Post text (+ the PNG) to the owner's Discord webhook, like discord_clip.post_clip. Never prints the URL, the
    server's reply or exception text; never raises."""
    try:
        url = WEBHOOK.read_text(encoding="utf-8").strip()
        if not url.startswith("https://"):
            raise ValueError
        b = "ClashBot" + uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json"
                f"\r\n\r\n").encode() + json.dumps({"content": text[:1900]}).encode()
        if png is not None and png.exists():
            body += (f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{png.name}\"\r\n"
                     f"Content-Type: image/png\r\n\r\n").encode() + png.read_bytes()
        body += f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                                              "User-Agent": "ClashBot-updates/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            ok = r.status in (200, 204)
    except Exception:                                    # noqa: BLE001 -- an alert failure must not hide the stop
        ok = False
    print(f"[ladder] Discord alert {'posted' if ok else 'FAILED'}", flush=True)
    return ok


def grab(adb: list[str]):
    from hero_button import parse_raw_screencap
    try:
        return parse_raw_screencap(subprocess.run(adb + ["exec-out", "screencap"], capture_output=True,
                                                  timeout=5).stdout)
    except Exception:                                    # noqa: BLE001 -- a missed grab is an unknown frame
        return None


class LadderNavRunner:
    """Device side, same interface as friend_nav.FriendNav: probe() before match 1, run() between matches."""
    POLL_S, COOLDOWN_S = 0.5, 1.5
    NAV_SCREENS = {"results", "main", "popup_x", "modes", "trophy_road", "choose_reward", "conn_lost"}

    def __init__(self, adb: list[str], dry_run: bool = False, log_dir: Path = HERE, state_path: Path = STATE,
                 wins_today: int | None = None, trophy_log: bool = True, seed: int | None = None, alert=discord_alert):
        self.adb, self.dry_run, self.log_dir, self.state_path = adb, dry_run, log_dir, state_path
        self.rng, self.alert = random.Random(seed), alert     # reward-card pick; TROPHY_ROAD_ALERT poster(text, png)
        self.clf = Classifier()
        self.trophy = None                       # passive trophy reader (trophy_read.py); None = off or digit bank missing
        self.trophies_total: int | None = None   # last main-menu trophy counter read
        if trophy_log:
            try:
                import trophy_read
                self.trophy = trophy_read.load()
            except Exception:                    # noqa: BLE001 -- passive logging never blocks navigation
                self.trophy = None
        self.st = load_state(state_path)
        if wins_today is not None:
            self.st["wins_today"] = wins_today
        self.last_outcome: bool | None = None

    def save(self) -> None:
        if not self.dry_run:                     # atomic: a crash mid-write must not reset the day's count
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st))
            tmp.replace(self.state_path)

    def read_trophy(self, kind: str, img):
        """Passive, timed read: kind 'total' (main menu counter) or 'delta' (results-screen change, magnitude).
        -> (value | None, ms). Any failure is None; never raises."""
        if self.trophy is None or img is None:
            return None, 0.0
        t0 = time.perf_counter()
        try:
            v = getattr(self.trophy, kind)(img)
        except Exception:                        # noqa: BLE001
            v = None
        return v, round(1000 * (time.perf_counter() - t0), 2)

    def probe(self, seconds: float = 8.0) -> str | None:
        t_end = time.time() + seconds
        while time.time() < t_end:
            s = self.clf.classify(grab(self.adb))["screen"]
            if s in self.NAV_SCREENS:
                print(f"[ladder] launch screen: {s} -- navigating to start match 1", flush=True)
                return s
            time.sleep(self.POLL_S)
        print(f"[ladder] no menu screen in {seconds:.0f} s -- assuming a battle is running: playing it", flush=True)
        return None

    def run(self) -> tuple[bool, str]:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        log = open(self.log_dir / f"ladder_nav_{stamp}.jsonl", "w", encoding="utf-8")
        shots = self.log_dir / "ladder_unknown"

        def W(**k):
            log.write(json.dumps({"t": round(time.time(), 2), **k}, default=str) + "\n")
            log.flush()
        nav, prev, last, reported = LadderNav(time.time(), self.st, self.rng), None, None, False
        d_pending, d_tries, total_tries, total_done = False, 0, 0, False   # passive trophy reads (see read_trophy)
        W(event="nav_start", dry_run=self.dry_run, state={k: v for k, v in self.st.items()})
        try:
            while True:
                img = grab(self.adb)
                scr = self.clf.classify(img)
                p = nav.plan(scr, time.time())
                if scr["screen"] == "results" and nav.counted and not reported:
                    reported, outcome = True, scr["won"]
                    self.last_outcome = outcome
                    mag, ms = self.read_trophy("delta", img)
                    delta = None if mag is None or outcome is None else (mag if outcome else -mag)   # sign = WINNER banner
                    d_pending = self.trophy is not None and delta is None and outcome is not None
                    extra = {} if self.trophy is None else {"trophies_delta": delta, "trophies_abs": mag,
                                                            "trophy_ms": ms}     # --no-trophy-log: event unchanged
                    W(event="outcome", won=outcome, **extra, state=dict(self.st))
                    tro = "" if self.trophy is None else f"  trophies {delta:+d}" if delta is not None else "  trophies n/a"
                    print(f"[ladder] result: {'WIN' if outcome else 'LOSS' if outcome is False else 'draw/unread'}"
                          f"  (session W{self.st.get('W', 0)} L{self.st.get('L', 0)} D{self.st.get('D', 0)}, "
                          f"wins today {self.st.get('wins_today', 0)}){tro}", flush=True)
                elif d_pending and scr["screen"] == "results" and d_tries < 4:
                    # the banner may still be animating on the first results frame: retry on the next few (we are
                    # still on this screen until the Play Again tap), then give up with the null already logged
                    d_tries += 1
                    mag, ms = self.read_trophy("delta", img)
                    if mag is not None and self.last_outcome is not None:
                        d_pending, delta = False, mag if self.last_outcome else -mag
                        W(event="trophies", trophies_delta=delta, trophies_abs=mag, trophy_ms=ms, retry=d_tries)
                        print(f"[ladder] trophies: {delta:+d}", flush=True)
                if scr["screen"] == "main" and p[:2] == ("act", "battle") and not total_done and total_tries < 3:
                    total_tries += 1       # the main screen is stable here (planner waited STABLE_N frames)
                    tot, ms = self.read_trophy("total", img)
                    if self.trophy is not None:
                        W(event="trophies", trophies_total=tot, trophy_ms=ms)     # null = failed read
                    if tot is not None:
                        total_done, self.trophies_total = True, tot
                        print(f"[ladder] trophies: {tot} total", flush=True)
                if (scr["screen"], p[:2]) != last:
                    W(event="screen", screen=scr["screen"], plan=p, scores=scr["scores"],
                      bonus=scr.get("bonus"), won=scr.get("won"))
                    print(f"[ladder] {scr['screen']}: {p}", flush=True)
                    last = (scr["screen"], p[:2])
                if p[0] in ("handoff", "stop"):
                    png = self.log_dir / f"ladder_stop_{stamp}.png"
                    if p[0] == "stop" and img is not None:
                        cv2.imwrite(str(png), img)
                    W(event=p[0], why=p[1], state=dict(self.st))
                    print(f"[ladder] {p[0].upper()}: {p[1]}", flush=True)
                    if p[0] == "stop" and p[1].startswith(ALERT):   # owner 2026-10-07: stop + alert, never tap blind
                        text = (f"ClashAI ladder STOPPED {time.strftime('%H:%M')} in the trophy-road reward choice: "
                                f"{p[1]}. Screenshot attached. Navigate it by hand, then restart the run.")
                        sent = False if self.dry_run else self.alert(text, png if png.exists() else None)
                        W(event="alert", text=text, sent=sent, png=str(png) if png.exists() else None)
                    self.save()
                    return p[0] == "handoff", p[1]
                if p[0] == "act":
                    same = prev and prev[1] == p[1] and (p[2] is None or max(abs(prev[2][0] - p[2][0]),
                                                                          abs(prev[2][1] - p[2][1])) <= 8)
                    if same:
                        cmd = command_for(p[1], p[2])
                        if (p[1] in ("tap_through", "choose", "reward_card") or (p[1] == "battle" and nav.via_main)) \
                                and img is not None:
                            # evidence: unknown (chest?) screens, the main screen we requeue from after OK, and the
                            # first real MuMu frames of the trophy-road reward choice
                            shots.mkdir(exist_ok=True)
                            tag = "" if p[1] in ("tap_through", "battle") else f"_{p[1]}"
                            cv2.imwrite(str(shots / f"{stamp}_{nav.taps:02d}{tag}.png"), img)
                        if p[1] == "reward_card":
                            W(event="reward_pick", side=("left", "right")[nav.pick], point=p[2])
                            print(f"[ladder] reward choice: random pick = {('left', 'right')[nav.pick]} card", flush=True)
                        W(event="input", target=p[1], cmd=cmd, dry_run=self.dry_run)
                        print(f"[ladder] {'WOULD ' if self.dry_run else ''}{p[1]}: {cmd}", flush=True)
                        if not self.dry_run:
                            subprocess.run(self.adb + ["shell", cmd], capture_output=True, timeout=5)
                        nav.acted(p[1], time.time())
                        prev = None
                        time.sleep(self.COOLDOWN_S)
                        continue
                    prev = p
                else:
                    prev = None
                time.sleep(self.POLL_S)
        finally:
            self.save()
            log.close()
