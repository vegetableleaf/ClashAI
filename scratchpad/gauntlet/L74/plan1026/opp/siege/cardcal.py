"""Per-card calibration from a siege_a --dump: (i) card CHOICE on play rows with the card in hand (human frequency vs the model's
mean probability), (ii) card x TIMING on slot rows with the card in hand (model expected plays of the card = sum h * p(card) vs
the human's actual plays of it), inside X-Bow windows (0-10 s) vs outside.  python cardcal.py DUMP.npz [CARD ...]"""
import sys
import numpy as np
z = np.load(sys.argv[1])
voc = list(z["vocab"])
cards = sys.argv[2:] or ["earthquake", "rocket", "pekka", "electro-giant", "mega-knight", "valkyrie", "knight", "tesla", "cannon",
                         "the-log", "fireball", "ice-golem", "arrows"]
hand, p4, h, y = z["hand"], z["p4"], z["h"], z["y_card"]
play, cok, sok, grp = z["play"], z["card_ok"], z["slot_ok"], z["grp"]
print("| card | where | choice rows | human P(card) | model mean p | slot rows | human plays | model expected (sum h*p) | ratio |")
print("|---|---|---|---|---|---|---|---|---|")
for c in cards:
    if c not in voc:
        continue
    ci = voc.index(c)
    inh = (hand == ci)
    has = inh.any(1)
    pc = (p4 * inh).sum(1)
    for nm, g in (("window", grp >= 1), ("outside", grp == 0)):
        ch = cok & has & g
        sl = sok & has & g
        hp = int((play & g & (y == ci)).sum())
        ex = float((h[sl] * pc[sl]).sum())
        print(f"| {c} | {nm} | {ch.sum()} | {(y[ch] == ci).mean():.3f} | {pc[ch].mean():.3f} | {sl.sum()} | {hp} | {ex:.0f} | {ex / max(hp, 1):.2f} |")
