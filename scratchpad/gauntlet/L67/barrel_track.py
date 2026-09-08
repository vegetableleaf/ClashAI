"""L67h: how far does a goblin barrel TRAVEL after the frame you see it in? Owner's live report, measured.

Owner (2026-09-08): "when the model detects a goblin barrel mid-air, it tries to log the goblin barrel's
current position even though the barrel itself isn't the target, it's the goblins that come out after it
lands." The first attempt at this measured the barrel against the CENTROID OF LATER GOBLIN DETECTIONS and is
RETRACTED: those goblins land at board y 0.512 (the river) and only 38% sit within 3 tiles of my princess
row, i.e. the probe was associating Goblin Gang / spear goblins with a barrel they never came from.

This version needs no cross-class association. A barrel is TRACKED across frames by proximity; the landing
estimate is its LAST sighting, and the question the owner asked -- how wrong is the CURRENT position -- is
answered by the distance from each earlier sighting to that last one. Also reported: how close the last
sighting sits to my princess towers, which is what an aim rule would target instead.

usage: python scratchpad/gauntlet/L67/barrel_track.py <session>... --out <json>
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))

import cv2                                                    # noqa: E402
from clashrl.actions import ActionSpace                       # noqa: E402
from clashrl.config import Config                             # noqa: E402
from clashrl.replay_mine import load_detector                 # noqa: E402

TILES_X, TILES_Y = 18.0, 32.0
MY_PRINCESS_Y = 0.797                     # board frame, me at the bottom (obs_contract docstring)
LINK_TILES = 6.0                          # a barrel moves fast; link generously, it is the only barrel class
GAP_FRAMES = 4                            # sampled frames a track may skip before it is considered landed


def main() -> int:
    sessions = [s for s in sys.argv[1:] if not s.startswith("--")]
    out_p = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("barrel_track.json")
    cfg = Config.load()
    det = load_detector(cfg)
    if not det.available:
        raise SystemExit("detector weights not found")
    warp = ActionSpace(cfg).warp
    conf = float(cfg.get("observation", "detector_conf", default=0.35))

    tracks_out = []
    for s in sessions:
        cap = cv2.VideoCapture(str(REPO / "icebow" / "data" / "sessions" / s / "video.mp4"))
        if not cap.isOpened():
            print(f"skip {s}", flush=True)
            continue
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 12.0)
        live: list[dict] = []
        done: list[dict] = []
        fi = -1
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            fi += 1
            if fi % 2:
                continue
            ds = [d for d in det.detect(fr, conf=conf)
                  if str(d.cls).startswith("goblin_barrel") and not str(d.cls).endswith("aoe")]
            pts = [warp.frame_to_board(float(d.cx), float(d.gy)) for d in ds]
            for tr in live:
                tr["miss"] = tr.get("miss", 0) + 1
            for (bx, by) in pts:
                best, bd = None, LINK_TILES
                for tr in live:
                    lx, ly = tr["pts"][-1]
                    d = float(np.hypot((bx - lx) * TILES_X, (by - ly) * TILES_Y))
                    if d < bd:
                        best, bd = tr, d
                if best is None:
                    live.append({"pts": [(bx, by)], "f0": fi, "f1": fi, "miss": 0, "sess": s})
                else:
                    best["pts"].append((bx, by))
                    best["f1"] = fi
                    best["miss"] = 0
            keep = []
            for tr in live:
                (done if tr["miss"] > GAP_FRAMES else keep).append(tr)
            live = keep
        done += live
        cap.release()
        for tr in done:
            if len(tr["pts"]) < 2:
                continue
            p = np.array(tr["pts"])
            last = p[-1]
            errs = np.hypot((p[:-1, 0] - last[0]) * TILES_X, (p[:-1, 1] - last[1]) * TILES_Y)
            tracks_out.append({"session": s, "sightings": int(len(p)),
                               "dur_s": round((tr["f1"] - tr["f0"]) / max(fps, 1e-6), 2),
                               "first": [round(float(v), 4) for v in p[0]],
                               "last": [round(float(v), 4) for v in last],
                               "first_to_last_tiles": round(float(errs[0]), 2),
                               "mean_sighting_err_tiles": round(float(errs.mean()), 2),
                               "last_dy_to_my_princess_tiles": round(float(abs(last[1] - MY_PRINCESS_Y) * TILES_Y), 2)})
        print(f"{s}: {sum(1 for t in tracks_out if t['session'] == s)} barrel tracks", flush=True)

    if tracks_out:
        f2l = np.array([t["first_to_last_tiles"] for t in tracks_out])
        msе = np.array([t["mean_sighting_err_tiles"] for t in tracks_out])
        dy = np.array([t["last_dy_to_my_princess_tiles"] for t in tracks_out])
        summary = {"tracks": len(tracks_out),
                   "sightings_median": float(np.median([t["sightings"] for t in tracks_out])),
                   "first_to_last_tiles": {"median": round(float(np.median(f2l)), 2),
                                           "p90": round(float(np.percentile(f2l, 90)), 2)},
                   "mean_sighting_err_tiles": {"median": round(float(np.median(msе)), 2),
                                               "p90": round(float(np.percentile(msе, 90)), 2)},
                   "last_sighting_dy_to_my_princess": {"median": round(float(np.median(dy)), 2),
                                                       "frac_within_3_tiles": round(float((dy < 3).mean()), 3)}}
        print(json.dumps(summary), flush=True)
    else:
        summary = {"tracks": 0}
    out_p.write_text(json.dumps({"summary": summary, "tracks": tracks_out}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
