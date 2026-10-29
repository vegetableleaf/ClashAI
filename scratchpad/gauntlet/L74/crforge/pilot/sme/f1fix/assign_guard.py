"""ENG-FIX4 gate guard for SME_HIDDEN_ASSIGN (owner 10-29: ratified "for now, but make sure it doesn't hurt our results").
Every gate run is made twice, ASSIGN off and on (runH.sh default on; SME_HIDDEN_ASSIGN=0 for off), both with SME_CLS_TICKS=1.
    python3 assign_guard.py OFF/results.jsonl ON/results.jsonl   -> one line per match, then PASS or FAIL-TO-REPORT
FAIL when, for any match: a frame exact with ASSIGN off is not exact with it on; the frame count differs; or the match class
gets worse (strictly exact > exact apart from torn > fail; flagged matches are compared too)."""
import json, sys


def load(p):
    return {r['match']: r for r in map(json.loads, open(p))}


def klass(r):
    c = r['counts']
    return 2 if set(c) <= {'exact'} else 1 if all(k == 'exact' or k.startswith('torn_') for k in c) else 0


def main(off_p, on_p):
    off, on = load(off_p), load(on_p)
    bad = []
    if set(off) != set(on):
        bad.append('match sets differ: %s' % sorted(set(off) ^ set(on)))
    for m in sorted(set(off) & set(on)):
        a, b = off[m], on[m]
        if 'cls_ticks' not in a or 'cls_ticks' not in b:
            bad.append('%s: no cls_ticks (run without SME_CLS_TICKS=1)' % m)
            continue
        na = {t for ts in a['cls_ticks'].values() for t in ts}
        lost = sorted({t for ts in b['cls_ticks'].values() for t in ts} - na)
        why = []
        if lost:
            why.append('%d OFF-exact frames not exact ON (first %s)' % (len(lost), lost[:5]))
        if a['frames'] != b['frames']:
            why.append('frames %d -> %d' % (a['frames'], b['frames']))
        if klass(b) < klass(a):
            why.append('class %d -> %d' % (klass(a), klass(b)))
        print(m, 'flags' if a['flags'] else 'unflagged', a['counts'], '->', b['counts'], 'OK' if not why else 'BAD ' + '; '.join(why))
        if why:
            bad.append(m)
    print('PASS' if not bad else 'FAIL-TO-REPORT %s' % bad)
    return not bad


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--selftest':   # the smallest check that fails if the logic breaks
        import os, tempfile
        d = tempfile.mkdtemp()
        r = dict(match='m', flags=[], frames=4, counts={'exact': 3, 'torn_hidden': 1}, cls_ticks={'torn_hidden': [2]})
        w = lambda n, x: open(os.path.join(d, n), 'w').write(json.dumps(x) + '\n') and os.path.join(d, n)   # noqa: E731
        assert main(w('a', r), w('b', r))
        assert not main(w('a', r), w('b', dict(r, counts={'exact': 3, 'div': 1}, cls_ticks={'div': [2]})))   # worse class
        assert not main(w('a', r), w('b', dict(r, cls_ticks={'torn_hidden': [3]})))                         # lost frame 3
        print('selftest ok')
    else:
        sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
