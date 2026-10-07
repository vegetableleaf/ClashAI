"""One-off: make sparse test frames + labels.json + digits.npz from the labelled recorded frames.
Sources live in the main checkout (untracked); we keep only the ROI bands (black elsewhere => tiny PNGs).
Labels were read by eye from contact sheets (main total) and the banner crops (result delta magnitude).
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/trophies/build_digits.py
"""
import glob
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "L68" / "live_reader"))
import trophy_read as tr  # noqa: E402

SRC = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet")
UNK = SRC / "L68/live_reader/ladder_unknown"
MAIN_LABELS = """0 10793|1 10815|2 10904|3 11000|4 11000|5 11031|6 11178|7 11086|8 11118|9 11000|10 11011|11 11030|12 11000
13 11014|14 11119|15 11092|16 11152|17 11152|18 11128|19 11157|20 11190|21 11166|22 11167|23 11109|24 11107|25 11136
26 11084|27 11122|28 11003|29 11130|30 11132|31 11164|32 11132|33 11030|34 11030|35 11038|36 11223|37 11141|38 11117
39 11057|40 11146|41 11000|42 11067|43 11102|44 11155|45 11062|46 11060|47 11062|48 11121|49 11159|50 11189|51 11248
52 10132|53 10132|54 10189|55 10159|56 10159|57 10159|58 10159|59 10159|60 10159|61 10159|62 10159|63 10189"""
# result delta magnitudes (res_1..8 = ladder ClashAI frames, ranked = another mode but same banner/font)
RESULTS = {f"L70/ladder_nav/raw/res_{i}.png": 30 for i in range(1, 9)}
RESULTS.update({"L69/nav/raw_ranked/ranked_results_105635_1_last.png": 28,
                "L69/nav/raw_ranked/ranked_results_120517_1_last.png": 31,
                "L69/nav/raw_ranked/ranked_results_121534_1_last.png": 30,
                "L69/nav/raw_ranked/ranked_results_121856_1_last.png": 30,
                "L69/nav/raw_ranked/ranked_results_122228_1_last.png": 29,
                "L69/nav/raw_ranked/ranked_results_122643_1_last.png": 30,
                "L69/nav/raw_ranked/ranked_results_150349_1_last.png": 30})
NONE_FRAMES = {"L69/nav/raw/results_131619.png": ("result", None)}   # friendly-battle results: no trophy change shown


def sparse(img, y0, y1):
    x0, x1 = (360, 560) if y0 == 300 else (640, 820)   # keep only the ROI window; black elsewhere
    out = np.zeros_like(img)
    out[y0:y1, x0:x1] = img[y0:y1, x0:x1]
    return out


def main():
    (HERE / "img").mkdir(exist_ok=True)
    mainlist = [Path(p) for p in open("C:/Users/benpe/AppData/Local/Temp/mainlist.txt").read().split("\n")]
    labels = {}
    for tok in MAIN_LABELS.replace("\n", "|").split("|"):
        i, v = tok.split()
        n = f"main_{int(i):02d}.png"
        cv2.imwrite(str(HERE / "img" / n), sparse(cv2.imread(str(mainlist[int(i)])), 300, 390))
        labels[n] = {"kind": "main", "value": int(v), "src": mainlist[int(i)].name}
    live = cv2.imread(str(HERE / "img" / "live_idle.png"))   # full frame from `adb exec-out screencap -p`, deleted after use
    assert live is not None, "put a main-menu screencap at img/live_idle.png (value 11222) first"
    cv2.imwrite(str(HERE / "img" / "main_live_idle.png"), sparse(live, 300, 390))
    labels["main_live_idle.png"] = {"kind": "main", "value": 11222, "src": "adb screencap 2026-10-07 (read-only)"}
    (HERE / "img" / "live_idle.png").unlink()
    for k, (p, v) in enumerate(RESULTS.items()):
        n = f"result_{k:02d}.png"
        cv2.imwrite(str(HERE / "img" / n), sparse(cv2.imread(str(SRC / p)), 900, 990))
        labels[n] = {"kind": "result", "value": v, "src": p}
    for p, (kind, v) in NONE_FRAMES.items():
        n = "result_none_friendly.png"
        cv2.imwrite(str(HERE / "img" / n), sparse(cv2.imread(str(SRC / p)), 900, 990))
        labels[n] = {"kind": kind, "value": v, "src": p}
    (HERE / "labels.json").write_text(json.dumps(labels, indent=1))
    # digit bank from the main frames only (the result frames stay an independent test set)
    seen, X, y = set(), [], []
    for n, e in labels.items():
        if e["kind"] != "main":
            continue
        g = tr.glyphs(cv2.imread(str(HERE / "img" / n)), tr.MAIN_ROI)
        s = str(e["value"])
        if len(g) != len(s):
            print("SEGMENT MISMATCH", n, len(g), s)
            continue
        for v, d in zip(s, g):
            d8 = np.round(d * 255).astype(np.uint8)
            key = (v, d8.tobytes())
            if key not in seen:
                seen.add(key)
                X.append(d8)
                y.append(int(v))
    np.savez_compressed(HERE / "digits.npz", X=np.array(X), y=np.array(y))
    print("exemplars", len(X), "per digit", np.bincount(y, minlength=10))


if __name__ == "__main__":
    main()
