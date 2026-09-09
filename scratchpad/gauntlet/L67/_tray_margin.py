"""Would lowering the threshold be SAFE? On every failing crop, rank all templates and ask whether the
top candidate is the identity the neighbouring frames prove the slot held."""
import sys, collections; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, numpy as np
from clashrl.config import Config
from clashrl.vision import Vision
cfg=Config.load(); v=Vision(cfg); keys=list(v.deck_keys)
thr=float(cfg.get('cards','match_threshold',default=0.5))
cap=cv2.VideoCapture(sys.argv[1])
fi=used=0; per_slot=[[] for _ in range(4)]
while used<300:
    ok,fr=cap.read()
    if not ok: break
    fi+=1
    if fi%15: continue
    used+=1
    for si in range(4):
        crop=v.hand_crop(fr,*v.hand_slots[si])
        if not crop.size:
            per_slot[si].append((-1,-1.0,-1)); continue
        idx,score=v.match_card(crop)
        # rank ALL templates by score, ignoring the threshold
        pack=v._tpl_matrix(v._card_tpls,1.0)
        best=(-1,-9.9)
        if pack is not None:
            M,norms,owner,(fh,fw)=pack
            c=cv2.resize(crop,(fw,fh),interpolation=cv2.INTER_AREA)
            cc=v._center_pc(c.astype(np.float32)).ravel()
            n=np.linalg.norm(cc)+1e-9
            s=(M@cc)/(norms*n)
            j=int(np.argmax(s)); best=(int(owner[j]), float(s[j]))
        per_slot[si].append((idx,float(score),best[0]))
cap.release()
# temporal ground truth: the identity a slot held in the nearest confident frames
tot=fixed=wrong=0
truth_hist=collections.Counter(); slot_hist=collections.Counter()
for si in range(4):
    seq=per_slot[si]
    for i,(idx,score,top) in enumerate(seq):
        if idx>=0: continue
        nb=[seq[j][0] for j in range(max(0,i-3),min(len(seq),i+4)) if seq[j][0]>=0]
        if not nb: continue
        truth=collections.Counter(nb).most_common(1)[0][0]
        tot+=1
        truth_hist[keys[truth] if 0<=truth<len(keys) else str(truth)]+=1
        slot_hist[si]+=1
        if top==truth: fixed+=1
        else: wrong+=1
print('failing slot-reads with a temporal ground truth: %d' % tot)
if tot:
    print('  best-scoring template IS the right card: %d (%.1f%%)' % (fixed,100*fixed/tot))
    print('  best-scoring template is WRONG:          %d (%.1f%%)' % (wrong,100*wrong/tot))
    print('  which CARD the failing slot actually held:', truth_hist.most_common(8))
    print('  which SLOT failed:', sorted(slot_hist.items()))
