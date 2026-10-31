"""Summary of r5_partA.py rows:  python -I recon/r5_partA_sum.py partA.jsonl [...]"""
import json, sys, statistics

rows = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
ex = lambda r: (r or {}).get('counts', {}).get('exact', 0)           # noqa: E731
tot = lambda r: sum((r or {}).get('counts', {}).values())            # noqa: E731
fd = lambda r: (r or {}).get('first') if (r or {}).get('first') is not None else 10 ** 9   # noqa: E731
gain = [ex(r['best_prefix']) - ex(r['identity']) for r in rows]
print('records', len(rows))
print('exact frames: identity %d, best-prefix %d of %d; per record gain median %d, min %d, max %d' % (
    sum(ex(r['identity']) for r in rows), sum(ex(r['best_prefix']) for r in rows), sum(tot(r['identity']) for r in rows),
    statistics.median(gain), min(gain), max(gain)))
print('first divergence later: %d, same %d, earlier %d; moved >= 100 ticks later: %d' % (
    sum(fd(r['best_prefix']) > fd(r['identity']) for r in rows), sum(fd(r['best_prefix']) == fd(r['identity']) for r in rows),
    sum(fd(r['best_prefix']) < fd(r['identity']) for r in rows), sum(fd(r['best_prefix']) >= fd(r['identity']) + 100 for r in rows)))
print('exact apart from torn: identity %d, best-prefix %d' % (
    sum(all(k == 'exact' or k.startswith('torn_') for k in r['identity']['counts']) for r in rows if r['identity']),
    sum(all(k == 'exact' or k.startswith('torn_') for k in r['best_prefix']['counts']) for r in rows if r['best_prefix'])))
