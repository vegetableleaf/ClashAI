"""Cut the TV Royale / replay-viewer templates from 900x1600 MuMu captures (L70/ladder_nav/templates/_build.py style).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/tv_templates.py [--check]

Captures: icebow/data/replay_rec/screens/ (nav_dryrun.py --device; git-ignored). Templates + manifest.json go to
icebow/data/replay_rec/templates/ (git-ignored, never staged). --check: classify every capture with the result.
Built from the 2026-10-08 21:0x owner pass (replay viewer only -- the TV Royale menu screens were not saved: the
old nav_dryrun saved only screens no classifier knew, and ladder_nav calls any screen with a red X `popup_x`).
TODO after the next capture pass (nav_dryrun.py --device now saves EVERY screen): add the SPEC rows marked
TV_SCREENS below -- tv_entry (the button on the main screen), tv_list_hdr, tv_channel_btn, tv_channels_hdr, one
tvch_<tier> label per channel in tv_nav.CHANNELS, tv_row_play, and rp_exit (the end-of-replay screen's way out).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[3] / "icebow" / "data" / "replay_rec"
RAW, OUT = DATA / "screens", DATA / "templates"
# name: (capture, box x0 y0 x1 y1, search region, threshold)
SPEC = {
    # replay viewer controls (shown after a tap; hidden again after a few seconds)
    "rp_close": ("unknown_210535.png", (18, 645, 92, 715), (0, 560, 160, 800), 0.85),
    "rp_pause": ("unknown_210535.png", (18, 765, 92, 835), (0, 680, 160, 900), 0.85),
    "spd_x1":   ("unknown_210528.png", (20, 885, 92, 930), (0, 850, 140, 960), 0.90),
    "spd_x05":  ("unknown_210531.png", (20, 885, 92, 930), (0, 850, 140, 960), 0.90),
    "spd_x4":   ("unknown_210535.png", (20, 885, 92, 930), (0, 850, 140, 960), 0.90),
    "rp_rewind": ("unknown_210535.png", (180, 1115, 290, 1190), (100, 1050, 400, 1260), 0.85),
}
TV_SCREENS = ("tv_entry", "tv_list_hdr", "tv_channel_btn", "tv_channels_hdr", "tv_row_play", "rp_exit")


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    man = {}
    for n, (src, b, reg, thr) in SPEC.items():
        img = cv2.imread(str(RAW / src))
        if img is None:
            raise SystemExit(f"capture missing: {RAW / src}")
        cv2.imwrite(str(OUT / f"{n}.png"), img[b[1]:b[3], b[0]:b[2]])
        man[n] = {"file": f"{n}.png", "source": src, "box": b, "region": reg, "threshold": thr}
    (OUT / "manifest.json").write_text(json.dumps({"frame": [900, 1600], "templates": man}, indent=1))
    return len(man)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    print("built", build(), "templates in", OUT)
    if a.check:
        import tv_nav
        c = tv_nav.Classifier()
        for p in sorted(RAW.glob("*.png")):
            r = c.classify(cv2.imread(str(p)))
            print(p.name, r["screen"], r.get("speed"), {k: v for k, v in r["scores"].items() if v > 0.6})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
