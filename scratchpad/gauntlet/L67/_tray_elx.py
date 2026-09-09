import sys, json, collections; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, numpy as np
from clashrl.config import Config
from clashrl.vision import Vision
cfg=Config.load(); v=Vision(cfg)
thr=float(cfg.get('cards','match_threshold',default=0.5))
cap=cv2.VideoCapture(sys.argv[1])
fi=used=0; rows=[]
while used<300:
    ok,fr=cap.read()
    if not ok: break
    fi+=1
    if fi%15: continue
    used+=1
    el=float(v.read_elixir(fr))
    ids=list(v.recognize_hand(fr))
    for si in range(4):
        crop=v.hand_crop(fr,*v.hand_slots[si])
        idx,score=v.match_card(crop) if crop.size else (-1,-1.0)
        rows.append((el, si, int(ids[si]) if si<len(ids) else -1, float(score)))
cap.release()
el=np.array([r[0] for r in rows]); bad=np.array([r[2]<0 for r in rows]); sc=np.array([r[3] for r in rows])
print('slot-reads: %d   overall failure %.1f%%' % (len(rows), 100*bad.mean()))
print('failure rate by ELIXIR:')
for lo,hi in ((0,2),(3,4),(5,6),(7,8),(9,10)):
    m=(el>=lo)&(el<=hi)
    if m.sum()<20: continue
    print('  elixir %2d-%2d  n=%4d  fail %5.1f%%   mean score %.3f' % (lo,hi,int(m.sum()),100*bad[m].mean(),sc[m].mean()))
