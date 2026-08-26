import re, sys, json
CACHE='research/sim_parity/webcache/'
def digest(fn, hist_grep=None):
    t=open(CACHE+fn,encoding='utf-8').read()
    print('#### FILE:',fn,'len',len(t))
    # infobox
    m=re.search(r'\{\{Card Infobox(.*?)\}\}', t, re.S)
    if m: print('INFOBOX:', m.group(1).replace('\n',' ')[:400])
    # vardefines
    for vm in re.finditer(r'\{\{#vardefine:\s*([^|]+?)\s*\|\s*([^}]+?)\s*\}\}', t):
        print('VAR:', vm.group(1),'=',vm.group(2))
    # attribute tables: capture each wikitable id=unit-attributes-table block (header + rows)
    for tm in re.finditer(r'\{\|[^\n]*unit-attributes-table.*?\n\|\}', t, re.S):
        blk=tm.group(0)
        hdr=[h.split('<br>')[0].strip('!scope="col"| ') for h in re.findall(r'!scope="col"\|([^\n]+)', blk)]
        rows=[r for r in re.findall(r'\n\|([^\-\}][^\n]*)', blk) if '||' in r]
        print('ATTR HDR:', ' ; '.join(hdr))
        for r in rows: print('ATTR ROW:', r.strip())
    # any other subheader labels near tables (multi-mode cards)
    for sm in re.finditer(r'\{\{StatisticsSubheader\|([^}]+)\}\}', t):
        print('SUBHEADER:', sm.group(1))
    # history section: dated bullets
    hm=re.search(r'==\s*History\s*==(.*?)(\n==[^=]|\Z)', t, re.S)
    if hm:
        h=hm.group(1)
        lines=[l for l in h.split('\n') if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}', l) and l.strip().startswith('*')]
        print('HISTORY (%d dated lines):'%len(lines))
        for l in lines:
            l2=re.sub(r'\[\[([^\]|]*\|)?([^\]]*)\]\]', r'\2', l)
            l2=re.sub(r"'''?",'',l2)
            if hist_grep and not re.search(hist_grep,l2,re.I): continue
            print(' ', l2.strip()[:300])
if __name__=='__main__':
    digest(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
