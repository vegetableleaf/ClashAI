"""Accuracy + timing of trophy_read on every labelled test frame -> results.json.
Main frames: leave-one-image-out (bank rebuilt without that image's exemplars is NOT possible after dedupe, so the bank
excludes exemplars whose bytes occur ONLY in that image). Result frames use the main-frame bank (independent set).
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/trophies/eval_trophies.py
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(1)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "L68" / "live_reader"))
import trophy_read as tr  # noqa: E402

labels = json.loads((HERE / "labels.json").read_text())
imgs = {n: cv2.imread(str(HERE / "img" / n)) for n in labels}
rd = tr.TrophyReader()
rows, t_main, t_res = [], [], []
# leave-one-image-out bank for main frames
owner: dict[bytes, set] = {}
for n, e in labels.items():
    if e["kind"] == "main":
        for d in tr.glyphs(imgs[n], tr.MAIN_ROI):
            owner.setdefault(np.round(d * 255).astype(np.uint8).tobytes(), set()).add(n)
Xb = (rd.X * 255).round().astype(np.uint8)
for n, e in labels.items():
    img = imgs[n]
    if e["kind"] == "main":
        keep = np.array([owner.get(x.tobytes(), set()) != {n} for x in Xb])
        loo = tr.TrophyReader.__new__(tr.TrophyReader)
        loo.X, loo.y = rd.X[keep], rd.y[keep]
        got = loo.total(img)
        t0 = time.perf_counter()
        for _ in range(20):
            rd.total(img)
        t_main.append((time.perf_counter() - t0) / 20)
    else:
        got = rd.delta(img)
        t0 = time.perf_counter()
        for _ in range(20):
            rd.delta(img)
        t_res.append((time.perf_counter() - t0) / 20)
    rows.append({"img": n, "kind": e["kind"], "expected": e["value"], "read": got, "ok": got == e["value"]})
main_ok = sum(r["ok"] for r in rows if r["kind"] == "main")
n_main = sum(r["kind"] == "main" for r in rows)
res_ok = sum(r["ok"] for r in rows if r["kind"] == "result")
n_res = sum(r["kind"] == "result" for r in rows)
blank = np.zeros((1600, 900, 3), np.uint8)
t0 = time.perf_counter()
for _ in range(50):
    rd.total(blank), rd.delta(blank)
t_blank = (time.perf_counter() - t0) / 100
out = {"main_total": f"{main_ok}/{n_main}", "result_delta": f"{res_ok}/{n_res}",
       "ms_per_call_total_median": round(1000 * float(np.median(t_main)), 3),
       "ms_per_call_total_max": round(1000 * max(t_main), 3),
       "ms_per_call_delta_median": round(1000 * float(np.median(t_res)), 3),
       "ms_per_call_blank_frame": round(1000 * t_blank, 3), "rows": rows}
(HERE / "results.json").write_text(json.dumps(out, indent=1))
print({k: v for k, v in out.items() if k != "rows"})
for r in rows:
    if not r["ok"]:
        print("MISS", r)
