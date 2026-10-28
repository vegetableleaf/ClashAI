#!/usr/bin/env python
"""Tightened live watcher (PROPOSAL, not deployed; replaces scratchpad/gauntlet/L70/live/stuck_watch.sh).

What was wrong with stuck_watch.sh (measured on overnight.out, 78,140 lines, results/transitions.md):
  - its rule "6 of the last 12 lines match `] unknown:|tap_through:`" fires on 2,478 of the 5,312 firing windows INSIDE
    normal handoff transitions (a normal transition prints `unknown: ('wait'..)` + `unknown: ('handoff'..)` + loading lines;
    benign chest openings print up to 34 tap_through lines) -> false alarms;
  - it exits at the first alert, so it has to be re-armed by hand.
This watcher only reacts to events that mean something, never to unknown / tap_through / handoff lines, and it keeps running
(each alert is ONE stdout line: run it under Monitor, or with --once as a one-shot like the old script):
  STOP      a `[nav] run stopped before match N: <why>` line (classified: adb_down, unknown_screen, transition_timeout,
            another_device, loading_stuck, trophy_road, other). Repeats of one class within 20 min are counted and re-reported
            at the 3rd / 6th / 9th (the supervisor gives up after 10).
  GAVE_UP   supervisor.log `NOT restarting` (restart limit reached: nobody restarts live any more).
  NO_PROGRESS  no `{"played"...}` / `[ladder] result:` line for 12 min while a live_play process runs (match gaps: median 4.1 min,
            p99 8 min, results/gaps; every gap over 10 min was a real incident).
  PROC_GONE no ladder live_play process for 10 min and no STOP file.
A `[live] stop file ... found` line (the normal owner / lead stop) is NOT an alert.
Screenshots (adb exec-out screencap -p, read-only, timeout 20 s) are taken on an alert unless --no-screenshot; skipped for adb_down.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/stuck_watch2.py [--once] [--no-screenshot] [--poll 30]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
L = REPO / "scratchpad/gauntlet/L70/live"
ADB = r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe"

STOP_RE = re.compile(r"^\[nav\] run stopped before match (\d+): (.*)$")
PROGRESS_RE = re.compile(r'^\{"played": |^\[ladder\] result: ')
# (substring of the stop reason, class, what the lead should do)
CLASSES = [
    ("ANOTHER_DEVICE", "another_device", "the owner's phone took the account: do NOT restart; ask the owner"),
    ("screenshots failing", "adb_down", "adb transport to MuMu dropped: `adb connect 127.0.0.1:16384`, check `adb devices -l`"),
    ("tap-throughs and still no known screen", "unknown_screen", "a screen the navigator does not know: look at the screenshot (Claim All?)"),
    ("loading screen for", "loading_stuck", "game stuck on loading: look at MuMu, relaunch is automatic once"),
    ("transition over 300 s", "transition_timeout", "main screen never settled / maintenance: check the game"),
    ("TROPHY_ROAD_ALERT", "trophy_road", "trophy-road reward choice stuck: navigate by hand"),
]


NO_SHOT = ("GAVE_UP", "PROC_GONE", "STOP[adb_down]", "STOP[another_device]")   # a screenshot says nothing / adb is the problem


def classify(why: str) -> tuple[str, str]:
    for sub, label, hint in CLASSES:
        if sub in why:
            return label, hint
    return "other", "read overnight.out"


class Detector:
    """Pure state machine: feed(line, now, src) and tick(now, live_running, stop_file) return alert strings."""

    def __init__(self, now: float, no_progress_s: float = 720.0, gone_s: float = 600.0, repeat_window_s: float = 1200.0):
        self.no_progress_s, self.gone_s, self.repeat_window_s = no_progress_s, gone_s, repeat_window_s
        self.last_progress, self.np_alerted = now, False
        self.gone_since: float | None = None
        self.gone_alerted = False
        self.seen: dict[str, list] = {}           # class -> [first time of this burst, count, last time]
        self.stops = 0                            # STOP lines fed (alerted or not)
        self.alerts = 0

    def _emit(self, s: str) -> list[str]:
        self.alerts += 1
        return [s]

    def feed(self, line: str, now: float, src: str = "overnight") -> list[str]:
        line = line.rstrip("\r\n")
        if src == "supervisor":
            return self._emit(f"GAVE_UP supervisor stopped restarting: {line[:200]}") if "NOT restarting" in line else []
        if PROGRESS_RE.match(line):
            self.last_progress, self.np_alerted = now, False
            return []
        m = STOP_RE.match(line)
        if not m:
            return []
        self.stops += 1
        self.last_progress, self.np_alerted = now, False      # the stop alert is the news; a fresh window starts
        label, hint = classify(m.group(2))
        rec = self.seen.get(label)
        if rec is None or now - rec[2] > self.repeat_window_s:      # a new burst: >20 min since this class last stopped the run
            self.seen[label] = [now, 1, now]
            return self._emit(f"STOP[{label}] before match {m.group(1)}: {m.group(2)[:120]} -- {hint}")
        rec[1], rec[2] = rec[1] + 1, now
        if rec[1] in (3, 6, 9):
            return self._emit(f"STOP[{label}] REPEAT x{rec[1]} in {int((now - rec[0]) / 60)} min (supervisor limit 10): {m.group(2)[:100]}")
        return []

    def tick(self, now: float, live_running: bool, stop_file: bool) -> list[str]:
        out: list[str] = []
        if stop_file:                                        # an owner / lead stop is in progress or done: nothing to report
            self.last_progress, self.np_alerted, self.gone_since, self.gone_alerted = now, False, None, False
            return out
        if live_running:
            self.gone_since, self.gone_alerted = None, False
        elif self.gone_since is None:
            self.gone_since = now
        elif now - self.gone_since >= self.gone_s and not self.gone_alerted:
            self.gone_alerted = True
            out += self._emit(f"PROC_GONE no ladder live_play process for {int((now - self.gone_since) / 60)} min and no STOP file")
        if live_running and not self.np_alerted and now - self.last_progress >= self.no_progress_s:
            self.np_alerted = True
            out += self._emit(f"NO_PROGRESS no match finished for {int((now - self.last_progress) / 60)} min while live_play runs")
        return out


def read_new(path: Path, pos: int) -> tuple[list[str], int]:
    """Complete new lines since byte offset pos (a shorter file = rotated: start over)."""
    try:
        size = path.stat().st_size
        if size < pos:
            pos = 0
        with open(path, "rb") as f:
            f.seek(pos)
            data = f.read()
    except OSError:
        return [], pos
    end = data.rfind(b"\n") + 1
    return data[:end].decode("utf-8", "replace").splitlines(), pos + end


def live_running() -> bool:
    import psutil
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            c = " ".join(p.info["cmdline"] or [])
        except Exception:                                    # noqa: BLE001
            continue
        if (p.info["name"] or "").lower().startswith("python") and "--ladder" in c and ("live_play.py" in c or "live_play_hand_v" in c):
            return True
    return False


def screenshot(why: str) -> str:
    png = L / f"stuck_{time.strftime('%H%M')}.png"
    try:
        with open(png, "wb") as f:
            subprocess.run([ADB, "-s", "127.0.0.1:16384", "exec-out", "screencap", "-p"], stdout=f, stderr=subprocess.DEVNULL, timeout=20)
        return f"  screenshot {png}"
    except Exception as exc:                                 # noqa: BLE001
        return f"  screenshot failed ({type(exc).__name__})"


def run(a: argparse.Namespace, live_dir: Path = L, max_iter: int | None = None, clock=time.time, sleep=time.sleep,
        running=live_running, out=print) -> int:
    ov, sup = live_dir / "overnight.out", live_dir / "supervisor.log"
    pos = {ov: ov.stat().st_size if ov.exists() else 0, sup: sup.stat().st_size if sup.exists() else 0}
    det = Detector(clock())
    last_run_check, running_now, n = -1e9, True, 0
    while max_iter is None or n < max_iter:
        n += 1
        sleep(a.poll)
        now, alerts = clock(), []
        for p, src in ((ov, "overnight"), (sup, "supervisor")):
            lines, pos[p] = read_new(p, pos[p])
            for ln in lines:
                alerts += det.feed(ln, now, src)
        if now - last_run_check >= 60:                       # a process scan is ~1 s: once a minute
            running_now, last_run_check = running(), now
        alerts += det.tick(now, running_now, (live_dir / "STOP").exists())
        for al in alerts:
            extra = "" if a.no_screenshot or al.startswith(NO_SHOT) else screenshot(al)
            out(f"{time.strftime('%H:%M', time.localtime(now))} {al}{extra}", flush=True)
        if alerts and a.once:
            return 0
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="exit after the first alert (the old stuck_watch.sh behaviour)")
    ap.add_argument("--no-screenshot", action="store_true")
    ap.add_argument("--poll", type=float, default=30.0)
    sys.exit(run(ap.parse_args()))
