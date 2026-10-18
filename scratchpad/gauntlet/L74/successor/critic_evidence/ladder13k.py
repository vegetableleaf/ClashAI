# Recompute CXXXVIII live record from overnight.out: running trophies from the 12530 anchor.
import re, sys, math
P = r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/live/overnight.out"
L = open(P, encoding="utf-8", errors="replace").read().splitlines()
start = int(sys.argv[1]) if len(sys.argv) > 1 else 46889  # 1-based line of 'trophies: 12530 total'
cur = None; rows = []
for i, s in enumerate(L[start-1:], start):
    m = re.search(r"\[ladder\] trophies: (\d+) total", s)
    if m:
        t = int(m.group(1))
        if cur is not None and t != cur: rows.append(("ANCHOR_MISMATCH", i, cur, t))
        cur = t; continue
    m = re.search(r"\[ladder\] result: (WIN|LOSS|DRAW).*?trophies ([+-]?\d+|n/a)", s)
    if m:
        r, d = m.group(1), m.group(2)
        d = int(d) if d != "n/a" else None
        rows.append((r, i, cur, d))
        if cur is not None and d is not None: cur += d
res = [x for x in rows if x[0] in ("WIN","LOSS","DRAW") and x[3] is not None]
print("ranked/n-a results excluded:", sum(1 for x in rows if x[0] in ("WIN","LOSS","DRAW") and x[3] is None))
print("results:", len(res), "mismatches:", [x for x in rows if x[0]=="ANCHOR_MISMATCH"])
def wil(k, n):
    if n == 0: return (float('nan'),)*2
    z=1.96; p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return ((c-h)/d,(c+h)/d)
first = next(j for j,x in enumerate(res) if x[2] is not None and x[2] >= 13000)
for name, sub in (("before first 13000", res[:first]), ("since first 13000", res[first:]), ("all", res)):
    w = sum(x[0]=="WIN" for x in sub); n = len(sub)
    lo, hi = wil(w, n)
    floored = [x for x in sub if x[0]=="LOSS" and x[3] is not None and x[3] > -20]
    print(f"{name}: n {n} W {w} L {n-w} win {100*w/n:.1f}% [{100*lo:.1f}, {100*hi:.1f}]; floored losses (delta > -20): {len(floored)} {[ (x[2],x[3]) for x in floored]}")
# first 81 only (the plan's window)
sub81 = res[:81]; f81 = next(j for j,x in enumerate(sub81) if x[2] >= 13000)
s = sub81[f81:]; w = sum(x[0]=="WIN" for x in s)
print("plan window (first 81): since-13000 n", len(s), "W", w, "floored", sum(1 for x in s if x[0]=="LOSS" and x[3] > -20), "zero-cost", sum(1 for x in s if x[0]=="LOSS" and x[3]==0))
print("last trophies:", cur)
