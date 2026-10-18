"""Which set-up flags travel with misses (strict fights, rows_fin12st_f.tsv): per flag, fights carrying it, their miss rate,
and the card-stratified excess = sum over cards of n_with x (miss rate with - miss rate without). ASSOCIATION, not cause:
busy boards carry more flags. usage: python flagassoc.py rows_fin12st_f.tsv [MIN_N]"""
import sys
from collections import defaultdict
MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 40
R = []
for ln in open(sys.argv[1], encoding='utf-8'):
    c = ln.rstrip('\n').split('\t')
    if c[3] != '1' or c[4] == '':
        continue
    R.append((c[2], 1 - float(c[4]), set(x for x in (c[11] if len(c) > 11 else '').split(',') if x)))
flags = defaultdict(int)
for _, _, f in R:
    for x in f:
        flags[x] += 1
bycard = defaultdict(list)
for r in R:
    bycard[r[0]].append(r)
out = []
for fl, n in flags.items():
    if n < MIN:
        continue
    w = [r[1] for r in R if fl in r[2]]
    wo = [r[1] for r in R if fl not in r[2]]
    ex = 0.
    for card, xs in bycard.items():
        a = [m for _, m, f in xs if fl in f]
        b = [m for _, m, f in xs if fl not in f]
        if a and b:
            ex += len(a)*(sum(a)/len(a) - sum(b)/len(b))
    out.append((ex, fl, n, sum(w)/len(w), sum(wo)/len(wo) if wo else 0, sum(w)))
print('flag | strict fights with it | miss rate with | without | miss mass with | card-stratified excess mass')
for ex, fl, n, rw, ro, mw in sorted(out, reverse=True):
    print(f"{fl} | {n} | {rw:.3f} | {ro:.3f} | {mw:.1f} | {ex:+.1f}")
