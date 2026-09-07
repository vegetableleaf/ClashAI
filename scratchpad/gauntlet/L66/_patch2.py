p = "scratchpad/gauntlet/L66/deckid.py"
s = open(p, encoding="utf-8").read()
s = s.replace(
 'ICEBOW = ("tornado", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight_evo", "the_log", "skeletons")',
 '''# BASE keys. The deck is (tornado, tesla_evo, ice_wizard, x_bow, rocket, knight_evo, the_log, skeletons),
# but an evolved card's hand art is the same art with different framing, and the matcher reads the base
# every time (measured: evo tesla in hand scores 0.73 as "tesla"). Deck IDENTITY does not depend on which
# two slots are evolved, so evo and base fold together here and the evo question is left to the miner.
ICEBOW = ("tornado", "tesla", "ice_wizard", "x_bow", "rocket", "knight", "the_log", "skeletons")
def base_key(n: str) -> str:
    return n[:-4] if n.endswith("_evo") else n''')
s = s.replace('PER_CARD = 6                       # templates kept per card; more is slower, not better (they are near-dupes)',
              'PER_CARD = 4                       # templates kept per card; more is slower, not better (they are near-dupes)')
s = s.replace('SCALES = (1.10, 1.35, 1.60)', 'SCALES = (1.15, 1.45)')
s = s.replace('            vecs.append([cv2.resize(g, (int(TW * k), int(TH * k))) for k in SCALES])\n            names.append(card)',
              '            vecs.append([cv2.resize(g, (int(TW * k), int(TH * k))) for k in SCALES])\n            names.append(base_key(card))')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
