import glob, json, os
rows = []
for f in sorted(glob.glob('C:/Users/benpe/ClashBot/.foreman/scratch/recon6/diag/live_play_*_base.txt')):
    m = os.path.basename(f)[:-9]
    def head(p):
        l = open(p).readline()
        try:
            return json.loads(l)
        except Exception:
            return None
    b, n = head(f), head(f[:-9] + '_noopp.txt')
    rows.append((m, b, n))
out = ['match | RECON-5 final plan: exact, div, first div | opponent hero/evo slot flags cleared: exact, div, first div | verdict']
worse = same = better = 0
for m, b, n in rows:
    fb, fn = b['first'], n['first']
    v = 'worse (first div earlier)' if (fn or 10**9) < (fb or 10**9) else 'same first div' if fn == fb else 'better'
    if v.startswith('worse'): worse += 1
    elif v.startswith('same'): same += 1
    else: better += 1
    out.append('%s | %d, %d, %s | %d, %d, %s | %s' % (m[10:], b['counts'].get('exact', 0), b['counts'].get('div', 0), fb, n['counts'].get('exact', 0), n['counts'].get('div', 0), fn, v))
out.append('15 records: worse %d, same %d, better %d' % (worse, same, better))
open('C:/Users/benpe/ClashBot/.foreman/scratch/recon6/probe_table.txt', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
