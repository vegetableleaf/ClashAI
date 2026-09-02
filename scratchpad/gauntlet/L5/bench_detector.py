"""Idle-box detector latency benchmark. Mirrors the ONE live call, BoardDetector.detect():
   model.predict(frame, conf=floor, imgsz=960, verbose=False)  -- fp32, default device, 1182x668 BGR.
Wall clock around predict() is what the agent pays; ultralytics' own speed dict is the split.
"""
import sys, time, statistics as st, json
import cv2, torch
from ultralytics import YOLO
from pathlib import Path

ROOT = Path("C:/Users/benpe/ClashBot/icebow")
stems = [l.strip().lstrip("\ufeff") for l in open(ROOT/"data/detect/val_board15.txt", encoding="utf-8") if l.strip()]
frames = [cv2.imread(str(ROOT/"data/detect/images/val"/(s+".jpg"))) for s in stems]
frames = [f for f in frames if f is not None]
print(f"frames {len(frames)} shape {frames[0].shape}  torch {torch.__version__} cuda {torch.cuda.is_available()}")

ARMS = {
    "board-24-5 (operating)": ROOT/"runs/detect/board-24-5/weights/best.pt",
    "board-26": ROOT/"runs/detect/board-26/weights/best.pt",
    "screen-y11s": ROOT/"runs/detect/screen-y11s/weights/best.pt",
    "screen-y26s": ROOT/"runs/detect/screen-y26s/weights/best.pt",
}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
out = {}
for name, w in ARMS.items():
    for half in (False, True):
        m = YOLO(str(w))
        kw = dict(conf=0.25, imgsz=960, verbose=False, half=half)
        for f in frames[:10]:
            m.predict(f, **kw)                      # warm-up (cudnn autotune, allocator)
        torch.cuda.synchronize()
        wall, pre, inf, post, ndet = [], [], [], [], []
        for i in range(N):
            f = frames[i % len(frames)]
            t0 = time.perf_counter()
            r = m.predict(f, **kw)[0]
            wall.append((time.perf_counter() - t0) * 1000)
            pre.append(r.speed["preprocess"]); inf.append(r.speed["inference"]); post.append(r.speed["postprocess"])
            ndet.append(len(r.boxes))
        row = dict(n=N, half=half,
                   wall_med=st.median(wall), wall_p90=sorted(wall)[int(0.9*N)], wall_max=max(wall),
                   pre=st.median(pre), inf=st.median(inf), post=st.median(post), dets=st.mean(ndet))
        out[f"{name} half={half}"] = row
        print(f"{name:<24} half={half!s:<5} wall med {row['wall_med']:6.1f} p90 {row['wall_p90']:6.1f} max {row['wall_max']:6.1f} ms"
              f" | pre {row['pre']:.1f} inf {row['inf']:.1f} post {row['post']:.1f} | dets {row['dets']:.1f}", flush=True)
        del m; torch.cuda.empty_cache()
json.dump(out, open(Path(__file__).with_name("bench_detector.json"), "w"), indent=1)
