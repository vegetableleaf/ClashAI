"""Handedness check for the i=1 rotation: per-card x distribution of the TEAM's (blue) placements,
i=0 half (plays_ext.csv, as served) vs i=1 half (plays_ext_i1.csv, rotated x'=18-x, y'=32-y).
A wrong transform (vertical mirror) would flip any left/right asymmetry. usage: handedness.py <deck>"""
import sys, csv, collections, math
from pathlib import Path
deck = sys.argv[1]
d = Path(f"C:/Users/benpe/ClashBot/{deck}/data/royaleapi/crawl2")
def load(fn, rotate):
    out = collections.defaultdict(list); tags = set()
    for r in csv.DictReader(open(d / fn, encoding="utf-8")):
        if r.get("attr_ability") == "1" or r["x_units"] in ("", "None"): continue
        x, y = int(r["x_units"]) / 1000, int(r["y_units"]) / 1000
        if rotate: x, y = 18 - x, 32 - y
        out[(r["attr_s"], r["attr_card"])].append((x, y)); tags.add(r["replay_tag"])
    return out, tags
a, ta = load("plays_ext.csv", False); b, tb = load("plays_ext_i1.csv", True)
print(f"{deck}: i=0 {len(ta)} replays, i=1 {len(tb)} replays (rotated)")
def stats(v):
    xs = [p[0] for p in v]; ys = [p[1] for p in v]; n = len(v)
    return n, sum(xs)/n, sum(x < 9 for x in xs)/n, sum(ys)/n, sum(y > 16 for y in ys)/n
print(f"{'side':5} {'card':18} {'n0':>6} {'mean_x0':>7} {'left0':>6} {'y0':>6} {'top0':>5} | {'n1':>6} {'mean_x1':>7} {'left1':>6} {'y1':>6} {'top1':>5} | {'dLeft':>6} {'z':>5}")
tot = 0; flips = 0; rows = []
for k in sorted(set(a) | set(b), key=lambda k: -len(a.get(k, []))):
    if len(a.get(k, [])) < 30 or len(b.get(k, [])) < 30: continue
    n0, mx0, l0, y0, t0 = stats(a[k]); n1, mx1, l1, y1, t1 = stats(b[k])
    p = (l0 * n0 + l1 * n1) / (n0 + n1); se = math.sqrt(p * (1 - p) * (1 / n0 + 1 / n1)) or 1e-9
    z = (l1 - l0) / se; tot += 1; flips += abs(z) > 3
    print(f"{k[0]:5} {k[1]:18} {n0:6d} {mx0:7.2f} {l0:6.3f} {y0:6.2f} {t0:5.2f} | {n1:6d} {mx1:7.2f} {l1:6.3f} {y1:6.2f} {t1:5.2f} | {l1-l0:+6.3f} {z:5.1f}")
print(f"cards compared {tot}, |z|>3 on left-fraction: {flips}")
# mirror alternative: x unchanged -> left1_mirror = 1 - left1(rotated) ; report which transform agrees better overall
sa = sum(abs(stats(b[k])[2] - stats(a[k])[2]) for k in a if k in b and len(a[k]) >= 30 and len(b[k]) >= 30)
sm = sum(abs((1 - stats(b[k])[2]) - stats(a[k])[2]) for k in a if k in b and len(a[k]) >= 30 and len(b[k]) >= 30)
print(f"sum |dLeft| rotation {sa:.3f} vs mirror {sm:.3f}")
