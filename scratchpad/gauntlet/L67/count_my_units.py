"""L67h: did the bot PLAY at all? Count MY units in an overlay clip -- evidence without stdout.

The play_*.log file records only state transitions, so a frozen run and a 70-play run look identical in it.
The overlay clip does not: every card the bot deploys puts a body on MY side of the board. Run the detector
over the clip, tag teams the way the live path does, and count distinct MY-side bodies over time. A run that
never played shows towers and nothing else.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))

from clashrl.cards import CardDB                                    # noqa: E402
from clashrl.config import Config                                   # noqa: E402
from clashrl.replay_mine import TeamTracker, load_detector, own_card_bases   # noqa: E402

clip = Path(sys.argv[1])
every = int(sys.argv[2]) if len(sys.argv) > 2 else 10
cfg = Config.load()
det = load_detector(cfg)
db = CardDB(path=Path("icebow/config/cards.yaml"))
tracker = TeamTracker(own_cards=own_card_bases(db))
conf = float(cfg.get("observation", "detector_conf", default=0.35))

cap = cv2.VideoCapture(str(clip))
fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
fi, used, mine_frames, seen = -1, 0, 0, {}
prev, events, timeline = set(), [], []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    fi += 1
    if fi % every:
        continue
    used += 1
    dets = tracker.tag(det.detect(fr, conf=conf), fi / max(fps, 1e-6))
    mine = [d for d in dets if str(d.team) == "mine"]
    if mine:
        mine_frames += 1
    cur = {str(d.cls) for d in mine}
    for c in cur - prev:                       # class absent last sample, present now ~= a deploy
        events.append((fi / max(fps, 1e-6), c))
    prev = cur
    timeline.append((fi / max(fps, 1e-6), len(cur)))
    for d in mine:
        seen[str(d.cls)] = seen.get(str(d.cls), 0) + 1
cap.release()
print(f"clip {clip.name}: {used} sampled frames over {fi / max(fps,1e-6):.0f}s")
print(f"frames with ANY of my units: {mine_frames} ({100.0*mine_frames/max(used,1):.1f}%)")
print("my classes seen:", sorted(seen.items(), key=lambda kv: -kv[1])[:10])
dur = fi / max(fps, 1e-6)
print(f"approx deploy events: {len(events)} over {dur:.0f}s = {60.0*len(events)/max(dur,1):.1f}/min "
      f"(pro 8-10.5/min; the 18:38 student run measured 9.1/min)")
print("first 12 events (s, card):", [(round(t, 1), c) for t, c in events[:12]])
gaps = [round(events[i+1][0]-events[i][0], 1) for i in range(len(events)-1)]
print("gaps between events (s):", gaps)
