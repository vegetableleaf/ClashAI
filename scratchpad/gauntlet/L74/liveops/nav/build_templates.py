"""Crop the Claim All button template ("Rewards" 10-19 and "Supercell Support" 10-28 screens: the same orange button) from the stuck screenshot.
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/nav/build_templates.py
Source frame (900x1600 PNG, `adb exec-out screencap -p` taken by stuck_watch.sh): scratchpad/gauntlet/L70/live/stuck_0258.png,
copied next to the templates as source_support_claim.png so the build is reproducible."""
import json
import shutil
from pathlib import Path
import cv2

H = Path(__file__).resolve().parent
SRC = H / "source_support_claim.png"
if not SRC.exists():
    shutil.copy(H.parents[2] / "L70" / "live" / "stuck_0258.png", SRC)
# name: (box x0 y0 x1 y1, search region, threshold)
SPEC = {
    "claim_all": ((322, 1408, 578, 1514), (150, 1300, 750, 1600), 0.85),    # orange "Claim All" button
}
img = cv2.imread(str(SRC))
assert img.shape[:2] == (1600, 900), img.shape
man = {}
for n, (b, reg, thr) in SPEC.items():
    cv2.imwrite(str(H / "templates" / f"{n}.png"), img[b[1]:b[3], b[0]:b[2]])
    man[n] = {"file": f"{n}.png", "source": SRC.name, "box": b, "region": reg, "threshold": thr}
(H / "manifest_fragment.json").write_text(json.dumps(man, indent=1))
print("built", sorted(man))
