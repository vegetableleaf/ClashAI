import sys, collections; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, numpy as np
from clashrl.config import Config
from clashrl.vision import Vision
from clashrl.cards import CardDB
cfg=Config.load(); v=Vision(cfg); db=CardDB(path='icebow/config/cards.yaml')
keys=list(v.deck_keys)
cost={}
for i,k in enumerate(keys):
    c=db.elixir(k.replace('_evo',''))
    cost[i]=float(c or 0)
cap=cv2.VideoCapture(sys.argv[1])
fi=used=0
agg=collections.defaultdict(list)   # (card, affordable) -> scores
bright=collections.defaultdict(list)
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
        if not crop.size: continue
        idx,score=v.match_card(crop)
        if idx<0: continue                       # only SUCCESSFUL reads: we know the identity
        aff = cost.get(idx,0) <= el+1e-6
        agg[(keys[idx],aff)].append(float(score))
        bright[(keys[idx],aff)].append(float(crop.mean()))
cap.release()
print('%-14s %-10s %5s %7s %8s' % ('card','affordable','n','score','brightness'))
for (k,aff),v2 in sorted(agg.items()):
    if len(v2)<8: continue
    print('%-14s %-10s %5d %7.3f %8.1f' % (k, str(aff), len(v2), float(np.mean(v2)), float(np.mean(bright[(k,aff)]))))
