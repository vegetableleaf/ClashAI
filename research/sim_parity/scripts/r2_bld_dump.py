"""R2 buildings: dump P1 vardefines / P2 attribute tables / P3 history for one page."""
import re,sys,os
CACHE=os.path.join(os.path.dirname(__file__),"..","webcache")

def load(t): return open(os.path.join(CACHE,t.replace(' ','_')+'.wikitext'),encoding='utf-8').read()

def p1(src):
    return re.findall(r'\{\{#vardefine:\s*([^|]+?)\s*\|\s*([^}]*?)\s*\}\}', src)

def tables(src):
    """every wikitable with its id, returned as (id, header_cells, data_rows)."""
    out=[]
    for m in re.finditer(r'\{\|(?![^\n]*?class="wikitable"[^\n]*?collapsible)[^\n]*\n', src):
        start=m.start()
        # find matching |}
        depth=0; i=start; end=None
        while i < len(src)-1:
            if src[i]=='{' and src[i+1]=='|': depth+=1; i+=2; continue
            if src[i]=='|' and src[i+1]=='}':
                depth-=1; i+=2
                if depth==0: end=i; break
                continue
            i+=1
        if end is None: continue
        blk=src[start:end]
        tid=re.search(r'id="([^"]+)"',blk.split('\n')[0])
        out.append((tid.group(1) if tid else '(no-id)', blk))
    return out

def history(src):
    m=re.search(r'\n==\s*History\s*==\s*\n(.*?)(?=\n==[^=]|\Z)', src, re.S)
    return m.group(1) if m else ''

if __name__=='__main__':
    t=sys.argv[1]; what=sys.argv[2] if len(sys.argv)>2 else 'all'
    src=load(t)
    if what in ('all','p1'):
        print('===== P1 VARDEFINES : %s ====='%t)
        for n,v in p1(src): print('  %-28s = %s'%(n,v))
    if what in ('all','p2'):
        print('===== P2 TABLES : %s ====='%t)
        for tid,blk in tables(src):
            if 'statistics-table' in tid: 
                print('--- table id=%s  [level table, showing first data rows] ---'%tid)
                print('\n'.join(blk.split('\n')[:6])); print('   ...[formula-driven, skipped]')
                continue
            print('--- table id=%s ---'%tid); print(blk)
    if what in ('all','p3'):
        print('===== P3 HISTORY : %s ====='%t)
        print(history(src))
