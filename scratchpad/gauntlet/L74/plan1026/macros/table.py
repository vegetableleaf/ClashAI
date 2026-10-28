"""LIBRARY.json -> markdown tables for MACROS.md (one row per macro x source).   python -B table.py LIBRARY.json"""
import hashlib
import json
import sys

p = sys.argv[1]
raw = open(p, 'rb').read()
d = json.loads(raw)


def f(v):
    if not v or v.get('est') is None or v['est'] != v['est'] or v['ci'][0] is None:
        return '-'
    return '%+.3f [%+.3f, %+.3f]' % (v['est'], v['ci'][0], v['ci'][1])


print('LIBRARY.json sha256 `%s`, B = %s, data: %s\n' % (hashlib.sha256(raw).hexdigest(), d['B'], json.dumps(d['data'])))
print('| macro | src | n (matches) | treated | win lift [95% CI] | margin lift 30 s | margin lift end | success lift | status | horizon |')
print('|---|---|---|---|---|---|---|---|---|---|')
for m in d['macros']:
    first = True
    for s in ('pro', 'hf', 'human', 'live'):
        v = m['sources'].get(s)
        if v is None:
            continue
        print('| %s | %s | %s (%s) | %s (%s) | %s | %s | %s | %s | %s | %s |' % (
            m['id'] if first else '', s, v.get('n'), v.get('matches', '-'), v.get('n_tr'),
            '%.1f%%' % (100 * v['tr_rate']) if 'tr_rate' in v else '-', f(v.get('lift_win')), f(v.get('lift_n600')),
            f(v.get('lift_nend')), f(v.get('lift_success')), m['status'] if first else '', m['horizon_ticks'] if first else ''))
        first = False
ex = d.get('extras') or {}
print('\nMined per-play extras: %s icebow8 pairs tested (Bonferroni z %s); listed = raw CI low > 0 (candidates; a library '
      'entry needs Bonferroni = yes):\n' % (ex.get('tested'), ex.get('z_bonferroni')))
print('| pair (A>B:lane rel + B zone) | n A-plays (B in hand) | treated (B next) | win lift [95% CI] | Bonferroni |')
print('|---|---|---|---|---|')
for e in ex.get('pairs', []):
    if e['ci'][0] is not None and e['ci'][0] > 0:
        print('| %s | %d | %d | %s | %s |' % (e['pair'], e['n'], e['n_tr'], f(e), 'yes' if e['bonferroni'] else 'no'))
