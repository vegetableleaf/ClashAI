# python3 trk.py RUN M t0 side x y   (rec point at t0) -- rec vs sim track of that body, sim target / neighbours
import json,sys
sys.path.insert(0,"/workspace/pilot/sme")
from sme import run_batch
from sme_live import load_frames, runnable
run,m,t0,side,x,y=sys.argv[1],"live_play_"+sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),int(sys.argv[6])
plan=json.load(open("%s/%s/plan.json"%(run,m))); fr=load_frames("/workspace/pilot/sme_live/frames2/"+m+".jsonl")
o=run_batch([(runnable(plan),t0+6,t0-40)],"/tmp/a2c4/trk")[0]; by={s["t"]:s for s in o}
# sim twin at t0: nearest same-side C to the rec point
e0=min((e for e in by[t0]["E"] if e[3]==side and e[1]=="C"),key=lambda e:abs(e[4]-x)+abs(e[5]-y)); sid=e0[0]
print("body",e0[2],"src",e0[8])
px,py=x,y
for t in range(t0+4,t0-30,-1):
    e=next((e for e in by.get(t,{"E":[]})["E"] if e[0]==sid),None)
    r=None
    if t in fr and e:
        r=min((q for q in fr[t]["E"] if q[0]==side),key=lambda q:abs(q[1]-e[4])+abs(q[2]-e[5]))
    tg=next((g for g in by[t]["E"] if e and len(e)>12 and g[0]==e[12]),None) if e else None
    nb=sorted((abs(g[4]-e[4])+abs(g[5]-e[5]),g[2],g[3]) for g in by[t]["E"] if e and g[1]=="C" and g[0]!=sid and abs(g[4]-e[4])+abs(g[5]-e[5])<1600)[:3] if e else []
    print(t,"sim",e and (e[4],e[5],e[6]),"rec",r and (r[1],r[2],r[4]),"d",r and e and (r[1]-e[4],r[2]-e[5]),"tgt",tg and (tg[2],tg[4],tg[5]),"near",nb)
