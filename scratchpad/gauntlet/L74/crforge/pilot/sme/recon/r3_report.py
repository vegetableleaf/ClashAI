"""RECON-3 report: hand-rule gate vs RECON v1 vs RECON v2 on the SAME 151 strict-fresh FRESH2-8 inputs and lib.
    python3 recon/r3_report.py GATE.jsonl V1a.jsonl,V1b.jsonl V2a.jsonl,V2b.jsonl [GATE_A0.jsonl RC_A0.jsonl V2_A0.jsonl]
Class: 2 strictly exact, 1 exact apart from torn, 0 fail (r2_tally.klass). A match the extractor flags counts as not passing in
'all'. Prints: pooled counts + one-sided 95% Clopper-Pearson lower bounds, paired exact sign tests (McNemar), every match that
fails in any pipeline with a first-divergence summary, and the ASSIGN on / off comparison of the reader-hidden records.
Paired test: n01 = matches pass in B only, n10 = A only; two-sided exact binomial p under H0 p = 0.5 on n01 + n10."""
import json, os, sys
from math import comb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2_tally import klass, cp_lower, load  # noqa: E402


def sign_p(a, b):
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)


def summ(r):
    """first_detail rows -> 'U-sim Skeleton(side0) U-rec Witch ...' short text."""
    out = []
    for row in (r.get('first_detail') or [])[:5]:
        k, a, b = row[0], row[1], row[2]
        if k.endswith('_elixir'):
            out.append('%s %s/%s' % (k, a, row[3]))
        elif k.startswith('T_'):
            out.append('%s %s' % (k, a))
        else:
            out.append('%s %s%s' % (k, b, '' if a is None else ' s%s@(%s,%s)' % (a[0], a[1], a[2])))
    return '; '.join(out)


def main():
    a = sys.argv[1:]
    gate, v1, v2 = load(a[0]), load(a[1]), load(a[2])
    ms = sorted(set(gate) | set(v1) | set(v2))
    P = {'gate': gate, 'v1': v1, 'v2': v2}
    cls = {n: {m: (klass(d[m]) if m in d else 0) for m in ms} for n, d in P.items()}
    flg = {n: {m: bool(d.get(m, {}).get('flags')) for m in ms} for n, d in P.items()}
    print('matches %d (gate %d, v1 %d, v2 %d)' % (len(ms), len(gate), len(v1), len(v2)))
    for scope in ('all', 'unflagged'):
        for n in P:
            sel = [m for m in ms if scope == 'all' or not flg[n][m]]
            pas = sum(cls[n][m] >= 1 and not flg[n][m] for m in sel)
            st = sum(cls[n][m] == 2 and not flg[n][m] for m in sel)
            N = len(sel)
            print('%-5s %-9s n %3d  pass(apart from torn) %3d (%.3f, CP low %.3f)  strict %3d (%.3f, CP low %.3f)' % (
                n, scope, N, pas, pas / N, cp_lower(pas, N), st, st / N, cp_lower(st, N)))
    ok = lambda n, m, lv: cls[n][m] >= lv and not flg[n][m]  # noqa: E731
    print('\npaired exact sign tests (all 151, flagged = not passing); only-A / only-B = matches passing in just one')
    for A, B in (('gate', 'v1'), ('gate', 'v2'), ('v1', 'v2')):
        for lv, nm in ((1, 'pass'), (2, 'strict')):
            oa = [m for m in ms if ok(A, m, lv) and not ok(B, m, lv)]
            ob = [m for m in ms if ok(B, m, lv) and not ok(A, m, lv)]
            print('%-5s vs %-3s %-6s only-%s %2d only-%s %2d  p=%.4f' % (A, B, nm, A, len(oa), B, len(ob), sign_p(len(oa), len(ob))))
    print('\nmatches failing (class != 2 or flagged) in any pipeline: class per pipeline (F = flagged), counts, first div, first diff rows')
    for m in ms:
        if all(cls[n][m] == 2 and not flg[n][m] for n in P):
            continue
        tag = ' '.join('%s%s%d' % (n, 'F' if flg[n][m] else '', cls[n][m]) for n in P)
        r = v2.get(m) or v1.get(m) or gate.get(m)
        print(m[-13:], tag, '| gate', gate.get(m, {}).get('counts'), gate.get(m, {}).get('first_div'), '| v2', v2.get(m, {}).get('counts'),
              v2.get(m, {}).get('first_div'), '|', summ(v2.get(m) or r), '| v2 structural edits',
              [e for e in (v2.get(m, {}).get('edits') or []) if not e.startswith('shift')])
    print('\nregressions v1 -> v2 (strict class went down or exact frames fell):')
    for m in ms:
        x, y = v1[m], v2[m]
        if cls['v2'][m] < cls['v1'][m] or y['counts'].get('exact', 0) < x['counts'].get('exact', 0):
            print(m, x['counts'], x.get('first_div'), '->', y['counts'], y.get('first_div'))
    if len(a) >= 6:
        print('\nASSIGN on/off on the reader-hidden records (counts and class; per-frame guard needs cls_ticks, gate only):')
        for name, on, off in (('gate', gate, load(a[3])), ('v1', v1, load(a[4])), ('v2', v2, load(a[5]))):
            for m in sorted(off):
                print(name, m[-13:], 'off', off[m]['counts'], off[m].get('first_div'), '-> on', on[m]['counts'], on[m].get('first_div'),
                      'class %d -> %d' % (klass(off[m]), klass(on[m])), 'BAD' if klass(on[m]) < klass(off[m]) or on[m]['counts'].get('exact', 0) < off[m]['counts'].get('exact', 0) else 'ok')


if __name__ == '__main__':
    main()
