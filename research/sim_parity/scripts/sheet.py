import re, sys, os
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"

def load(f):
    return open(os.path.join(CACHE, f), encoding="utf-8").read()

def vardefines(t):
    out=[]
    for m in re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t):
        out.append((m.group(1), m.group(2)))
    return out

def attr_tables(t):
    """Return every wikitable that has an id=... containing 'attributes' or 'statistics',
       plus any table row that looks like a stat row."""
    blocks=[]
    for m in re.finditer(r'\{\|[^\n]*id="([^"]*)"(.*?)\n\|\}', t, re.S):
        tid=m.group(1); body=m.group(2)
        blocks.append((tid, body))
    return blocks

def history(t):
    m=re.search(r'\n==\s*History\s*==\s*\n(.*?)(?=\n==[^=]|\Z)', t, re.S)
    return m.group(1) if m else ""

def sections(t):
    return re.findall(r'\n(==+\s*[^=\n]+\s*==+)', t)

if __name__=="__main__":
    f=sys.argv[1]
    what=sys.argv[2] if len(sys.argv)>2 else "all"
    t=load(f)
    if what in ("all","var"):
        print("### VARDEFINES");  [print(f"   {n:18s} = {v}") for n,v in vardefines(t)]
    if what in ("all","tab"):
        print("\n### TABLES (id -> body)")
        for tid, body in attr_tables(t):
            print(f"\n--- id={tid} ---")
            lines=[l for l in body.split("\n") if l.strip()]
            for l in lines[:40]:
                if "#expr" in l and "1.1^" in l: 
                    continue
                print("   ", l[:400])
    if what in ("all","sec"):
        print("\n### SECTIONS"); [print("   ",s.strip()) for s in sections(t)]
    if what in ("all","hist"):
        h=history(t)
        print("\n### HISTORY (%d chars)"%len(h))
        print(h[:12000])
