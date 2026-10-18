"""Hog-only gate ranges: SIM rates p with |z| < 1.96 vs the live cell (two-proportion z, SIM noise included, as gate_fit.py).
Also the Fisher test of CXXXVIII-13k Hog OT vs CXXIV-12k Hog OT. Self-check: the live rate itself is inside its range."""
import math
def z(k, n, p, m):
    q = k / n; s = math.sqrt(q * (1 - q) / n + p * (1 - p) / m) or 1e-9
    return (p - q) / s
def rng(k, n, m):
    ok = [i / 1000 for i in range(1, 1000) if abs(z(k, n, i / 1000, m)) < 1.96]
    return ok[0], ok[-1]
def fisher_two_sided(a, b, c, d):
    from math import comb
    n1, n2, k = a + b, c + d, a + c
    P = lambda x: comb(n1, x) * comb(n2, k - x) / comb(n1 + n2, k)
    p0 = P(a); return sum(P(x) for x in range(max(0, k - n2), min(n1, k) + 1) if P(x) <= p0 + 1e-12)
CELLS = [("CXXXVIII 13k Hog win", 6, 21), ("CXXXVIII 13k Hog OT share", 13, 21), ("CXXXVIII 13k Hog OT win", 1, 13),
         ("CXXIV 12k Hog win", 32, 54), ("CXXIV 12k Hog OT share", 31, 54), ("CXXIV 12k Hog OT win", 22, 31)]
SIM_HOG = 480                                     # SIM Hog games per Mark (one 480-seed Hog-only gap run)
for name, k, n in CELLS:
    m = SIM_HOG if "OT win" not in name else int(SIM_HOG * 0.6)   # ~60% of SIM games reach OT (E4 run: 60.3%)
    lo, hi = rng(k, n, m); assert lo <= k / n <= hi
    print(f"{name:28s} live {k}/{n} = {k/n:5.1%}  allowed SIM [{lo:.1%}, {hi:.1%}] (SIM n {m})")
print("Fisher CXXXVIII-13k Hog OT 1/13 vs CXXIV-12k Hog OT 22/31: p =", round(fisher_two_sided(1, 12, 22, 9), 5))
print("Fisher CXXXVIII-13k Hog regulation 5/8 vs CXXIV-12k Hog regulation 10/23: p =", round(fisher_two_sided(5, 3, 10, 13), 3))
