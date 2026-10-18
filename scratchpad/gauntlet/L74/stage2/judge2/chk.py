import json, math
from math import comb
def fisher_exact(t):
    (a,b),(c,d)=t; r1=a+b; c1=a+c; n=a+b+c+d
    p=lambda k: comb(c1,k)*comb(n-c1,r1-k)/comb(n,r1)
    p0=p(a); return sum(p(k) for k in range(max(0,r1+c1-n),min(r1,c1)+1) if p(k)<=p0*(1+1e-9))
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate/live_targets.json"))
H = "Hog (incl. Royal Hogs)"
rows = [x for x in R if x["mark"]=="CXXXVIII" and x["src"]=="ladder" and x["start"] is not None and x["start"]>=13000]
rows.sort(key=lambda x: x["ts"])
print("13k CXXXVIII n", len(rows))
for half,(a,b) in (("first",(0,len(rows)-35)),("last35",(len(rows)-35,len(rows)))):
    s=rows[a:b]
    for lab,f in (("HogOT",lambda x:x["cls"]==H and x["ot"]),("HogReg",lambda x:x["cls"]==H and not x["ot"]),("restOT",lambda x:x["cls"]!=H and x["ot"])):
        t=[x for x in s if f(x)]; print(half,lab,sum(x["res"]=="WIN" for x in t),"/",len(t))
print("fisher HogOT 1/13 vs 22/31", fisher_exact([[1,12],[22,9]]))
print("fisher HogReg 5/8 vs 10/23", fisher_exact([[5,3],[10,13]]))
# draws
from collections import Counter
print(Counter(x["res"] for x in rows))
# OT dur distribution on 13k hog OT
print(sorted((x["dur_s"],x["res"]) for x in rows if x["cls"]==H and x["ot"]))
# tower level z
p1,n1,p2,n2=144,300,40,57
pp=(p1+p2)/(n1+n2); se=math.sqrt(pp*(1-pp)*(1/n1+1/n2)); print("lvl z",(p2/n2-p1/n1)/se)
