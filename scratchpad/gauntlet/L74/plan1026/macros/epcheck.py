"""Quick sanity table of an episode file set: per macro n, treated share, well share, win (treated / not), el band 'na' share.
    python -B epcheck.py EP_FILE_OR_DIR [...]"""
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

files = [f for a in sys.argv[1:] for f in (sorted(Path(a).glob('*.jsonl.gz')) if Path(a).is_dir() else [Path(a)])]
S = defaultdict(lambda: defaultdict(float))
for f in files:
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        e = json.loads(line)
        s = S[e['macro']]
        s['n'] += 1
        if e['macro'] == '_side':
            s['win'] += e['win']
            continue
        s['tr'] += e['tr']
        s['na'] += e['el'] == 'na'
        if e['well'] is not None:
            s['wn'] += 1
            s['well'] += e['well']
        s['w%d' % e['tr']] += e['win']
        s['c%d' % e['tr']] += 1
print('%-24s %8s %6s %6s %6s %6s %6s' % ('macro', 'n', 'tr', 'well', 'winT', 'winC', 'el_na'))
for k, s in sorted(S.items()):
    n = s['n']
    if k == '_side':
        print('%-24s %8d win %.3f' % (k, n, s['win'] / n))
        continue
    print('%-24s %8d %6.3f %6s %6s %6s %6.3f' % (k, n, s['tr'] / n, '%.3f' % (s['well'] / s['wn']) if s['wn'] else '-',
          '%.3f' % (s['w1'] / s['c1']) if s['c1'] else '-', '%.3f' % (s['w0'] / s['c0']) if s['c0'] else '-', s['na'] / n))
