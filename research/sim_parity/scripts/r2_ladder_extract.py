# -*- coding: utf-8 -*-
"""Pull the rendered per-level statistics table out of each cached rendered page."""
import re, html, json, io, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
C = r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'

def strip(c):
    c = re.sub(r'<[^>]+>', '', c)
    return re.sub(r'\s+', ' ', html.unescape(c)).strip()

def stat_table(hpath):
    h = open(hpath, encoding='utf-8').read()
    m = re.search(r'<table[^>]*id="unit-statistics-table"[^>]*>(.*?)</table>', h, re.S)
    if not m:
        return None, None
    body = m.group(1)
    rows = []
    for rm in re.finditer(r'<tr[^>]*>(.*?)</tr>', body, re.S):
        cells = [strip(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rm.group(1), re.S)]
        if cells:
            rows.append(cells)
    return rows[0], rows[1:]

if __name__ == '__main__':
    for fn in sorted(os.listdir(C)):
        if not fn.endswith('.rendered.html'):
            continue
        hdr, rows = stat_table(os.path.join(C, fn))
        print('#####', fn.replace('.rendered.html', ''))
        if hdr is None:
            print('   NO unit-statistics-table'); continue
        print('   HDR:', ' | '.join(hdr))
        print('   L%s: %s' % (rows[0][0], ' | '.join(rows[0][1:])))
        print('   L%s: %s' % (rows[-1][0], ' | '.join(rows[-1][1:])))
        print('   rows:', [r[0] for r in rows])
