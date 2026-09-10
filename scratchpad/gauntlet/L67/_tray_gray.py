"""Does matching on LUMINANCE beat colour matching for dimmed (unaffordable) cards?

The dim is a desaturation -- colour mixed toward grey -- which MIXES channels, so the per-channel centring
that makes TM_CCOEFF_NORMED brightness-invariant does not cancel it. Grayscale should be far less affected.
Graded against temporal ground truth: the identity the neighbouring confident frames prove the slot held.
"""
import sys, collections; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, numpy as np
from clashrl.config import Config
from clashrl.vision import Vision
cfg=Config.load(); v=Vision(cfg); keys=list(v.deck_keys)
thr=float(cfg.get('cards','match_threshold',default=0.5))

def gray_scores(crop):
    pack=v._tpl_matrix(v._card_tpls,1.0)
    if pack is None: return -1,-9.9
    M,norms,owner,(fh,fw)=pack
    c=cv2.resize(crop,(fw,fh),interpolation=cv2.INTER_AREA)
    g=cv2.cvtColor(c,cv2.COLOR_BGR2GRAY).astype(np.float32)
    g=(g-g.mean()).ravel(); gn=np.linalg.norm(g)+1e-9
    # rebuild template matrix in gray from the same packed templates
    best=(-1,-9.9)
    for j in range(M.shape[0]):
        t=M[j].reshape(fh,fw,3)
        tg=t.sum(-1)/3.0
        tg=(tg-tg.mean()).ravel()
        s=float(np.dot(tg,g)/((np.linalg.norm(tg)+1e-9)*gn))
        if s>best[1]: best=(int(owner[j]),s)
    return best

cap=cv2.VideoCapture(sys.argv[1]); fi=used=0; per=[[] for _ in range(4)]
while used<200:
    ok,fr=cap.read()
    if not ok: break
    fi+=1
    if fi%15: continue
    used+=1
    for si in range(4):
        crop=v.hand_crop(fr,*v.hand_slots[si])
        if not crop.size: per[si].append((-1,-1.0,-1,-1.0)); continue
        idx,sc=v.match_card(crop)
        gi,gs=gray_scores(crop)
        per[si].append((idx,float(sc),gi,float(gs)))
cap.release()
col_ok=col_bad=gr_ok=gr_bad=fails=0
for si in range(4):
    seq=per[si]
    for i,(idx,sc,gi,gs) in enumerate(seq):
        nb=[seq[j][0] for j in range(max(0,i-3),min(len(seq),i+4)) if seq[j][0]>=0]
        if not nb: continue
        truth=collections.Counter(nb).most_common(1)[0][0]
        if idx<0:
            fails+=1
            if gs>=thr and gi==truth: gr_ok+=1
            elif gs>=thr: gr_bad+=1
        else:
            if idx==truth: col_ok+=1
            else: col_bad+=1
print('colour matcher on SUCCESSFUL reads: right %d, wrong %d (%.1f%% correct)' % (col_ok,col_bad,100*col_ok/max(col_ok+col_bad,1)))
print('reads the colour matcher FAILED: %d' % fails)
print('  of those, GRAYSCALE clears threshold AND is right: %d (%.1f%%)' % (gr_ok, 100*gr_ok/max(fails,1)))
print('  of those, GRAYSCALE clears threshold but is WRONG: %d (%.1f%%)' % (gr_bad, 100*gr_bad/max(fails,1)))
