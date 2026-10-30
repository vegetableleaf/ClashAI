"""RECON-4 report: N pipelines on the same matches, the first is the reference (the hand-rule gate).
    python3 recon/r4_report.py gate=GATE.jsonl v2=A.jsonl,B.jsonl v3=C.jsonl [--a0 gate=GATE_A0.jsonl v3=V3_A0.jsonl] [--unflag 155249,000242]
Class as r2_tally.klass (2 strict, 1 exact apart from torn, 0 fail). A match the extractor flags counts as not passing, except the
--unflag matches in the non-gate pipelines (owner 10-30: RECON counts them; both counts are printed). One-sided 95% Clopper-Pearson
lower bounds, paired exact sign tests vs the reference, every match failing in any pipeline with its first diff rows, and the ASSIGN
off / on comparison (per frame when both runs carry cls_ticks)."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2_tally import klass, cp_lower, load  # noqa: E402
from r3_report import sign_p, summ  # noqa: E402


def guard(off, on):
    """assign_guard's rule on two result dicts: -> list of (match, problem)."""
    bad = []
    for m in sorted(set(off) & set(on)):
        a, b = off[m], on[m]
        if 'cls_ticks' not in a or 'cls_ticks' not in b:
            bad.append((m, 'no cls_ticks (counts only)' if a['counts'] == b['counts'] else 'counts differ, no cls_ticks'))
            continue
        lost = {t for ts in b['cls_ticks'].values() for t in ts} - {t for ts in a['cls_ticks'].values() for t in ts}
        if lost or a['frames'] != b['frames'] or klass(b) < klass(a):
            bad.append((m, 'lost %d frames, class %d -> %d' % (len(lost), klass(a), klass(b))))
    return bad


def main():
    args, P, a0, un = sys.argv[1:], {}, {}, []
    mode = 'p'
    for a in args:
        if a == '--a0':
            mode = 'a'
        elif a == '--unflag':
            mode = 'u'
        elif mode == 'u':
            un = a.split(',')
        else:
            n, f = a.split('=')
            (P if mode == 'p' else a0)[n] = load(f)
    names = list(P)
    ms = sorted(set().union(*P.values()))
    ref = names[0]
    flg = {n: {m: bool(P[n].get(m, {}).get('flags')) for m in ms} for n in names}
    cls = {n: {m: (klass(P[n][m]) if m in P[n] else 0) for m in ms} for n in names}
    for variant in ('as extracted (flagged = not passing)', 'with --unflag counted'):
        if variant.startswith('with') and not un:
            continue
        print('==', variant)
        f2 = {n: {m: flg[n][m] and not (variant.startswith('with') and n != ref and any(m.endswith(u) for u in un)) for m in ms} for n in names}
        for n in names:
            N = len(ms)
            pas = sum(cls[n][m] >= 1 and not f2[n][m] for m in ms)
            st = sum(cls[n][m] == 2 and not f2[n][m] for m in ms)
            print('%-6s n %3d  pass(apart from torn) %3d (%.3f, CP low %.3f)  strict %3d (%.3f, CP low %.3f)' % (
                n, N, pas, pas / N, cp_lower(pas, N), st, st / N, cp_lower(st, N)))
        for n in names[1:]:
            for lv, nm in ((1, 'pass'), (2, 'strict')):
                ok = lambda x, m: cls[x][m] >= lv and not f2[x][m]  # noqa: E731
                oa = [m for m in ms if ok(ref, m) and not ok(n, m)]
                ob = [m for m in ms if ok(n, m) and not ok(ref, m)]
                print('%s vs %s %-6s only-%s %2d only-%s %2d  p=%.4f' % (ref, n, nm, ref, len(oa), n, len(ob), sign_p(len(oa), len(ob))))
    print('\nfailing in any pipeline (class per pipeline, F = flagged):')
    for m in ms:
        if all(cls[n][m] == 2 and not flg[n][m] for n in names):
            continue
        last = P[names[-1]].get(m) or P[ref][m]
        print(m[-13:], ' '.join('%s%s%d' % (n, 'F' if flg[n][m] else '', cls[n][m]) for n in names), '|',
              ' | '.join('%s %s %s' % (n, P[n].get(m, {}).get('counts'), P[n].get(m, {}).get('first_div')) for n in names), '|', summ(last),
              '| struct', [e for e in (last.get('edits') or []) if not e.startswith('shift')])
    if a0:
        print('\nASSIGN off vs on on the reader-hidden records:')
        for n, off in a0.items():
            for m, why in guard(off, P[n]) or [('-', 'PASS')]:
                print(n, m[-13:], why)
            for m in sorted(off):
                print(n, m[-13:], 'off', off[m]['counts'], '-> on', P[n][m]['counts'])


if __name__ == '__main__':
    main()
