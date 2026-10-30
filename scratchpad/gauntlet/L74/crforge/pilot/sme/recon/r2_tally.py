"""RECON-2 item 3 tally (pod): pooled fresh exactness on the 151 scored strict-fresh FRESH2-8 matches, the hand-rule
pipeline (gate on the flags-ON re-extraction) vs RECON (search on the flags-OFF re-extraction), per match and pooled.
    python3 recon/r2_tally.py GATE/results.jsonl RECON1/recon_results.jsonl[,RECON2/...] [STRICT_REF.jsonl]
Class: 2 strictly exact, 1 exact apart from torn, 0 fail. A match the extractor flags (opp_no_fitting_deal, ...) is
listed and counted as not passing in 'all 151', and left out in 'unflagged'. One-sided 95% Clopper-Pearson lower bounds."""
import json, sys
from math import comb


def klass(r):
    c = r.get('counts') or {}
    if not c:
        return 0
    return 2 if set(c) <= {'exact'} else 1 if all(k == 'exact' or k.startswith('torn_') for k in c) else 0


def cp_lower(k, n, a=0.05):
    if k == 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        p = (lo + hi) / 2
        tail = sum(comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))
        lo, hi = (p, hi) if tail < a else (lo, p)
    return lo


def load(paths):
    out = {}
    for p in paths.split(','):
        for line in open(p):
            r = json.loads(line)
            out[r['match']] = r
    return out


def main():
    gate, rc = load(sys.argv[1]), load(sys.argv[2])
    ms = sorted(set(gate) | set(rc))
    rows = []
    for m in ms:
        g, r = gate.get(m, {}), rc.get(m, {})
        rows.append((m, bool(g.get('flags')), klass(g), bool(r.get('flags')), klass(r), g, r))
    for name, keep in (('all %d' % len(rows), lambda x: True),):
        for label, fl, kl in (('hand-rule gate (flags on)', 1, 2), ('RECON search (flags off)', 3, 4)):
            sel = [x for x in rows if keep(x)]
            n = len(sel)
            un = [x for x in sel if not x[fl]]
            for title, s, tot in (('all', sel, n), ('unflagged', un, len(un))):
                pas = sum(x[kl] >= 1 and not x[fl] for x in s)
                st = sum(x[kl] == 2 and not x[fl] for x in s)
                print('%-28s %-9s n %3d  pass (exact apart from torn) %3d (%.3f, CP lower %.3f)  strict %3d (%.3f, CP lower %.3f)' % (
                    label, title, tot, pas, pas / max(tot, 1), cp_lower(pas, tot), st, st / max(tot, 1), cp_lower(st, tot)))
    print('\nper match where the two differ (class 2 strict / 1 torn-only / 0 fail; F = flagged):')
    for m, gf, gk, rf, rk, g, r in rows:
        if (gk, gf) != (rk, rf):
            print(m, 'gate', ('F' if gf else '') + str(gk), g.get('counts'), g.get('first_div'), '| recon', ('F' if rf else '') + str(rk),
                  r.get('counts'), r.get('first_div'), [e for e in r.get('edits') or [] if not e.startswith('shift')], g.get('flags') or '', r.get('flags') or '')


if __name__ == '__main__':
    main()
