import json, sys
from collections import Counter, defaultdict
c = defaultdict(Counter)
for line in open(sys.argv[1]):
    x = json.loads(line)
    for blk, fl, fs, tl, ts, n in x['rows']:
        c[blk]['n'] += n
        c[blk]['first same'] += n * (fl == fs)
        c[blk][f'first live={fl} sim={fs}'] += n
        c[blk]['live ends on tower'] += n * tl
        c[blk]['SIM ends on tower'] += n * ts
        c[blk]['end same'] += n * (tl == ts)
for k, v in c.items():
    print(k, dict(v.most_common(12)))
