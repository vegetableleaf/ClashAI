import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
def digest(cf, show_history=True):
    t=open(CACHE+cf,encoding='utf-8').read()
    print('#### FILE:',cf, 'revid line:', t.split('\n',1)[0])
    # infobox
    m=re.search(r'\{\{Evolved Card Infobox([^}]*)\}\}',t)
    if m: print('INFOBOX:',m.group(1).strip())
    # vardefines
    for vm in re.finditer(r'\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]+?)\s*\}\}',t):
        print('VARDEF:',vm.group(1),'=',vm.group(2))
    # attribute tables: find subheader name then table rows
    for tm in re.finditer(r'\{\{StatisticsSubheader\|([^}]+)\}\}\s*\n\{\|(.*?)\n\|\}', t, re.S):
        name=tm.group(1); body=tm.group(2)
        heads=re.findall(r'!scope="col"\|(.+)',body)
        heads=[re.sub(r'<br\s*/?>.*','',h).strip() for h in heads]
        # data rows: lines starting with | that contain ||
        rows=[l for l in body.split('\n') if l.startswith('|') and '||' in l]
        print('TABLE [%s]: headers=%s'%(name,heads))
        for r in rows[:4]:
            cells=[c.strip() for c in r.lstrip('|').split('||')]
            print('   ROW:',cells)
    if show_history:
        hm=re.search(r'==\s*History\s*==(.*?)(\n==[^=]|\Z)',t,re.S)
        if hm:
            lines=[l for l in hm.group(1).split('\n') if l.strip().startswith('*')]
            print('HISTORY (%d lines):'%len(lines))
            for l in lines: print('  ',l.strip()[:400])
        else:
            print('HISTORY: none found')
if __name__=='__main__':
    for cf in sys.argv[1:]:
        digest(cf)
        print('='*80)
