import sys, json
from pathlib import Path
import cv2
REPO = Path.cwd(); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"icebow"/"src"))
from clashrl.config import Config
from clashrl.replay_mine import load_detector
cfg = Config.load(); det = load_detector(cfg)
conf = float(cfg.get("observation","detector_conf",default=0.35))
out = {}
for s in sys.argv[1:]:
    cap = cv2.VideoCapture(str(Path("icebow/data/sessions")/s/"video.mp4"))
    hits = []; fi = -1
    while True:
        ok, fr = cap.read()
        if not ok: break
        fi += 1
        if fi % 6: continue
        for d in det.detect(fr, conf=conf):
            if "barrel" in str(d.cls):
                hits.append({"frame": fi, "cls": str(d.cls), "conf": round(float(d.conf),3),
                             "cx": round(float(d.cx),4), "cy": round(float(d.cy),4),
                             "gy": round(float(d.gy),4), "team": str(d.team)})
    cap.release(); out[s] = hits
    print(s, "barrel detections:", len(hits), flush=True)
Path("scratchpad/gauntlet/L67/barrel_hits.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
