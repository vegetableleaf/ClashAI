"""stepsim.py -- crforge Displacement.displace proposal (step clamp, truncating scale, avoidance blend) in Python, no push / GridMove.
python stepsim.py SX SY BLEND BUDGET  (prints the end point for every cell-centre aim within 2 cells)"""
import math, sys


def td(a, b):
    return 0 if b == 0 else int(a / b) if abs(a) < 2 ** 52 else (abs(a) // abs(b)) * (1 if (a >= 0) == (b > 0) else -1)


def isqrt(n): return math.isqrt(n)


def normalize(v, scale):
    L = isqrt(v[0] * v[0] + v[1] * v[1])
    if L: v[0], v[1] = td(v[0] * scale, L), td(v[1] * scale, L)
    return L


def step(sx, sy, tx, ty, budget, blend=0):
    dx, dy = tx - sx, ty - sy
    d = max(isqrt(dx * dx + dy * dy), 1)
    st = min(budget, d, 250)
    p = [td(td(dx << 8, d) * st, 256), td(td(dy << 8, d) * st, 256)]
    if blend:
        b = max(min(blend, 256), -256)
        f = 256 - abs(b)
        w = [((f * p[0]) >> 8) + ((b * p[1]) >> 8), ((f * p[1]) >> 8) + ((-(p[0] * b)) >> 8)]
        normalize(w, st)
        p = w
    return sx + p[0], sy + p[1]


if __name__ == '__main__':
    assert step(7660, 17112, 7250, 17250, 90, -60) == (7570, 17113), step(7660, 17112, 7250, 17250, 90, -60)  # 170912@745 crforge
    assert step(7746, 17139, 6250, 17250, 90, -70) == (7660, 17112)  # 170912@744 crforge
    sx, sy, bl, bud = (int(a) for a in sys.argv[1:5])
    for r in range(sy // 500 - 3, sy // 500 + 4):
        for c in range(sx // 500 - 3, sx // 500 + 4):
            print((c * 500 + 250, r * 500 + 250), step(sx, sy, c * 500 + 250, r * 500 + 250, bud, bl))
