"""Raw agreement by match era (FIN12_stamped rows): matches up to a stem cut vs after, overall and per card (n >= 40 both).
Tests whether fixes found on the old matches carry to the new ones. usage: python byera.py ROWS.tsv CUT_STEM"""
import sys
from collections import defaultdict
from trigger import load, boot_ci
rows, cut = load(sys.argv[1]), sys.argv[2]
mean = lambda v: sum(v)/len(v) if v else None
for lab, sel in (('old (<= cut)', lambda r: r['stem'] <= cut), ('new (> cut)', lambda r: r['stem'] > cut)):
    xs = [r for r in rows if sel(r)]
    it = [(r['stem'], r['aK']) for r in xs]
    print(f"{lab}: matches {len({r['stem'] for r in xs})}, fights {len(xs)}, raw {mean([v for _, v in it]):.4f} CI {boot_ci(it, mean, B=1000)}")
by = defaultdict(lambda: ([], []))
for r in rows:
    by[r['card']][r['stem'] > cut].append(r['aK'])
print('card | old n raw | new n raw')
for c, (o, n) in sorted(by.items(), key=lambda kv: -len(kv[1][0]) - len(kv[1][1])):
    if len(o) >= 40 and len(n) >= 40:
        print(f"{c} | {len(o)} {mean(o):.3f} | {len(n)} {mean(n):.3f}")
