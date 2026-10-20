"""j6cause.py restricted to the fights fights.is_clean(strict) passes (the j6diag run/matches records give each fight's flags).
  python j6cause_clean.py DIR"""
import json, glob, os, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
D = sys.argv[1]
clean = {}
for f in glob.glob(D + '/run/matches/*.json'):
    d = json.load(open(f))
    for fi in d.get('fights', []):
        if 'error' not in fi:
            clean[(d['summary']['match'], fi['t0'])] = F.is_clean(fi, 'strict')
cls = Counter(); ex = []
for f in glob.glob(D + '/*.jsonl'):
    m = Path(f).stem
    for line in open(f):
        d = json.loads(line)
        c = clean.get((m, d['t0']))
        L = {r[0]: r for r in d['live']}; S = {r[0]: r for r in d['sim']}
        k = 'P'
        for t in sorted(set(L) & set(S)):
            l, s = L[t], S[t]
            if l[4] and not s[4]:
                k = 'M'; break
            if abs(l[3] - s[3]) > max(20, .1 * max(l[3], s[3])):
                k = 'F'; break
        cls[('clean' if c else 'unclean' if c is False else 'unknown', k)] += 1
        if c and k == 'P':
            ex.append((m[10:], d['card'], d['t0'], d['live_cross'], d['sim_cross']))
print(sorted(cls.items()))
print('clean pathing candidates', ex)
