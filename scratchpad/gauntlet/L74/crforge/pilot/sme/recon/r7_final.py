"""RECON-7 tables: gate vs RECON v3 vs v3 + RECON-5 (RECON_CYC=1) vs + forms (RECON_FORM=1) vs RECON-7 (RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80) on one set (laptop).
  python -I recon/r7_final.py --name FRESH12 --gate G.jsonl --v3 V.jsonl --cyc-aff A.jsonl --cycform F.jsonl --r7 R.jsonl [--ok-v3 m1,m2] [--ok-cyc m1,m2] [--ok-form m1,m2] [--ok-r7 m1,m2]
(r6_final.py + one column: the RECON-7 row of a record = its --r7 row if it has one, else its forms row; same argument as for RECON-5 / forms.)
RECON-5 row of a record = its --cyc-aff row if it has one, else its v3 row (a record outside the affected set takes no RECON_CYC path, so its RECON_CYC=1 row is its v3 row;
RECON.md 12.7); forms row = its --cycform row if it has one, else the RECON-5 row (same argument for RECON_FORM). Counts as r5_final.py: as extracted (a flagged record never
counts), counted (a flagged record counts when it is exact AND in that pipeline's --ok list = every kept structural edit ablation-confirmed), raw (flag ignored); pass = class >= 1
(exact apart from torn), strict = class 2. One-sided 95% Clopper-Pearson lower bounds; paired exact sign tests between every two pipelines."""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2_tally import klass, cp_lower, load  # noqa: E402
from r3_report import sign_p  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--gate', required=True); ap.add_argument('--v3', required=True)
    ap.add_argument('--cyc-aff', required=True); ap.add_argument('--cycform', required=True); ap.add_argument('--r7', required=True)
    ap.add_argument('--ok-v3', default=''); ap.add_argument('--ok-cyc', default=''); ap.add_argument('--ok-form', default=''); ap.add_argument('--ok-r7', default='')
    a = ap.parse_args()
    G, V = load(a.gate), load(a.v3)
    C = dict(V); C.update(load(a.cyc_aff))
    F = dict(C); F.update(load(a.cycform))
    R7 = dict(F); R7.update(load(a.r7))
    P = {'gate': G, 'v3': V, 'recon5': C, 'forms': F, 'recon7': R7}
    ok = {'gate': set(), 'v3': set(a.ok_v3.split(',')) - {''}, 'recon5': set(a.ok_cyc.split(',')) - {''}, 'forms': set(a.ok_form.split(',')) - {''}, 'recon7': set(a.ok_r7.split(',')) - {''}}
    ms = sorted(G)
    names = ('gate', 'v3', 'recon5', 'forms', 'recon7')

    def cls(n, m):
        return klass(P[n][m]) if m in P[n] and 'error' not in P[n][m] else 0

    def passes(n, m, mode, lv):
        if cls(n, m) < lv:
            return False
        if mode == 'raw':
            return True
        fl = bool(P[n].get(m, {}).get('flags'))
        return (not fl) or (mode == 'counted' and any(m.endswith(x) for x in ok[n] if x))

    N = len(ms)
    errs = {n: sum(1 for m in ms if m not in P[n] or 'error' in P[n][m]) for n in names}
    print('== %s: n %d unique matches; rows missing or errored: %s' % (a.name, N, errs))
    for mode in ('asx', 'counted', 'raw'):
        line = []
        for n in names:
            pa = sum(passes(n, m, mode, 1) for m in ms); st = sum(passes(n, m, mode, 2) for m in ms)
            line.append('%s pass %3d (%.3f, CP low %.3f) strict %3d (%.3f, CP low %.3f)' % (n, pa, pa / N, cp_lower(pa, N), st, st / N, cp_lower(st, N)))
        print('%-8s' % mode, ' | '.join(line))
        for lv, nm in ((1, 'pass'), (2, 'strict')):
            for i, x in enumerate(names):
                for y in names[i + 1:]:
                    ox = [m for m in ms if passes(x, m, mode, lv) and not passes(y, m, mode, lv)]
                    oy = [m for m in ms if passes(y, m, mode, lv) and not passes(x, m, mode, lv)]
                    print('   %s vs %-6s %-6s only-%s %2d only-%s %2d p=%.4f' % (x, y, nm, x, len(ox), y, len(oy), sign_p(len(ox), len(oy))))
    for x, y in (('v3', 'recon5'), ('recon5', 'forms'), ('recon5', 'recon7'), ('v3', 'recon7'), ('gate', 'recon7')):
        g = [m[-13:] for m in ms if cls(y, m) >= 1 and cls(x, m) == 0]
        l = [m[-13:] for m in ms if cls(x, m) >= 1 and cls(y, m) == 0]
        print('raw gained by %s over %s: %s | lost: %s' % (y, x, g, l))


if __name__ == '__main__':
    main()
