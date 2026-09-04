"""Per-slot crop-centre calibration from recorded live matches: for many frames, find the (dx, dy)
that maximises the template score of each tray slot and the next-preview; report medians.
Measures the misalignment (5cs.7) instead of guessing it."""
import sys, cv2, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config; from clashrl.vision import Vision
cfg = Config.load(sys.argv[1]); v = Vision(cfg); vids = sys.argv[2:]
res = {si: [] for si in range(5)}
for vid in vids:
    cap = cv2.VideoCapture(vid); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); W = int(cap.get(3)); H = int(cap.get(4))
    for fi in range(90, n - 90, max(90, n // 12)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi); ok, fr = cap.read()
        if not ok: continue
        for si, (cx, cy) in enumerate(v.hand_slots):
            best = (-1, 0, 0)
            for dx in range(-4, 13):
                for dy in range(-6, 9):
                    i, s = v.match_card(v.hand_crop(fr, cx + dx / W, cy + dy / H))
                    if s > best[0]: best = (s, dx, dy)
            i0, s0 = v.match_card(v.hand_crop(fr, cx, cy))
            if best[0] >= 0.85: res[si].append((best[1] / W, best[2] / H, s0, best[0]))
        # next preview
        cx, cy = v.next_slot; best = (-1, 0, 0)
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                crop = fr[int((cy + dy / H - v.next_card_h) * H):int((cy + dy / H + v.next_card_h) * H), int((cx + dx / W - v.next_card_w) * W):int((cx + dx / W + v.next_card_w) * W)]
                i, s = v.match_card(crop, top_frac=0.8) if crop.size else (-1, -1)
                if s > best[0]: best = (s, dx, dy)
        crop = fr[int((cy - v.next_card_h) * H):int((cy + v.next_card_h) * H), int((cx - v.next_card_w) * W):int((cx + v.next_card_w) * W)]
        i0, s0 = v.match_card(crop, top_frac=0.8)
        if best[0] >= 0.7: res[4].append((best[1] / W, best[2] / H, s0, best[0]))
    print(vid, "frames scanned", len(range(90, n - 90, max(90, n // 12))), W, "x", H)
for si in range(5):
    a = np.array(res[si]); nm = f"slot {si}" if si < 4 else "next"
    if len(a) == 0: print(nm, "no confident frames"); continue
    base = v.hand_slots[si] if si < 4 else v.next_slot
    print(f"{nm}: n {len(a)}  median shift dx {np.median(a[:,0]):+.4f} dy {np.median(a[:,1]):+.4f} (IQR dx {np.percentile(a[:,0],25):+.4f}..{np.percentile(a[:,0],75):+.4f})  score as-configured median {np.median(a[:,2]):.3f} -> shifted {np.median(a[:,3]):.3f}  => centre [{base[0]+np.median(a[:,0]):.4f}, {base[1]+np.median(a[:,1]):.4f}]")
