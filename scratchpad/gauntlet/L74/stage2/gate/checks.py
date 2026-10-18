"""Small checks behind the gate report: (1) Fisher exact for the 13k+ OT halves 8/27 vs 10/15; (2) band-matched Hog contrast
(12,500-12,999: both Marks played there); (3) live pace per 100 matches (Hog / OT shares) for the sealed-set size."""
import json, math, os
X = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_targets.json")))


def fisher(a, b, c, d):
    """two-sided Fisher exact on [[a, b], [c, d]]."""
    n1, n2, k = a + b, c + d, a + c
    p = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n1 + n2, k)
    p0 = p(a)
    return sum(p(x) for x in range(max(0, k - n2), min(k, n1) + 1) if p(x) <= p0 * (1 + 1e-9))


print("13k+ OT halves 8/27 vs 10/15: Fisher p =", round(fisher(8, 19, 10, 5), 4))
L = [x for x in X if x["src"] == "ladder"]
for mk in ("CXXXVIII", "CXXIV"):
    Q = [x for x in L if x["mark"] == mk and x["start"] and 12500 <= x["start"] < 13000 and x["cls"].startswith("Hog")]
    print(f"{mk} Hog at 12,500-12,999: {sum(x['res'] == 'WIN' for x in Q)}/{len(Q)}")
C = [x for x in L if x["mark"] == "CXXXVIII"]
print(f"CXXXVIII per 100 matches: Hog {100 * sum(x['cls'].startswith('Hog') for x in C) / len(C):.0f}, OT {100 * sum(x['ot'] for x in C) / len(C):.0f}; "
      f"matches {len(C)} over {C and (min(x['ts'] for x in C), max(x['ts'] for x in C))}")
