"""RECON-5 tables: gate vs RECON v3 vs RECON v3 + cyc (RECON_CYC=1) on one set, 3 counts each.
  python3 recon/r5_final.py --name FRESH9 --gate G.jsonl --v3 V.jsonl --cyc C.jsonl [--cyc-aff A.jsonl] [--ok-v3 m1,m2] [--ok-cyc m1,m2] [--ok-gate ...]
--cyc-aff: rows that REPLACE the matching rows of --cyc (the affected records of a held-out set; every other record takes no RECON_CYC path, so its
RECON_CYC=1 row is the v3 row). Counts per pipeline, n = unique matches of the gate file:
  as extracted   a record the extractor flags counts as not passing (the historical rule)
  counted        a flagged record counts when its class is >= 1 AND it is in that pipeline's --ok list (every kept structural edit ablation-confirmed)
  raw            class >= 1 whatever the flag (engine fidelity of the replay itself)
class: 2 strictly exact, 1 exact apart from torn. One-sided 95% Clopper-Pearson lower bounds; paired exact sign tests (gate as reference)."""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2_tally import klass, cp_lower, load  # noqa: E402
from r3_report import sign_p  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--gate', required=True); ap.add_argument('--v3', required=True)
    ap.add_argument('--cyc', required=True); ap.add_argument('--cyc-aff'); ap.add_argument('--ok-v3', default=''); ap.add_argument('--ok-cyc', default='')
    a = ap.parse_args()
    G, V, C = load(a.gate), load(a.v3), load(a.cyc)
    if a.cyc_aff:
        C.update(load(a.cyc_aff))
    ms = sorted(G)
    ok = {'gate': set(), 'v3': set(a.ok_v3.split(',')) - {''}, 'cyc': set(a.ok_cyc.split(',')) - {''}}
    P = {'gate': G, 'v3': V, 'cyc': C}

    def cls(n, m):
        return klass(P[n][m]) if m in P[n] and 'error' not in P[n][m] else 0

    def flag(n, m):
        return bool(P[n].get(m, {}).get('flags')) or bool(G.get(m, {}).get('flags') and n == 'gate')

    def passes(n, m, mode, lv):
        if cls(n, m) < lv:
            return False
        if mode == 'raw':
            return True
        fl = bool(P[n].get(m, {}).get('flags'))
        return (not fl) or (mode == 'counted' and any(m.endswith(x) for x in ok[n] if x))

    N = len(ms)
    print('== %s: n %d unique matches' % (a.name, N))
    for mode in ('as extracted', 'counted', 'raw'):
        mm = mode.split()[0] if mode != 'as extracted' else 'as'
        mm = {'as extracted': 'asx', 'counted': 'counted', 'raw': 'raw'}[mode]
        line = []
        for n in ('gate', 'v3', 'cyc'):
            pa = sum(passes(n, m, mm, 1) for m in ms); st = sum(passes(n, m, mm, 2) for m in ms)
            line.append('%s pass %3d (%.3f, CP low %.3f) strict %3d (%.3f, CP low %.3f)' % (n, pa, pa / N, cp_lower(pa, N), st, st / N, cp_lower(st, N)))
        print('%-13s' % mode, ' | '.join(line))
        for lv, nm in ((1, 'pass'), (2, 'strict')):
            for x, y in (('gate', 'cyc'), ('v3', 'cyc'), ('gate', 'v3')):
                ox = [m for m in ms if passes(x, m, mm, lv) and not passes(y, m, mm, lv)]
                oy = [m for m in ms if passes(y, m, mm, lv) and not passes(x, m, mm, lv)]
                print('   %s %-6s only-%s %2d only-%s %2d p=%.4f' % ('%s vs %s' % (x, y), nm, x, len(ox), y, len(oy), sign_p(len(ox), len(oy))))
    gained = [m for m in ms if cls('cyc', m) >= 1 and cls('v3', m) == 0]
    lost = [m for m in ms if cls('v3', m) >= 1 and cls('cyc', m) == 0]
    print('raw gained by cyc over v3:', [m[-13:] for m in gained])
    print('raw lost by cyc vs v3:', [m[-13:] for m in lost])


if __name__ == '__main__':
    main()
