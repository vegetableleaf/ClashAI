import re,sys,statistics as st
rows=[]
for l in open(sys.argv[1]):
    m=re.search(r"by_misfit=\[([^\]]*)\]",l)
    if not m: print("ERR",l[:150]); continue
    b=[int(x) for x in m.group(1).split(",")]
    rows.append(b)
n=len(rows)
for k in range(4):
    c=[r[k] for r in rows]
    print(f"misfit={k}: matches with >=1 candidate {sum(x>0 for x in c)}/{n}, unique {sum(x==1 for x in c)}, median candidates {st.median(c)}")
mins=[next((r[k] for k in range(4) if r[k]>0),0) for r in rows]
print("at the lowest misfit with any candidate: unique",sum(x==1 for x in mins),"none",sum(x==0 for x in mins),"median",st.median(mins),"min",min(x for x in mins if x>0) if any(mins) else None)
