"""Self-check for trophy_read + its ladder_nav wiring (no device).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/test_trophy_read.py"""
import json
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ladder_nav  # noqa: E402
import trophy_read  # noqa: E402

IMG = HERE.parents[1] / "L73" / "trophies" / "img"
labels = json.loads((IMG.parent / "labels.json").read_text())
rd = trophy_read.TrophyReader()

# 1. every labelled frame reads exactly (main total: 65 frames; result delta: 15 frames + 1 "no trophy" frame -> None)
for n, e in labels.items():
    img = cv2.imread(str(IMG / n))
    got = rd.total(img) if e["kind"] == "main" else rd.delta(img)
    assert got == e["value"], (n, e["value"], got)

# 2. failures are None, never exceptions
blank = np.zeros((1600, 900, 3), np.uint8)
assert rd.total(blank) is None and rd.delta(blank) is None
assert rd.total(None) is None and rd.delta(None) is None
assert rd.total(np.zeros((10, 10, 3), np.uint8)) is None
assert trophy_read.load(Path("/nonexistent/digits.npz")) is None

# 3. ladder_nav wiring: results frame -> outcome event carries the signed delta; --no-trophy-log leaves it unchanged
res = cv2.imread(str(IMG / "result_00.png"))                       # delta magnitude 30
RES = {"screen": "results", "play_again": (310, 1450), "ok": (590, 1450), "scores": {}}


class Stop(Exception):
    pass


def run_once(won, trophy_log, frames=3):
    d = Path(tempfile.mkdtemp())
    r = ladder_nav.LadderNavRunner([], dry_run=True, log_dir=d, state_path=d / "s.json", trophy_log=trophy_log)
    seq = iter([dict(RES, won=won)] * frames)

    def classify(img):
        try:
            return next(seq)
        except StopIteration:
            raise Stop

    r.clf.classify = classify
    ladder_nav.grab, saved = (lambda adb: res), ladder_nav.grab
    time.sleep, real_sleep = (lambda s: None), time.sleep
    try:
        r.run()
    except Stop:
        pass
    finally:
        ladder_nav.grab, time.sleep = saved, real_sleep
    log = next(d.glob("ladder_nav_*.jsonl")).read_text().splitlines()
    return [json.loads(x) for x in log if '"outcome"' in x][0]


o = run_once(True, True)
assert o["trophies_delta"] == 30 and o["trophies_abs"] == 30 and o["won"] is True, o
o = run_once(False, True)
assert o["trophies_delta"] == -30, o
o = run_once(True, False)
assert "trophies_delta" not in o and "trophy_ms" not in o, o      # opt-out: event as before
print("trophy_read tests passed")
