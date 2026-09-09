"""Are tray failures the hand-CYCLE ANIMATION? Measure time since the last hand change, failures vs reads."""
import sys, collections; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, numpy as np
from clashrl.config import Config
from clashrl.vision import Vision
cfg=Config.load(); v=Vision(cfg)
cap=cv2.VideoCapture(sys.argv[1]); fps=float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
fi=used=0; hist=[]
EVERY=3                                    # ~0.12 s apart: fine enough to see an animation
while used<900:
    ok,fr=cap.read()
    if not ok: break
    fi+=1
    if fi%EVERY: continue
    used+=1
    ids=list(v.recognize_hand(fr))
    hist.append((fi/fps, tuple(int(x) for x in ids)))
cap.release()
last_change=None; rows=[]
prev_good=None
for t,ids in hist:
    good=tuple(x for x in ids if x>=0)
    if prev_good is not None and good and set(good)!=set(prev_good):
        last_change=t
    if good: prev_good=good
    dt=(t-last_change) if last_change is not None else None
    rows.append((t,ids,dt))
fails=[(t,dt) for t,ids,dt in rows if any(x<0 for x in ids) and dt is not None]
oks=[(t,dt) for t,ids,dt in rows if all(x>=0 for x in ids) and dt is not None]
print('sampled frames %d (every %.2fs)  frames with a bad slot: %d' % (len(rows), EVERY/fps, sum(1 for _,i,_ in rows if any(x<0 for x in i))))
for lo,hi,lab in ((0,0.5,'<0.5s'),(0.5,1.0,'0.5-1s'),(1.0,2.0,'1-2s'),(2.0,99,'>2s')):
    f=sum(1 for _,d in fails if lo<=d<hi); o=sum(1 for _,d in oks if lo<=d<hi)
    if f+o<10: continue
    print('  time since hand change %-7s  n=%4d  failure rate %5.1f%%' % (lab, f+o, 100*f/(f+o)))
