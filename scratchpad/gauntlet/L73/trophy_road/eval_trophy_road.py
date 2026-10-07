"""Accuracy of the trophy-road reward-choice detectors in ladder_nav on
  positives: the owner's two phone screenshots rescaled to 900x1600 (make_positives.variants), full classify(), and
  negatives: every saved 900x1600 live frame (L70 ladder_nav raw, L68 ladder_unknown + stop frames, L73 trophies img).
On a negative, classify() can return a different screen than before 2026-10-07 ONLY if reward_cards() fires (checked
before trophy_road / main) or the colour fallback "green button + blue OK" fires; otherwise it runs the old code path.
So the negatives run just those detectors (~30 ms a frame; the template pass is ~0.9 s and the box is loaded).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/trophy_road/eval_trophy_road.py eval_results.json"""
import json
import sys
from pathlib import Path

import cv2

D = Path(__file__).resolve().parent
sys.path.insert(0, str(D.parents[1] / "L68" / "live_reader"))
sys.path.insert(0, str(D))
import ladder_nav  # noqa: E402
import make_positives  # noqa: E402

cv2.setNumThreads(2)
MAIN = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet")          # raw captures live (untracked) in the main checkout
NEG = (sorted((MAIN / "L70/ladder_nav/raw").glob("*.png")) + sorted((MAIN / "L68/live_reader/ladder_unknown").glob("*.png"))
       + sorted((MAIN / "L68/live_reader").glob("*_stop_*.png")) + sorted((MAIN / "L73/trophies/img").glob("*.png")))


def main():
    out = {"positives": {}, "negatives": {}}
    clf = ladder_nav.Classifier()
    for src, kind in (("owner_choose_reward.webp", "choice"), ("owner_path_choose.webp", "path")):
        for n, img in make_positives.variants(cv2.imread(str(D / src))).items():
            s = clf.classify(img)
            out["positives"][f"{kind}_{n}"] = {"screen": s["screen"], "choose": s.get("choose"), "cards": s.get("cards"),
                                               "bottom_ok_template": s["scores"].get("bottom_ok"),
                                               "collect_template": s["scores"].get("collect")}
    skipped = 0
    for p in NEG:
        img = cv2.imread(str(p))
        if img is None or img.shape[:2] != (1600, 900):
            skipped += 1                              # sheets / crops: not frames
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        g = ladder_nav.green_buttons(hsv)
        e = out["negatives"][str(p.relative_to(MAIN))] = {"cards": ladder_nav.reward_cards(img, hsv), "green": g,
                                                          "blue_ok": ladder_nav.blue_ok(hsv) if g else None}
        if g:                                         # a green button: full classify -- is it Collect, or a "Choose"?
            s = clf.classify(img)
            e.update(screen=s["screen"], collect=s.get("collect"), choose=s.get("choose"))
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
    neg = out["negatives"]
    fp_cards = [k for k, v in neg.items() if v["cards"]]
    green = [k for k, v in neg.items() if v["green"]]
    fallback = [k for k, v in neg.items() if v["green"] and v["blue_ok"]]
    print(f"negatives: {len(neg)} frames ({skipped} non-frame images skipped)")
    print(f"  reward_cards fired (-> choose_reward): {len(fp_cards)} {fp_cards}")
    print(f"  green button found: {len(green)} {green}")
    print(f"  green button + blue OK (colour trophy_road fallback): {len(fallback)} {fallback}")
    full = {k: (v["screen"], v["collect"] is not None, v["choose"]) for k, v in neg.items() if v["green"]}
    print(f"  full classify of the green-button frames -> (screen, Collect template hit, Choose): "
          f"{sorted(set(full.values()), key=str)}; Choose found on: {[k for k, v in full.items() if v[2]]}")
    print(f"{'positive':18s} {'screen':14s} {'bottom_ok/collect tpl':22s} Choose button / card centres")
    for k, v in out["positives"].items():
        print(f"{k:18s} {v['screen']:14s} {v['bottom_ok_template']!s:>9} {v['collect_template']!s:>9}    "
              f"{v['choose'] or v['cards']}")


if __name__ == "__main__":
    main()
