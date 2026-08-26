import re,sys,os
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
def load(name): return open(os.path.join(CACHE,name+'.wikitext'),encoding='utf-8').read()
def vardefs(t):
    return {m.group(1).strip():m.group(2).strip() for m in re.finditer(r'\{\{#vardefine:\s*([^|]+)\|([^}]*)\}\}',t)}
def infobox(t):
    m=re.search(r'\{\{(?:Evolved )?Card Infobox\|([^}]*)\}\}',t)
    if not m: return {}
    return dict(p.split('=',1) for p in m.group(1).split('|') if '=' in p)
def attr_table(t):
    """Return list of (header,value) for the unit-attributes-table."""
    i=t.find('unit-attributes-table')
    if i==-1: return []
    j=t.find('{|',0)
    # find the table start before i
    starts=[m.start() for m in re.finditer(r'\{\|',t) if m.start()<=i]
    s=starts[-1]; e=t.find('|}',i)
    blk=t[s:e]
    heads=[re.sub(r'<br\s*/?>.*','',h).replace('! scope="col" |','').replace('!scope="col"|','').strip()
           for h in re.findall(r'^!.*$',blk,re.M)]
    rows=[l for l in blk.split('\n') if l.startswith('|') and '||' in l]
    out=[]
    for r in rows:
        vals=[v.strip() for v in r.lstrip('|').split('||')]
        out.append(list(zip(heads,vals)))
    return out
def section(t,name):
    m=re.search(r'^==\s*'+re.escape(name)+r'\s*==\s*$',t,re.M)
    if not m: return ''
    nxt=re.search(r'^==[^=]',t[m.end():],re.M)
    return t[m.end(): m.end()+(nxt.start() if nxt else len(t))]
if __name__=='__main__':
    n=sys.argv[1]; t=load(n)
    print('--- VARDEFINES ---')
    for k,v in vardefs(t).items(): print('  %-22s %s'%(k,v))
    print('--- INFOBOX ---')
    for k,v in infobox(t).items(): print('  %-14s %s'%(k,v))
    print('--- ATTR TABLE ---')
    for row in attr_table(t):
        for h,v in row: print('  %-18s %s'%(h,v))
    if len(sys.argv)>2:
        print('--- HISTORY ---'); print(section(t,'History').strip())
