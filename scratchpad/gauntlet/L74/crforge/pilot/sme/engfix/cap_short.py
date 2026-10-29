"""ENG-FIX5: from ENG-FIX4's cap_census.txt, the plays whose uncapped bank was only a little above 10 at the first read after
the drop (excess = uncapped - 10 < LIM): did the read fit the capped bank (10 - cost + regen) or the uncapped one (unc - cost)?
python cap_short.py CAP_CENSUS.txt [LIM]"""
import sys
lim = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
rows = []
for l in open(sys.argv[1]):
    f = l.split()
    if len(f) < 13 or f[1] != 't' or f[12] == 'None':
        continue
    m, t, e1, rate, um, cost = f[0], int(f[2]), float(f[4]), float(f[6]), float(f[8]), int(f[12])
    exc = um - (10 - e1)
    fit = 'UNCAPPED' if abs(um - cost) < 0.002 else 'capped' if abs(((10 - cost - e1) / rate) - round((10 - cost - e1) / rate)) < 0.05 else 'other'
    rows.append((exc, m, t, e1, rate, cost, fit))
short = sorted(r for r in rows if r[0] < lim)
print('plays', len(rows), 'with excess <', lim, ':', len(short))
for r in short:
    print('excess %.4f %s t %d e1 %.4f rate %.4f cost %d %s' % r)
