"""aimfit.py X0 Y0 X1 Y1 BUDGET [NT] -- node-centre aims (a tick each, NT ticks, default 2) whose pure steps take (X0,Y0) to (X1,Y1)"""
import math, sys, itertools
x0, y0, x1, y1, b = map(int, sys.argv[1:6]); nt = int(sys.argv[6]) if len(sys.argv) > 6 else 2
def tdiv(a, c):
    q = abs(a) // abs(c); return q if (a >= 0) == (c > 0) else -q
def pure(sx, sy, tx, ty, budget):
    d = math.isqrt((tx - sx) ** 2 + (ty - sy) ** 2); s = max(d, 1); st = min(budget, s, 250)
    return sx + tdiv(tdiv((tx - sx) << 8, s) * st, 256), sy + tdiv(tdiv((ty - sy) << 8, s) * st, 256)
C = [(c * 500 + 250, r * 500 + 250) for c in range(36) for r in range(64) if abs(c * 500 + 250 - x0) + abs(r * 500 + 250 - y0) < 4000]
def rec(p, k, path):
    if k == nt:
        if p == (x1, y1): print(path)
        return
    for a in C: rec(pure(p[0], p[1], a[0], a[1], b), k + 1, path + [a])
rec((x0, y0), 0, [])
