import re,sys,os
WC='C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
def clean(s):
    s=re.sub(r'\{\{Icon\|I=[^}]*\}\}','',s)
    s=re.sub(r'<br\s*/?>',' ',s)
    s=re.sub(r'\[\[[^|\]]*\|([^\]]*)\]\]',r'\1',s)
    s=re.sub(r'\[\[([^\]]*)\]\]',r'\1',s)
    s=re.sub(r'\{\{Rarity\|([^}]*)\}\}',r'\1',s)
    s=re.sub(r"'''?",'',s)
    return s.strip()
def main(fn, hist=1):
    t=open(WC+fn,encoding='utf-8').read()
    print('###FILE',fn,'len',len(t))
    print('--- VARDEFINES ---')
    for m in re.finditer(r'\{\{#vardefine:\s*([^|]+?)\s*\|\s*([^}]*?)\s*\}\}', t):
        print('  %-28s = %s' % (m.group(1), m.group(2)))
    print('--- ATTRIBUTE TABLES ---')
    # find StatisticsSubheader labels and wikitable blocks
    for m in re.finditer(r'\{\{StatisticsSubheader\|([^}]*)\}\}\s*(\{\|.*?\n\|\})', t, re.S):
        label=m.group(1); tbl=m.group(2)
        if 'unit-statistics-table' in tbl:   # the big per-level table: skip body
            continue
        hdr=[clean(x) for x in re.findall(r'^!\s*scope="col"\s*\|(.*)$', tbl, re.M)]
        rows=[]
        for line in tbl.split('\n'):
            if line.startswith('|') and '||' in line and not line.startswith('|-') and not line.startswith('|}'):
                rows.append(clean(line[1:]))
        print('  ['+label+']')
        print('   HDR:', ' | '.join(hdr))
        for r in rows: print('   ROW:', r)
    print('--- HISTORY ---')
    if hist:
        i=t.find('==History==')
        if i<0: i=t.find('== History ==')
        if i<0: print('  (no History section)')
        else:
            j=t.find('\n==',i+5)
            seg=t[i:j if j>0 else len(t)]
            for line in seg.split('\n'):
                line=line.strip()
                if line.startswith('*') or line.startswith(':'):
                    print('   ', clean(line))
if __name__=='__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv)>2 else 1)
