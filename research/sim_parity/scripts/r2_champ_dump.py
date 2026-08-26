import re,sys,os
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
def load(f): return open(os.path.join(CACHE,f),encoding='utf-8').read()
def vardefs(t):
    return re.findall(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t)
def tables(t):
    """yield (subheader, [headers], [rows]) for each unit-attributes table"""
    out=[]
    for m in re.finditer(r'\{\{StatisticsSubheader\|([^}]*)\}\}\s*\n(\{\|.*?\n\|\})', t, re.S):
        name=m.group(1); body=m.group(2)
        heads=[re.sub(r'<br\s*/?>.*','',h).replace('! scope="col" |','').strip()
               for h in re.findall(r'^!\s*scope="col"\s*\|(.*)$', body, re.M)]
        heads=[re.sub(r'<br\s*/?>.*','',h.strip()) for h in heads]
        rows=[]
        for line in body.split('\n'):
            ls=line.strip()
            if ls.startswith('|') and '||' in ls:
                rows.append([c.strip() for c in ls.lstrip('|').split('||')])
        out.append((name,heads,rows))
    return out
def section(t,name):
    m=re.search(r'^==\s*'+re.escape(name)+r'\s*==\s*$(.*?)(?=^==[^=]|\Z)', t, re.S|re.M)
    return m.group(1) if m else None
if __name__=='__main__':
    f=sys.argv[1]; t=load(f)
    print('######## VARDEFINES ########')
    for k,v in vardefs(t): print('  %-22s = %s'%(k,v))
    print('######## TABLES ########')
    for name,heads,rows in tables(t):
        print('--- %s ---'%name)
        for r in rows:
            for i,c in enumerate(r):
                h=heads[i] if i<len(heads) else '?%d'%i
                print('     %-24s : %s'%(h,c))
            print('     .')
