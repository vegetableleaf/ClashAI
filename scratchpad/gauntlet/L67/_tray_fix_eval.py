"""Does HandMemory actually close the gap? Replay the bot's own footage through it."""
import sys; sys.path.insert(0,'.'); sys.path.insert(0,'icebow/src')
import cv2, time
from clashrl.config import Config
from clashrl.vision import Vision
from clashrl.student_live import HandMemory
cfg=Config.load(); v=Vision(cfg); mem=HandMemory()
cap=cv2.VideoCapture(sys.argv[1]); fps=float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
fi=used=0; raw_bad=0; fixed_bad=0; frames=0
while used<900:
    ok,fr=cap.read()
    if not ok: break
    fi+=1
    if fi%3: continue
    used+=1; frames+=1
    ids=list(v.recognize_hand(fr))
    t=fi/fps
    st=mem.stabilize(ids,t)
    if any(int(x)<0 for x in ids[:4]): raw_bad+=1
    if any(int(x)<0 for x in st): fixed_bad+=1
cap.release()
print('frames %d  (sampled every %.2fs of real time)' % (frames, 3/fps))
print('  frames with an unreadable slot  BEFORE: %d (%.1f%%)' % (raw_bad, 100*raw_bad/frames))
print('  frames with an unreadable slot  AFTER : %d (%.1f%%)' % (fixed_bad, 100*fixed_bad/frames))
print('  slots filled from memory: %d of %d slot-reads (%.1f%%)' % (mem.filled, mem.seen, 100*mem.filled/max(mem.seen,1)))
