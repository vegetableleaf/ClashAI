p = "scratchpad/gauntlet/L66/deckid.py"
s = open(p, encoding="utf-8").read()

old_prep = '''def prep(bgr: np.ndarray) -> np.ndarray:
    """Zero-mean unit-norm vector of a 64x80 BGR crop -- NCC then reduces to a dot product."""
    v = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v'''
new_prep = '''def prep(bgr: np.ndarray) -> np.ndarray:
    """Grayscale float image, kept 2-D: the templates are TIGHTER crops of the card art than a slot box
    is (they exclude the card border and the elixir badge), so a whole-crop dot product compares a card
    against a zoom of a card and scores noise. v1 did exactly that and its calibration showed it: on
    known-icebow footage the non-icebow p90 (0.64-0.69) sat ABOVE the icebow median (0.51-0.57). The
    template has to SLIDE inside the slot, at several scales."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)'''
assert s.count(old_prep) == 1
s = s.replace(old_prep, new_prep)

s = s.replace('''            vecs.append(prep(cv2.resize(im, (TW, TH))))
            names.append(card)
    return np.stack(vecs), names''',
'''            g = prep(im)
            vecs.append([cv2.resize(g, (int(TW * k), int(TH * k))) for k in SCALES])
            names.append(card)
    return vecs, names''')

old_slot = s[s.index('def slot_scores('):s.index('def sample(')]
new_slot = '''def slot_scores(frame: np.ndarray, T, names: list[str]) -> list[tuple[str, float, str, float]]:
    """Per slot: (best card, best score, runner-up card, runner-up score). The runner-up is what makes a
    threshold defensible -- beating every other card by a wide margin is a different claim from edging
    out a lookalike."""
    h, w = frame.shape[:2]
    out = []
    for (x0, y0, x1, y1) in SLOTS:
        crop = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        if crop.size == 0:
            out.append(("", 0.0, "", 0.0)); continue
        g = cv2.resize(prep(crop), (CROP_W, CROP_H))
        per: dict[str, float] = {}
        for tset, nm in zip(T, names):
            best = -2.0
            for t in tset:
                if t.shape[0] > CROP_H or t.shape[1] > CROP_W:
                    continue
                r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                v = float(r.max())
                if v > best:
                    best = v
            if best > per.get(nm, -2):
                per[nm] = best
        rank = sorted(per.items(), key=lambda kv: -kv[1])
        out.append((rank[0][0], rank[0][1], rank[1][0], rank[1][1]))
    return out


'''
s = s.replace(old_slot, new_slot)
s = s.replace('TH, TW = 80, 64',
              'TH, TW = 80, 64\n# The slot box holds the whole card; the art inside it is roughly 60-85% of that, so the template is\n# scaled to a range of fractions of a canonical slot and slid over it.\nCROP_W, CROP_H = 132, 168\nSCALES = (1.10, 1.35, 1.60)')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
