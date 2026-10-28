"""Score the Claim All button template on every recorded 900x1600 screen we have (read-only, below-normal priority).
Corpus: L68/live_reader/ladder_unknown (evidence frames of every unknown screen the navigator tapped through),
ladder_stop_*.png, L70/ladder_nav/raw, L70/live/stuck_*.png, L68/live_reader/fixtures, icebow/data/ranked_nav (if present).
Writes results/claim_all_corpus.json (rows: file, claim_all score, claim_xy) + prints hits and the top negatives.
SLOW: ~7 min and ~4 GB of PNG reads for the 2,897 frames of 10-28 -- run it once, not in a loop; test_nav_proposed.py
uses the saved JSON plus a fixed sample.
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/nav/score_corpus.py"""
import ctypes
import json
from pathlib import Path
import cv2

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
H = Path(__file__).resolve().parent
G = H.parents[2]                                     # scratchpad/gauntlet
ROOT = G.parents[1]                                  # repo root
man = json.loads((H / "manifest_fragment.json").read_text())["claim_all"]
T = cv2.imread(str(H / "templates" / man["file"]))


def score(img):
    r = man["region"]
    sub = img[r[1]:r[3], r[0]:r[2]]
    _, s, _, loc = cv2.minMaxLoc(cv2.matchTemplate(sub, T, cv2.TM_CCOEFF_NORMED))
    return round(float(s), 3), (r[0] + loc[0] + T.shape[1] / 2, r[1] + loc[1] + T.shape[0] / 2)


def corpus():
    dirs = [G / "L68/live_reader/ladder_unknown", G / "L70/ladder_nav/raw", G / "L70/live", G / "L68/live_reader/fixtures",
            ROOT / "icebow/data/ranked_nav"]
    files = []
    for d in dirs:
        if d.exists():
            files += [p for p in d.iterdir() if p.suffix == ".png"]
    files += [p for p in (G / "L68/live_reader").iterdir() if p.name.startswith("ladder_stop_") and p.suffix == ".png"]
    return sorted(set(files))


if __name__ == "__main__":
    rows, skipped = [], 0
    for p in corpus():
        img = cv2.imread(str(p))
        if img is None or img.shape[:2] != (1600, 900):
            skipped += 1
            continue
        s, xy = score(img)
        rows.append({"file": str(p.relative_to(ROOT)), "claim_all": s, "claim_xy": xy})
    (H / "results").mkdir(exist_ok=True)
    (H / "results" / "claim_all_corpus.json").write_text(json.dumps(rows))
    hits = [r for r in rows if r["claim_all"] >= man["threshold"]]
    print(f"frames scored {len(rows)}, skipped {skipped}; hits (>= {man['threshold']}): {len(hits)}")
    print("lowest hit", min((r["claim_all"] for r in hits), default=None), "highest non-hit",
          max((r["claim_all"] for r in rows if r["claim_all"] < man["threshold"]), default=None))
