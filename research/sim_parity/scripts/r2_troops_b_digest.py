import re, os, sys, json
CACHE=os.path.join(os.path.dirname(__file__),'..','webcache')
def digest(fn):
    wt=open(os.path.join(CACHE,fn),encoding='utf-8').read()
    out={}
    out['vardefines']=re.findall(r'\{\{#vardefine:\s*([\w ]+?)\s*\|\s*([^}|]*?)\s*\}\}',wt)
    # attributes tables: find each wikitable with id="unit-attributes-table"
    tables=[]
    for m in re.finditer(r'\{\|[^\n]*unit-attributes-table.*?\n\|\}', wt, re.S):
        tab=m.group(0)
        headers=re.findall(r'!scope="col"\|([^<\n]+)', tab)
        rows=[r.strip() for r in re.findall(r'\n\|([^-}!][^\n]*)', tab) if r.strip()]
        tables.append({'headers':headers,'rows':rows})
    out['attr_tables']=tables
    # any other named stat-ish tables (e.g. secondary unit attributes) - capture captions
    caps=re.findall(r'\{\{StatisticsSubheader\|([^}]*)\}\}', wt)
    out['subheaders']=caps
    # history section
    hm=re.search(r'==\s*History\s*==(.*?)(\n==[^=]|\Z)', wt, re.S)
    hist=[]
    if hm:
        for line in hm.group(1).splitlines():
            l=line.strip()
            if l.startswith('*') and re.search(r'\d', l):
                hist.append(l)
    out['history']=hist
    return out
if __name__=='__main__':
    fn=sys.argv[1]
    d=digest(fn)
    print("### VARDEFINES")
    for k,v in d['vardefines']: print(f"  {k} = {v}")
    print("### SUBHEADERS", d['subheaders'])
    for i,t in enumerate(d['attr_tables']):
        print(f"### ATTR TABLE {i}: {' | '.join(t['headers'])}")
        for r in t['rows']: print("   ROW:", r)
    print("### HISTORY (%d lines)" % len(d['history']))
    for l in d['history']: print("  ", l)
