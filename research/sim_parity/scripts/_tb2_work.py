import re,os,json,sys
sys.path.insert(0,'C:/Users/benpe/ClashBot/research/sim_parity/scripts')
from attrs import parse_attr_table, clean
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
DB=json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json',encoding='utf-8'))['cards']
import yaml
CUR=yaml.safe_load(open('C:/Users/benpe/ClashBot/icebow/config/cards.yaml',encoding='utf-8'))['cards']

def vardefines(t):
    return [(m.group(1),m.group(2).strip()) for m in
            re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_ ]+?)\s*\|\s*([^}]*?)\s*\}\}',t)]

def hist(t, since=2024):
    i=t.find('==History==')
    if i<0: i=t.find('== History ==')
    if i<0: return []
    j=t.find('\n==',i+5)
    seg=t[i:j if j>0 else len(t)]
    out=[]
    for line in seg.split('\n'):
        ls=line.strip()
        if not (ls.startswith('*') or ls.startswith(':')): continue
        m=re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})',ls)
        yr=int(m.group(3)) if m else 0
        if yr>=since: out.append((yr,clean(ls)))
    return out

def show(fn, keys, since=2024, tids=('unit-attributes-table','unit-attributes-table-secondary','unit-attributes-table-tertiary')):
    t=open(CACHE+fn,encoding='utf-8').read()
    print('#'*70); print('# PAGE',fn,'len',len(t))
    print('--- P1 VARDEFINES ---')
    for k,v in vardefines(t): print('   %-30s = %s'%(k,v))
    print('--- P2 ATTRIBUTE TABLES ---')
    for tid in tids:
        r=parse_attr_table(t,tid)
        if not r: continue
        heads,rows=r
        print('  ['+tid+']')
        for row in rows:
            for h,c in zip(heads,row): print('     %-32s : %s'%(h,c))
            print('     ---')
    # any other subheaders present
    for m in re.finditer(r'\{\{StatisticsSubheader\|([^}]*)\}\}',t):
        print('  (subheader present:',m.group(1),')')
    print('--- P3 HISTORY (>=%d) ---'%since)
    for yr,l in hist(t,since): print('   ',l)
    print('--- DB ROWS ---')
    for k in keys:
        d=DB.get(k,{})
        print('  ==',k,'==')
        for f in sorted(d): print('     %-24s %s'%(f,json.dumps(d[f])))
        c=CUR.get(k)
        if c: print('     CURATED(verified=%s): %s'%(c.get('verified'),json.dumps({a:b for a,b in sorted(c.items()) if a!='verified'})))
if __name__=='__main__':
    fn=sys.argv[1]; keys=sys.argv[2].split(','); since=int(sys.argv[3]) if len(sys.argv)>3 else 2024
    show(fn,keys,since)
