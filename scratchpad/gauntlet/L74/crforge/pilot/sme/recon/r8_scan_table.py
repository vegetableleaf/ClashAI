"""RECON-8: tally of r8_scan.py rows.  python -I recon/r8_scan_table.py scan.jsonl [gk_records_first_div.txt]
A press is OK as extracted when the SIM's Golden Knight reproduces every REC frame of its window (asis == n). A press that is not OK is
'fixed by drop' when the dropped plan reproduces every frame, 'fixed by shift' when some run tick does (the best one listed), else 'open'."""
import collections, json, sys

rows = [json.loads(l) for l in open(sys.argv[1])]
fd = {}   # match -> the record's final first divergence (None = every frame exact), from gk_records_first_div.txt ("match first_div counts set")
if len(sys.argv) > 2:
    for l in open(sys.argv[2]):
        p = l.split(); fd[p[0]] = None if p[1] == 'None' else int(p[1])
cls = collections.Counter(); bad = []
for r in rows:
    n = r['n']
    if n == 0:
        cls['no_frames'] += 1; continue
    if r['asis'] == n:
        cls['ok'] += 1
    elif r['drop'] == n:
        cls['fixed_by_drop'] += 1; bad.append((r, 'drop'))
    elif r['best_run_score'] is not None and r['best_run_score'] == n:
        cls['fixed_by_shift'] += 1; bad.append((r, 'shift %s' % [k for k, v in r['runs'].items() if v == n]))
    elif fd.get(r['match']) is not None and fd[r['match']] < r['tick'] - 4:
        cls['upstream_divergence'] += 1; bad.append((r, 'upstream: the record already diverges at %d, before this press' % fd[r['match']]))
    else:
        cls['open'] += 1; bad.append((r, 'open (best shift %s %s/%s, drop %s)' % (r['best_run'], r['best_run_score'], n, r['drop'])))
print('GK presses', len(rows), dict(cls), 'records', len({r['match'] for r in rows}))
for src in ('gk_dash', 'gk_buff'):
    sub = [r for r in rows if r['source'] == src and r['n']]
    print(' ', src, len(sub), 'ok', sum(r['asis'] == r['n'] for r in sub))
print('records', len({r['match'] for r in rows}), 'with no first divergence', sum(1 for m in {r['match'] for r in rows} if m in fd and fd[m] is None), 'of', sum(1 for m in {r['match'] for r in rows} if m in fd))
print('not OK as extracted:')
for r, how in bad:
    print('  %s cmd %d %s tick %d run %d (window %d-%d)  n %d asis %d drop %d -> %s' % (r['match'][-13:], r['cmd'], r['source'], r['tick'], r['run'], r['lo'], r['hi'], r['n'], r['asis'], r['drop'], how))
