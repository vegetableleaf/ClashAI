import re,sys,os
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache'
f=sys.argv[1]
mode=sys.argv[2] if len(sys.argv)>2 else 'all'
t=open(os.path.join(CACHE,f),encoding='utf-8').read()
if mode in ('all','var'):
    vd=re.findall(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*)\}\}', t)
    print('--- VARDEFINES (%d) ---'%len(vd))
    for n,v in vd: print('  %-30s %s'%(n,v.strip()))
if mode in ('all','tab'):
    print('--- TABLES ---')
    for m in re.finditer(r'\{\{StatisticsSubheader\|([^}]*)\}\}\s*(\{\|.*?\n\|\})', t, re.S):
        print('### '+m.group(1))
        print(m.group(2))
        print()
    # also any unit-attributes tables without subheader
    for m in re.finditer(r'\{\|class="wikitable" id="unit-attributes-table[^"]*"(.*?)\n\|\}', t, re.S):
        pass
if mode in ('all','hist'):
    print('--- HISTORY ---')
    m=re.search(r'^==\s*History\s*==\s*$(.*?)(?=^==[^=]|\Z)', t, re.S|re.M)
    print(m.group(1).strip() if m else 'NO HISTORY SECTION')
if mode in ('all','intro'):
    print('--- INTRO ---')
    print(t[:t.find('==Strategy==') if '==Strategy==' in t else 3000][:3500])
