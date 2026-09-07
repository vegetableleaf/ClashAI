p = "scratchpad/gauntlet/L66/deckid.py"
s = open(p, encoding="utf-8").read()
old = "        rank = sorted(per.items(), key=lambda kv: -kv[1])\n        out.append((rank[0][0], rank[0][1], rank[1][0], rank[1][1]))\n    return out"
new = """        rank = sorted(per.items(), key=lambda kv: -kv[1])
        out.append((rank[0][0], rank[0][1], rank[1][0], rank[1][1]))
    return out


def slot_card_scores(frame: np.ndarray, T, names: list[str]) -> list[dict]:
    \"\"\"Every card's score in every slot, not just each slot's top two.

    profile.py's first version kept only the argmax and runner-up, so a card that was never any slot's
    best guess got no score at all and defaulted to zero -- which made a known-icebow video read
    worst_icebow = 0.000, indistinguishable from a video of some other deck. The scores are all computed
    anyway; throwing them away was the bug. Cost is identical.\"\"\"
    h, w = frame.shape[:2]
    out = []
    for (x0, y0, x1, y1) in SLOTS:
        crop = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        if crop.size == 0:
            out.append({}); continue
        g = cv2.resize(prep(crop), (CROP_W, CROP_H))
        per: dict[str, float] = {}
        for tset, nm in zip(T, names):
            for t in tset:
                if t.shape[0] > CROP_H or t.shape[1] > CROP_W:
                    continue
                v = float(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED).max())
                if v > per.get(nm, -2):
                    per[nm] = v
        out.append(per)
    return out"""
assert s.count(old) == 1
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new, 1))

q = "scratchpad/gauntlet/L66/profile.py"
t = open(q, encoding="utf-8").read()
t = t.replace("from deckid import ICEBOW, in_battle, load_templates, slot_scores        # noqa: E402",
              "from deckid import ICEBOW, in_battle, load_templates, slot_card_scores   # noqa: E402")
t = t.replace("""        for (c, s, r, rs) in slot_scores(f, T, names):
            if s > best.get(c, -2):
                best[c] = s
            if rs > best.get(r, -2):          # runner-up counts too: the card was seen, just not top
                best[r] = rs""",
"""        for per in slot_card_scores(f, T, names):
            for card, sc in per.items():
                if sc > best.get(card, -2):
                    best[card] = sc""")
t = t.replace('    ice = {c: round(best.get(c, 0.0), 3) for c in ICEBOW}',
              '    ice = {c: round(best.get(c, 0.0), 3) for c in ICEBOW}   # every card now HAS a score')
open(q, "w", encoding="utf-8", newline="\n").write(t)
print("ok")
