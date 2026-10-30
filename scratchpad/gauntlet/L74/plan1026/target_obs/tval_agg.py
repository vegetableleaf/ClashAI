"""TARGET-VAL aggregate: pooled agreement + 95% bootstrap CI by match (2,000 resamples, seed 0) over tval_score outputs.
    python3 tval_agg.py OUT1.jsonl [OUT2.jsonl ...]
Cohorts: all = every unflagged match's prefix-exact frames; strict = strictly exact matches only. Then the
disagreement classes (C '<metric>|why|<class>') and the top detail rows from OUT*.dis.jsonl."""
import collections, json, random, sys

rows = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
rows = [r for r in rows if 'C' in r]


def ci(ms, key):
    ok = [m['C'].get(key + '|ok', 0) for m in ms]
    n = [m['C'].get(key + '|n', 0) for m in ms]
    if not sum(n):
        return None
    rng, bs = random.Random(0), []
    for _ in range(2000):
        ix = [rng.randrange(len(ms)) for _ in ms]
        nn = sum(n[i] for i in ix)
        if nn:
            bs.append(sum(ok[i] for i in ix) / nn)
    bs.sort()
    return sum(ok), sum(n), sum(ok) / sum(n), bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs)) - 1], sum(x > 0 for x in n)


keys = sorted({k.rsplit('|', 1)[0] for r in rows for k in r['C'] if k.endswith('|n')})
for name, ms in (('all', rows), ('strict', [r for r in rows if r['strict']])):
    fr = sum(m['C'].get('frames', 0) for m in ms)
    rr, pa = sum(m['C'].get('rd_rows', 0) for m in ms), sum(m['C'].get('paired', 0) for m in ms)
    pr, pp = sum(m['C'].get('proj_rd', 0) for m in ms), sum(m['C'].get('proj_paired', 0) for m in ms)
    print(f'== cohort {name}: matches {len(ms)} exact frames {fr} body rows paired {pa}/{rr} proj paired {pp}/{pr}')
    for met in ('raw', 'acq', 'acq_active', 'acq2', 'acq2_active'):
        for m in ms:
            m['C'][f'{met}|ALL|ok'] = sum(v for k, v in m['C'].items() if k.startswith(met + '|') and k.endswith('|ok')
                                          and '|ALL|' not in k and '|why|' not in k)
            m['C'][f'{met}|ALL|n'] = sum(v for k, v in m['C'].items() if k.startswith(met + '|') and k.endswith('|n')
                                         and '|ALL|' not in k and '|why|' not in k)
    for k in [f'{m}|ALL' for m in ('raw', 'acq', 'acq_active', 'acq2', 'acq2_active')] + keys:
        c = ci(ms, k)
        if c:
            print(f'{k:28s} {c[0]:>8d} / {c[1]:<8d} {c[2]:.4f}  CI [{c[3]:.4f}, {c[4]:.4f}]  matches {c[5]}')
    why = collections.Counter()
    for m in ms:
        for k, v in m['C'].items():
            if '|why|' in k:
                why[k] += v
    print('-- disagreement classes')
    for k, v in sorted(why.items(), key=lambda kv: -kv[1]):
        print(f'{v:>8d} {k}')
D = collections.Counter()
for f in sys.argv[1:]:
    for l in open(f + '.dis.jsonl'):
        d = json.loads(l)
        D[(d[2], d[3], d[4], d[5], str(d[6]), str(d[7]))] += 1
print('-- top detail (metric, class, attacker class, attacker, engine target, reader target)')
for k, v in D.most_common(40):
    print(v, k)
