"""DRY-RUN replay-list navigation: classify screens only, never tap (L74 replay_rec). See NOTES.md "Navigation plan".

    # offline, on saved 900x1600 screenshots:
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/nav_dryrun.py --png a.png b.png
    # on the device (owner OK; read-only `adb exec-out screencap` every --every s), the owner navigates by hand:
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/nav_dryrun.py --device --every 2 --seconds 120

Each screen is classified by BOTH existing classifiers (ladder_nav.Classifier: results / main / popup_x / modes /
loading ...; friend_nav.Classifier: social / battle_type / ...) and mapped to the replay-plan step it implies with the
tap the future navigator WOULD make (`would_tap`, a plan entry -- nothing is sent). The TV Royale screens have no
templates yet: every screen both classifiers call unknown is saved to --save-dir, so the owner's by-hand pass yields
the PNGs that templates (L70/ladder_nav/templates/_build.py convention) get cut from.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = HERE.parents[1] / "L68" / "live_reader"
sys.path.insert(0, str(LIVE))

# step -> what the navigator would do there. Only "main" and "results" exist as templates today (ladder_nav);
# the tv_* screens are TO BUILD from the dry-run captures. The in-replay state is NOT a screen template: the memory
# reader's battle_active + both-hands-visible frames say it (recorder.py).
PLAN = {
    "main": "tap the TV Royale entry (Battle tab; exact button TO MEASURE from captures)",
    "tv_list": "open the channel dropdown once, pick the highest Ranked league channel; then tap the first replay "
               "row that is not greyed (grey = watched, TV_Royale wiki)",
    "tv_channels": "tap the target channel row",
    "replay": "no taps; recorder.py runs until battle_end",
    "results": "tap results_ok (ladder_nav TARGETS) -> back to tv_list",
    "popup_x": "tap the red X (ladder_nav close_x)",
    "loading": "wait",
    "conn_lost": "STOP (ladder_nav rule: never kick the owner's other device)",
    "content_update": "STOP (the owner restarts the game)",
}


def classify(img, ladder, friend) -> dict:
    a = ladder.classify(img)
    b = friend.classify(img)
    screen = a["screen"] if a["screen"] not in ("unknown", "nograb") else b["screen"]
    return dict(screen=screen, ladder=a["screen"], friend=b["screen"], would_tap=PLAN.get(screen))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--png", nargs="+")
    src.add_argument("--device", action="store_true")
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--save-dir", default=str(HERE.parents[3] / "icebow" / "data" / "replay_rec" / "screens"))
    a = ap.parse_args()
    import cv2
    from ladder_nav import Classifier as LadderC
    from friend_nav import Classifier as FriendC
    ladder, friend = LadderC(), FriendC()
    if a.png:
        for p in a.png:
            print(json.dumps(dict(png=p, **classify(cv2.imread(p), ladder, friend))))
        return 0
    from ladder_nav import grab                    # read-only screencap; no input command exists in this script
    import live_play as lp
    save = Path(a.save_dir)
    save.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    while time.time() - t0 < a.seconds:
        img = grab(lp.ADB)
        r = classify(img, ladder, friend)
        if r["screen"] == "unknown" and img is not None:
            r["saved"] = str(save / f"unknown_{time.strftime('%H%M%S')}.png")
            cv2.imwrite(r["saved"], img)
        print(json.dumps(dict(t=round(time.time() - t0, 1), **r)), flush=True)
        time.sleep(a.every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
