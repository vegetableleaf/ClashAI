"""Classify every empty-slot (-1) run in a recorded live match: read all 4 slots on every k-th
frame, then print each maximal run of consecutive -1 reads per slot with its duration and what was
read before/after. Decides whether empties are ~1 s deal gaps (benign) or stuck states (defect).
argv: cfg yaml, mp4, stride (frames), [min_run_s to list, default 0]"""
import sys, cv2, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.vision import Vision
cfg = Config.load(sys.argv[1]); vid = sys.argv[2]; every = int(sys.argv[3]); min_s = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
FPS = 18.5
v = Vision(cfg); cap = cv2.VideoCapture(vid); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
reads = []  # (frame, [key per slot])
fi = 0
while True:
    ok, fr = cap.read()
    if not ok: break
    if fi % every == 0:
        reads.append((fi, [v.match_card(v.hand_crop(fr, cx, cy))[0] for cx, cy in v.hand_slots]))
    fi += 1
print(vid, n, "frames", len(reads), "reads every", every, "frames =", every / FPS, "s")
tot_reads = len(reads) * 4; empty_reads = sum(1 for _, s in reads for i in s if i < 0)
print(f"empty slot-reads {empty_reads}/{tot_reads} = {empty_reads/tot_reads:.3f}")
hist = {}
for sl in range(4):
    run = None
    for k, (f, s) in enumerate(reads):
        if s[sl] < 0:
            if run is None: run = [k, k]
            else: run[1] = k
        elif run is not None:
            a, b = run; dur = (reads[b][0] - reads[a][0] + every) / FPS
            before = v.deck_keys[reads[a-1][1][sl]] if a > 0 and reads[a-1][1][sl] >= 0 else "?"
            after = v.deck_keys[s[sl]]
            bucket = "<=1.5s" if dur <= 1.5 else ("<=3s" if dur <= 3 else ("<=10s" if dur <= 10 else ">10s"))
            hist[bucket] = hist.get(bucket, 0) + 1
            if dur >= min_s: print(f"slot {sl} frames {reads[a][0]:5d}-{reads[b][0]:5d} t={reads[a][0]/FPS:6.1f}s dur={dur:5.1f}s  {before} -> EMPTY -> {after}")
            run = None
    if run is not None:
        a, b = run; dur = (reads[b][0] - reads[a][0] + every) / FPS
        bucket = "tail(end of video)"; hist[bucket] = hist.get(bucket, 0) + 1
        print(f"slot {sl} frames {reads[a][0]:5d}-{reads[b][0]:5d} t={reads[a][0]/FPS:6.1f}s dur={dur:5.1f}s  EMPTY to end of video")
print("run-length histogram:", dict(sorted(hist.items())))
