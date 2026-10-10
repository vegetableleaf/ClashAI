"""Emote reliability test for --emote-spam (owner 2026-10-10). Run it IN a live Classic 1v1 (never between matches).

Sends N emotes, each as ONE two-tap command (chat button, gap, emote), INTERVAL s apart (default 1.5 s > the 1.3 s cooldown).
0.5 s after each command returns it takes a screencap and classifies the HAND AREA (y 1330-1520):
  hand  = card art (the four magenta elixir drops show)       -> pass
  panel = the white quick-chat phrase boxes cover the area    -> FAIL, then one chat-button tap closes it
  other = neither (match over / menu / paused)                 -> FAIL
Calibrated on the lead's shots (hand strips: ref_emoN_hand.png here): panel white fraction 0.471, hand 0.027 / magenta 0.021, menu-ish screens 0 / 0.

It checks that the panel CLOSED (the hand is back). It does not prove the emote bubble was sent.
Only `input tap` commands and screencaps are sent; nothing else touches the game.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/emote/emote_reliability.py [--n 20] [--gap-ms 150] [--fast-input]
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/emote/emote_reliability.py --selftest   (reference shots, no adb)
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
LIVE = HERE.parents[1] / "L68" / "live_reader"
sys.path.insert(0, str(LIVE))
import emote_spam  # noqa: E402  the same coordinates / command as live_play --emote-spam

# the MuMu adb that LIVE/adb.sh pins to the live emulator
ADB = ["C:/Program Files/Netease/MuMuPlayer/nx_device/15.0/shell/adb.exe", "-s", "127.0.0.1:16384"]
WHITE_PANEL, MAGENTA_HAND = 0.25, 0.005
Y0, Y1, X0 = 1330, 1520, 170    # hand area; x >= 170 skips the chat icon (white) at the far left


def features(im: Image.Image, cropped: bool = False) -> dict:
    """white = fraction of near-white pixels, magenta = fraction of elixir-drop pixels, in the hand area.
    cropped: im is already the y 1330-1520 strip (the saved reference crops)."""
    w, h = im.size
    sy, sx = (1.0 if cropped else h / 1600), w / 900
    rows = slice(0, h) if cropped else slice(round(Y0 * sy), round(Y1 * sy))
    a = np.asarray(im.convert("RGB"))[rows, round(X0 * sx):].astype(int)
    white = (a.min(axis=2) >= 235).mean()
    magenta = ((a[..., 0] > 180) & (a[..., 2] > 150) & (a[..., 1] < 120)).mean()
    return dict(white=round(float(white), 3), magenta=round(float(magenta), 4))


def classify(im: Image.Image, cropped: bool = False) -> str:
    f = features(im, cropped)
    return "panel" if f["white"] >= WHITE_PANEL else "hand" if f["magenta"] >= MAGENTA_HAND else "other"


def selftest() -> int:
    want = {"emo3": "panel", "emo2": "hand", "emo4": "hand", "emo1": "other", "emo5": "other"}
    bad = 0
    for n, w in want.items():
        im = Image.open(HERE / f"ref_{n}_hand.png")
        got = classify(im, cropped=True)
        bad += got != w
        print(f"{n}: {got} (want {w}) {features(im, True)}")
    print("SELFTEST", "PASS" if not bad else "FAIL")
    return int(bool(bad))


def run(cmd: list[str], timeout: float = 10, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(ADB + cmd, capture_output=True, timeout=timeout, **kw)


def shot() -> Image.Image:
    return Image.open(io.BytesIO(run(["exec-out", "screencap", "-p"], timeout=15).stdout))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--gap-ms", type=int, default=150)
    ap.add_argument("--interval-s", type=float, default=1.5)
    ap.add_argument("--look-s", type=float, default=0.5, help="screencap this long after the command returns")
    ap.add_argument("--fast-input", action="store_true", help="send through one persistent adb shell, as live_play --fast-input")
    ap.add_argument("--out", type=Path, default=HERE / f"reliability_{time.strftime('%Y%m%d_%H%M%S')}.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    sh = None
    if a.fast_input:
        from fast_input import PersistentShell
        sh = PersistentShell(ADB)
        if not sh.run("true"):
            print("persistent shell did not answer")
            return 2
    base = classify(shot())
    if base != "hand":
        print(f"ABORT: the hand area reads {base!r} before any input -- start this inside a live match with the hand showing")
        return 2
    cmd = emote_spam.emote_cmd(900, 1600, a.gap_ms)
    print(f"channel={'persistent shell' if sh else 'adb.exe per call'}  cmd: {cmd}")
    rows, t0 = [], time.time()
    for i in range(a.n):
        t_due = t0 + i * a.interval_s
        time.sleep(max(0.0, t_due - time.time()))
        late_ms = round((time.time() - t_due) * 1000)
        t = time.time()
        ok = sh.run(cmd, timeout=5) if sh else run(["shell", cmd], timeout=5).returncode == 0
        cmd_ms = round((time.time() - t) * 1000)
        time.sleep(a.look_s)
        t = time.time()
        im = shot()
        state, f = classify(im), features(im)
        row = dict(i=i + 1, cmd_ms=cmd_ms, cmd_ok=bool(ok), late_ms=late_ms, shot_ms=round((time.time() - t) * 1000), state=state, **f)
        if state != "hand":
            run(["shell", f"input tap {emote_spam.CHAT_XY[0]} {emote_spam.CHAT_XY[1]}"])   # one tap on the chat button closes it
            time.sleep(0.4)
            row["after_close_tap"] = classify(shot())
        rows.append(row)
        print(json.dumps(row), flush=True)
    if sh:
        sh.close()
    passed = sum(r["state"] == "hand" and r["cmd_ok"] for r in rows)
    summary = dict(n=a.n, passed=passed, failed=a.n - passed, gap_ms=a.gap_ms, interval_s=a.interval_s, fast_input=bool(sh),
                   cmd_ms_median=int(np.median([r["cmd_ms"] for r in rows])), cmd_ms_max=max(r["cmd_ms"] for r in rows),
                   states={s: sum(r["state"] == s for r in rows) for s in ("hand", "panel", "other")})
    a.out.write_text(json.dumps(dict(summary=summary, rows=rows), indent=1))
    print(f"PASS {passed}/{a.n}" if passed == a.n else f"FAIL: {passed}/{a.n} passed", json.dumps(summary), f"-> {a.out}")
    return int(passed != a.n)


if __name__ == "__main__":
    raise SystemExit(main())
