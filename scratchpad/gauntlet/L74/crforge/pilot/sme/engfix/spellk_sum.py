"""Summarise spellk_census.py output per card: king-sourced shots, on the line (offline <= 50), k integral (+-0.05),
rule tick inside the extractor window [prev, first - 1], rule tick != default.
    python -I spellk_sum.py CENSUS.tsv"""
import collections, csv, sys
c = collections.defaultdict(collections.Counter)
for r in csv.DictReader(open(sys.argv[1]), delimiter='\t'):
    s = c[r['card']]
    s['shots'] += 1
    if not (r['src'] or '').endswith('K'):
        continue
    s['king_src'] += 1
    k, off = float(r['k']), float(r['offline'])
    if off > 50:
        continue
    s['on_line'] += 1
    if abs(k - round(k)) > .05:
        s['k_frac'] += 1
        continue
    s['k_int'] += 1
    s['k=%d' % round(k)] += 1
    rr, lo, hi = int(r['rule_run']), int(r['prev']), int(r['first']) - 1
    s['in_window' if lo <= rr <= max(lo, hi) else 'out_window'] += 1
    s['differs' if rr != int(r['default_tick']) else 'same'] += 1
for k, s in sorted(c.items()):
    print(k, dict(s))
