"""F635b: outcome classes of ButtonProbe / ButtonProbeP runs: python3 bpcount.py RUN.tsv [RUN.tsv ...]
(an outcome's class = its text with play / command names (p123, a45) blanked); presses per side summed."""
import collections, re, sys
for path in sys.argv[1:]:
    rows = [l.rstrip('\n').split('\t') for l in open(path)][1:]
    c = collections.Counter(re.sub(r'\b[pa]\d+\b', '#', r[5]) for r in rows)
    presses = sum(int(r[2]) + int(r[3]) for r in rows)
    print('== %s: %d episodes, %d presses' % (path, len(rows), presses))
    for k, n in c.most_common():
        print('  %4d  %s' % (n, k[:170]))
