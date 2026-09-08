"""L67g: where does a goblin barrel LAND, relative to where it is seen mid-air?

Label-free ground truth: the goblins spawn AT the landing point, so the centroid of goblin detections in the
~1.5 s after a barrel track ends is the landing. Owner's report: the bot aims The Log at the barrel's current
airborne position instead. This measures (a) how far mid-air position is from the landing, and (b) whether
"the nearer of my princess towers" predicts the landing well enough to aim at.
"""
import sys, json
from pathlib import Path
import numpy as np, cv2
REPO = Path.cwd(); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"icebow"/"src"))
from clashrl.config import Config
from clashrl.actions import ActionSpace
from clashrl.replay_mine import load_detector

cfg = Config.load(); det = load_detector(cfg); warp = ActionSpace(cfg).warp
conf = float(cfg.get("observation", "detector_conf", default=0.35))
# the detector names a body by its CARD, so a barrel's goblins come back as "goblins" (plural) --
# the first run of this probe looked for "goblin"/"spear_goblin" and matched 0 boxes in 2 sessions.
GOB = {"goblins", "goblins_hero", "goblin_gang", "spear_goblins"}
rows = []
for s in sys.argv[1:]:
    cap = cv2.VideoCapture(str(Path("icebow/data/sessions")/s/"video.mp4"))
    per = {}
    fi = -1
    while True:
        ok, fr = cap.read()
        if not ok: break
        fi += 1
        if fi % 3: continue
        ds = det.detect(fr, conf=conf)
        b = [d for d in ds if str(d.cls).startswith("goblin_barrel") and not str(d.cls).endswith("aoe")]
        g = [d for d in ds if str(d.cls) in GOB]
        if b or g:
            per[fi] = {"barrels": [(float(d.cx), float(d.gy)) for d in b],
                       "goblins": [(float(d.cx), float(d.gy)) for d in g]}
    cap.release()
    frames = sorted(per)
    for f in frames:
        if not per[f]["barrels"]:
            continue
        bx, by = per[f]["barrels"][0]
        later = [per[k]["goblins"] for k in frames if 0 < k - f <= 18 and per[k]["goblins"]]
        if not later:
            continue
        pts = [p for grp in later[:3] for p in grp]
        gx, gy = float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))
        b_b = warp.frame_to_board(bx, by); g_b = warp.frame_to_board(gx, gy)
        rows.append({"session": s, "frame": f, "barrel_board": [round(v,4) for v in b_b],
                     "goblins_board": [round(v,4) for v in g_b], "n_goblin_pts": len(pts),
                     "err_tiles": round(float(np.hypot((b_b[0]-g_b[0])*18.0, (b_b[1]-g_b[1])*32.0)), 2)})
    print(s, "barrel->goblin pairs:", sum(1 for r in rows if r["session"] == s), flush=True)
Path("scratchpad/gauntlet/L67/barrel_landing.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
if rows:
    e = [r["err_tiles"] for r in rows]
    print(json.dumps({"pairs": len(rows), "median_err_tiles": round(float(np.median(e)),2),
                      "p90": round(float(np.percentile(e,90)),2), "max": round(max(e),2)}))
