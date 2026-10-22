"""Control for the classifier: the FIRST GLOBAL divergence of every strict fight (pass 3 rules), failing vs passing. A
divergence class as common in passing fights as in failing ones does not explain failures.
  python control.py CLS3ALL_JSONL"""
import json, sys
from collections import Counter
rows = [f for line in open(sys.argv[1]) for f in json.loads(line)['fights'] if 'error' not in f]
ok = [r for r in rows if r.get('ok')]; bad = [r for r in rows if not r.get('ok')]
print('fights', len(rows), 'passing', len(ok), 'failing', len(bad))
def key(r, fine=False):
    f = r['first_global']
    if f is None:
        return 'no divergence at all'
    when = 'setup<=10' if f['dt'] <= 10 else 'early<=40' if f['dt'] <= 40 else 'late'
    return (f['kind'], when) if not fine else (f['kind'], f['body'], 'setup' if f.get('setup') else 'new')
for fine in (False, True):
    cp, cf = Counter(key(r, fine) for r in ok), Counter(key(r, fine) for r in bad)
    print('\nclass | share of passing | share of failing | P(fail | class) | n')
    for k in sorted(set(cp) | set(cf), key=lambda k: -(cf[k] + cp[k]))[:30 if fine else 40]:
        n = cp[k] + cf[k]
        print(f'{k} | {cp[k]/len(ok):.3f} | {cf[k]/len(bad):.3f} | {cf[k]/n:.3f} | {n}')
