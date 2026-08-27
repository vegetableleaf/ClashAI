import json, math, sys
def rec(tag): return {r['seed']: r for r in json.load(open(f'rs_{tag}.json'))['records']}
def cmp(a, b, key='tower_delta'):
    A, B = rec(a), rec(b); s = sorted(set(A) & set(B))
    d = [A[x][key] - B[x][key] for x in s]
    m = sum(d)/len(d); v = sum((z-m)**2 for z in d)/(len(d)-1); sem = math.sqrt(v/len(d))
    return m, sem, m/sem, len(s)
for a, b in [(x.split(':')[0], x.split(':')[1]) for x in sys.argv[1:]]:
    try:
        m, sem, z, n = cmp(a, b)
        print(f'{a:8s} vs {b:8s}  dtower={m:+.3f}  sem={sem:.3f}  sigma={z:+.2f}  n={n}  ' +
              ('DIFFERENT' if abs(z) >= 2 else 'no difference at 2 sigma'))
    except FileNotFoundError as e:
        print(f'{a} vs {b}: not finished')
