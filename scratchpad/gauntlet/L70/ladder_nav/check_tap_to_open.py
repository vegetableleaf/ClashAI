"""Classify every saved screenshot; print screen + chest_q/chest_q2/chest_tap scores. Usage: python check_tap_to_open.py [out.json]"""
import sys, json, glob
from pathlib import Path
import cv2
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[1] / "L68" / "live_reader"))
from ladder_nav import Classifier
c = Classifier()
files = sorted(glob.glob(str(H / "*.png")) + glob.glob(str(H / "raw" / "*.png")) + glob.glob(str(H.parent / "live" / "stuck_*.png")))
files = [f for f in files if "/templates/" not in f.replace("\\", "/")]
out = {}
for f in files:
    r = c.classify(cv2.imread(f))
    out[Path(f).name] = r["screen"]
    sc = r["scores"]
    print(f"{Path(f).name:34s} {r['screen']:14s} " + " ".join(f"{k}={sc[k]:.3f}" for k in ("chest_q", "chest_q2", "chest_tap") if k in sc))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
