"""A2c-BP6: is the game's reference point refreshed on a period? For each clean deciding goal-change event (bp5 goal6 rows,
x = variant goal with the reference at its end-of-t-k point, k=1..6, acq = at acquisition), the set of lags consistent with
the outcome: lag 0 = crforge's live point. Tests period P with phase by (absolute tick | tick - acquisition tick | unit id)."""
import collections, gzip, json, sys
rows = [json.loads(l) for l in gzip.open(sys.argv[1], 'rt')]
dec = [r for r in rows if r['clean'] and r['pre'] and r['out'] in ('crforge', 'alt0') and r.get('x')]
print('events', len(dec), collections.Counter(r['out'] for r in dec))


def lags(r):
    ok = set()
    for k in range(0, 7):
        g = r['goal'] if k == 0 else r['x']['e%d' % k]
        if g == -2:
            continue
        keep = g == r['held']
        if (r['out'] == 'alt0') == keep:
            ok.add(k)
    return ok


L = [(r, lags(r)) for r in dec]
print('alt0 lag sets', [(r['m'], r['t'], sorted(s)) for r, s in L if r['out'] == 'alt0'])
print('events where lag 0 is inconsistent', sum(1 for r, s in L if 0 not in s))
for key in ('abs', 'acq', 'id'):
    for P in range(2, 7):
        best = None
        for ph in range(P):
            bad = 0
            for r, s in L:
                base = 0 if key == 'abs' else (r['t'] - 1 - r['acq_age'] if key == 'acq' and r['acq_age'] is not None else r['id'] if key == 'id' else None)
                if base is None:
                    continue
                lag = (r['t'] - base + ph) % P if key != 'id' else (r['t'] + base + ph) % P
                if lag not in s:
                    bad += 1
            best = min(best or (10 ** 9, 0), (bad, ph))
        print(key, 'P', P, 'best phase', best[1], 'inconsistent', best[0])
